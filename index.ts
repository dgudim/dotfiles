import puppeteer, { Browser, Page } from "puppeteer";
import fs from "fs";

import creds from "./creds.json" assert {"type": "json"};

let browser: Browser;
let page: Page;

function sleep(ms: number) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

process.on('uncaughtException', (error, origin) => {
    console.log(`Uncaught exception: ${error}, origin: ${origin}`);
});

console.log("Starting puppeteer");
browser = await puppeteer.launch({
    args: ['--no-sandbox', '--disable-setuid-sandbox']
});

page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080 });

// load cookies
if (fs.existsSync("./cookies.json")) {
    const cookiesString = fs.readFileSync('./cookies.json').toString();
    const cookies = JSON.parse(cookiesString);
    await page.setCookie(...cookies);
    console.log("Loaded cookies");
}

console.log("Puppeteer started");

await page.goto("https://mano.vilniustech.lt", { waitUntil: "networkidle2" });
// wait for redirects
await sleep(10000);

console.log(`Loaded mano.vilniustech`);

// check if we need to log in
if (await page.evaluate(() => document.querySelector("#password"))) {
    await page.type("#username", creds.username);
    await page.type("#password", creds.password);
    await page.click("[type=\"submit\"]");

    await sleep(3000);
    console.log(`Logged in`);
} else {
    console.log(`No need to login`);
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
    console.log(`Accepted consent`);
} else {
    console.log(`No need to accept consent`);
}

// save cookies
const cookies = await page.cookies();
fs.writeFileSync('./cookies.json', JSON.stringify(cookies, null, 2));
console.log("Saved cookies");

// wait for main page to load
await page.waitForSelector(".week");

const week = await page.evaluate(() => document.querySelector(".week")?.textContent?.trim().replace("week ", ""));
console.log(`Current week: ${week}`);

// call timetable endpoint
await page.goto("https://mano.vilniustech.lt/timetable/site/my-timetable");

const timetable_raw = await page.$eval('*', (el) => {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNode(el);
    selection?.removeAllRanges();
    selection?.addRange(range);
    return window.getSelection()?.toString();
});

const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

type Subject = {
    index: string,
    time: string,
    week: string,
    group: string,
    name_and_type: string,
    auditorium: string
}

function stringify(obj: any): string {
    return JSON.stringify(obj);
}

function objectsEqual(obj1: any, obj2: any): boolean {
    return stringify(obj1) === stringify(obj2);
}

if (timetable_raw) {

    const searchStr = "Lecture\tTime\tWeek\tSubgroup\tSubject\tAuditorium\tLecturer\tType";
    const indexes = [...timetable_raw.matchAll(new RegExp(searchStr, 'gi'))].map(a => a.index);

    console.log('Current timetable:');

    let i = 0;
    let timetable_map: Map<string, Subject[]> = new Map();
    for (const index of indexes) {
        const last_index = timetable_raw.indexOf("\\n", index);
        const day_timetable = timetable_raw.substring(index! + searchStr.length, last_index).trim();
        const day_timetable_subjects_sep = day_timetable.split("\n");
        let sub_timetable_entries = [];
        for (let i = 0; i < day_timetable_subjects_sep.length; i += 3) {
            // merge lecurer and type with the entry
            sub_timetable_entries.push(
                day_timetable_subjects_sep[i].trim() + "\t" +
                day_timetable_subjects_sep[i + 1].trim() + "\t" +
                day_timetable_subjects_sep[i + 2].trim());
        }
        let day_timetable_subjects: Subject[] = [];
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
                auditorium: subject_raw[5].substring(0, subject_raw[5].indexOf("Auditorium"))
            };

            if (subject.group == "0" || subject.group == creds.group) {
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

    if (fs.existsSync("./timetable.txt")) {

        const timetable_map_old: Map<string, Subject[]> = new Map(JSON.parse(fs.readFileSync("./timetable.txt").toString()));

        let changed: number = 0;

        for (const day of days) {
            const old_subjects = timetable_map_old.get(day) || [];
            const new_subjects = timetable_map.get(day) || [];

            const removed = old_subjects.filter((old_sub: Subject) => !new_subjects.some(new_sub => objectsEqual(old_sub, new_sub)));
            const added = new_subjects.filter((new_sub: Subject) => !old_subjects.some(old_sub => objectsEqual(old_sub, new_sub)));

            if (removed.length == 0 && added.length == 0) {
                console.log(`No changes on ${day}`);
                continue;
            }

            changed += removed.length + added.length;

            for (const rem_subject of removed) {
                await fetch('https://ntfy.sh/mano_vilniustech_timetable_changed', {
                    method: 'POST',
                    body: `${rem_entry[1]} | ${rem_entry[4]} removed`,
                    headers: { 'Tags': 'orange_square', 'Title': `${day} timetable changed` }
                });
                console.log(`added ${stringify(rem_subject)}`);
            }

            for (const add_subject of added) {
                await fetch('https://ntfy.sh/mano_vilniustech_timetable_changed', {
                    method: 'POST',
                    body: `${add_entry[1]} | ${add_entry[4]} added`,
                    headers: { 'Tags': 'orange_square', 'Title': `${day} timetable changed` }
                });
                console.log(`added ${stringify(add_subject)}`);
            }
        }

        await fetch('https://ntfy.sh/mano_vilniustech_timetable_changed', {
            method: 'POST',
            body: `${changed} entries changed`,
            headers: { 'Tags': 'green_square', 'Title': 'Timetable scrape done' }
        })
        console.log(`Scrape done, ${changed} entries changed`);

    }

    fs.writeFileSync('./timetable.txt', JSON.stringify(Array.from(timetable_map.entries())));
}

console.log("DONE");
process.exit(0);
