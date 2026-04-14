import puppeteer, { type Browser } from "puppeteer-core";
import fs from "fs";
import path from "path";

import notifier from "node-notifier";

let browser: Browser | null = null;

const timetable_path = path.resolve("./timetable.txt");
const icon_path = path.resolve("./icon.png");
const cookies_path = path.resolve("./cookies.json");

import creds from "./creds.json" assert { "type": "json" };

function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

process.on("uncaughtException", (error, origin) => {
    console.log(`Uncaught exception: ${error}, origin: ${origin}`);
});

console.log("Starting puppeteer");

const executables = ["/usr/bin/chromium-browser", "/usr/bin/chromium"];

for (const executable of executables) {
    try {
        browser = await puppeteer.launch({
            executablePath: executable,
            headless: true,
            args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
        });
        break;
    } catch (error) {
        console.log(`${executable} not found, trying next`);
    }
}

if (!browser) {
    process.exit(1);
}

const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080 });

// load cookies
if (fs.existsSync(cookies_path)) {
    const cookiesString = fs.readFileSync("./cookies.json").toString();
    const cookies = JSON.parse(cookiesString);
    await page.setCookie(...cookies);
    console.log("Loaded cookies");
}

console.log("Puppeteer started");

await page.goto("https://mano.vilniustech.lt", { waitUntil: "networkidle2" });
// wait for redirects
await sleep(10000);

console.log("Loaded mano.vilniustech");

// check if we need to log in
if (await page.evaluate(() => document.querySelector("#password"))) {
    await page.type("#username", creds.username);
    await page.type("#password", creds.password);
    await page.click('[type="submit"]');

    await sleep(3000);
    console.log("Logged in");
} else {
    console.log("No need to login");
}

// check if "Consent about releasing personal information" exists
if (await page.evaluate(() => document.querySelector("#acceptance"))) {
    await page.evaluate(() => {
        (document.querySelector("#acceptance") as HTMLElement).click();
        setTimeout(() => {
            (document.querySelector("#yesbutton") as HTMLElement).click();
        }, 1000);
    });
    await sleep(3000);
    console.log("Accepted consent");
} else {
    console.log("No need to accept consent");
}

// save cookies
const cookies = await page.cookies();
fs.writeFileSync(cookies_path, JSON.stringify(cookies, null, 2));
console.log("Saved cookies");

// wait for main page to load
try {
    await page.waitForSelector(".week");
    const week = await page.evaluate(() => document.querySelector(".week")?.textContent?.trim().replace("week ", ""));
    console.log(`Current week: ${week}`);
} catch (error) {
    console.log(`Error getting current week, day off? ${error}`);

    try {
        await page.waitForSelector(".lecture_time");
    } catch (error2) {
        console.log(`Something is wront with the page, not proceeding ${error2}`);
        process.exit(34);
    }
}

// call timetable endpoint
await page.goto("https://mano.vilniustech.lt/timetable/site/my-timetable");

const timetable_raw = await page.$eval("*", (el) => {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNode(el);
    selection?.removeAllRanges();
    selection?.addRange(range);
    return window.getSelection()?.toString();
});

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

type Subject = {
    index: string;
    time: string;
    week: string;
    group: string;
    name_and_type: string;
    auditorium: string;
};

function stringify<T>(obj: T): string {
    return JSON.stringify(obj);
}

function objectsEqual<T>(obj1: T, obj2: T): boolean {
    return stringify(obj1) === stringify(obj2);
}

async function notify(title: string, body: string, tags: string) {
    await fetch("https://ntfy.sh/mano_vilniustech_timetable_changed", {
        method: "POST",
        body: body,
        headers: { Tags: tags, Title: title },
    });
    console.log(`${title}: ${body}`);
    notifier.notify({
        title: title,
        message: body,
        icon: icon_path,
    });
}

if (timetable_raw) {
    const searchStr = "Lecture\tTime\tWeek\tSubgroup\tSubject\tAuditorium\tLecturer\tType";
    const indexes = [...timetable_raw.matchAll(new RegExp(searchStr, "gi"))].map((a) => a.index);

    console.log("Current timetable:");

    let i = 0;
    const timetable_map: Map<string, Subject[]> = new Map();
    for (const index of indexes) {
        const last_index = timetable_raw.indexOf("\\n", index);
        const day_timetable = timetable_raw.substring(index + searchStr.length, last_index).trim();
        const day_timetable_subjects_sep = day_timetable.split("\n");
        const sub_timetable_entries = [];
        for (let i = 0; i < day_timetable_subjects_sep.length; i += 3) {
            // merge lecurer and type with the entry
            sub_timetable_entries.push(
                `${day_timetable_subjects_sep[i].trim()}\t${day_timetable_subjects_sep[
                    i + 1
                ].trim()}\t${day_timetable_subjects_sep[i + 2].trim()}`,
            );
        }
        const day_timetable_subjects: Subject[] = [];
        for (const entry of sub_timetable_entries) {
            const subject_raw = entry.split("\t");

            let type = "";

            switch (subject_raw[7]) {
                case "Lectures":
                    type = " (lecture)";
                    break;
                case "Practical exercises (practical work)":
                    type = " (lecture)";
                    break;
                case "Laboratory work (laboratory works)":
                    type = " (lab work)";
                    break;
            }

            const subject: Subject = {
                index: subject_raw[0],
                time: subject_raw[1],
                week: subject_raw[2],
                group: subject_raw[3],
                name_and_type: subject_raw[4].substring(0, subject_raw[4].indexOf("(") - 1) + type,
                auditorium: subject_raw[5].substring(0, subject_raw[5].indexOf("Auditorium")),
            };

            if (subject.group === "0" || subject.group === creds.group) {
                day_timetable_subjects.push(subject);
            } else {
                console.log(`Skipped ${stringify(subject)}`);
            }
        }
        console.log(days[i]);
        console.log(day_timetable_subjects);
        timetable_map.set(days[i], day_timetable_subjects);
        i++;
    }

    if (fs.existsSync(timetable_path)) {
        const timetable_map_old: Map<string, Subject[]> = new Map(
            JSON.parse(fs.readFileSync(timetable_path).toString()),
        );

        let changed = 0;

        const index_name_filter = (second_arr: Subject[], include: boolean) => (sub1: Subject) =>
            second_arr.some(
                (sub2: Subject) => sub1.index === sub2.index && sub1.name_and_type === sub2.name_and_type,
            ) === include;

        const equals_filter = (second_arr: Subject[]) => (sub1: Subject) =>
            !second_arr.some((sub2) => objectsEqual(sub1, sub2));

        for (const day of days) {
            const old_subjects = timetable_map_old.get(day) ?? [];
            const new_subjects = timetable_map.get(day) ?? [];

            let removed = old_subjects.filter(equals_filter(new_subjects));
            let added = new_subjects.filter(equals_filter(old_subjects));

            if (removed.length === 0 && added.length === 0) {
                console.log(`No changes on ${day}`);
                continue;
            }

            // elements both in removed and added
            const changed_subjects = removed.filter(index_name_filter(added, true));

            // removed changed elements
            removed = removed.filter(index_name_filter(changed_subjects, false));
            added = added.filter(index_name_filter(changed_subjects, false));

            changed += removed.length + added.length + changed_subjects.length;

            for (const ch_subject of changed_subjects) {
                await notify(
                    `${day} timetable changed`,
                    `${ch_subject.time} | ${ch_subject.name_and_type} changed`,
                    "orange_square",
                );
            }

            for (const rem_subject of removed) {
                await notify(
                    `${day} timetable changed`,
                    `${rem_subject.time} | ${rem_subject.name_and_type} removed`,
                    "orange_square",
                );
            }

            for (const add_subject of added) {
                await notify(
                    `${day} timetable changed`,
                    `${add_subject.time} | ${add_subject.name_and_type} added`,
                    "orange_square",
                );
            }
        }

        await notify("Timetable scrape done", `${changed} entries changed`, "green_square");
    }

    fs.writeFileSync(timetable_path, JSON.stringify(Array.from(timetable_map.entries())));
}

console.log("DONE");
process.exit(0);
