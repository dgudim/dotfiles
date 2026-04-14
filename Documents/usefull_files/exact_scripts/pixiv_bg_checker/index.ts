import puppeteer, { Browser, Page } from "puppeteer-core";
import fs from "fs";
import path from "path";

import readline from 'readline';

function askQuestion(query: string) {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
    });

    return new Promise(resolve => rl.question(query, (ans: string) => {
        rl.close();
        resolve(ans);
    }))
}

function sleep(ms: number) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

let browser: Browser;

console.log("Starting puppeteer");
// browser = await puppeteer.launch({
//     executablePath: "/usr/bin/google-chrome-stable",
//     headless: false,
//     args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"],
// });
const browserURL = 'http://127.0.0.1:21222';
browser = await puppeteer.connect({browserURL});

console.log("Puppeteer started");

const page = await browser.newPage();
await page.setViewport({ width: 1920, height: 1080 });
// await page.evaluateOnNewDocument(() => {
//     Object.defineProperty(navigator, 'platform', { get: () => 'Win32' })
//     Object.defineProperty(navigator, 'productSub', { get: () => '20100101' })
//     Object.defineProperty(navigator, 'vendor', { get: () => '' })
//     Object.defineProperty(navigator, 'oscpu', { get: () => 'Windows NT 10.0; Win64; x64' })
// })
    
// await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:73.0) Gecko/20100101 Firefox/73.0')
await page.goto(`https://www.pixiv.net`, {
    timeout: 240000
})
await askQuestion("Please log in")
await page.close()

const root = "/home/kloud/Pictures/Pictures/backgrounds/";

const authors: Map<string, string[]> = new Map();

fs.readdirSync(root).forEach((author: string) => {
    if (author.endsWith("pixiv")) {
        const parts = author.split('_')
        const author_id = parts[parts.length - 2].replace('id', '');
        console.log(`Found ${author_id}`);
        let artworks: string[] = []
        fs.readdirSync(`${root}/${author}`).forEach((file: string) => {
            const artwork_id = file.split('_')[0]
            console.log(`    ${artwork_id}`)
            artworks.push(artwork_id);
        });
        authors.set(author_id, artworks);
    }
});

async function check_artwork(art_id: string, author_id: string) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.goto(`https://www.pixiv.net/en/artworks/${art_id}`, {
        timeout: 240000
    })
    let author_followed = true;
    try {
        await page.waitForSelector(`a[data-gtm-value='${author_id}']`, {
            timeout: 240000
        });
        console.log(`✅ Confirmed artwork ${art_id}`);
        await page.waitForNetworkIdle()
        await sleep(2000);
        const button = await page.$(`button[data-gtm-user-id='${author_id}']`);
        if((await button?.evaluate((b) => b.outerText)) != "Following") {
            author_followed = false;
        }
    } catch (error) {
        console.log(`❌ Could not confirm artwork ${art_id} (author: ${author_id})`);
    }
    await page.close();
    return author_followed;
}

for (const [author, artworks] of authors) {
    console.log(`Checking ${author}`);
    let pages: Promise<boolean>[] = []
    for (const artwork of artworks) {
        console.log(`Checking artwork ${artwork}`);
        pages.push(check_artwork(artwork, author));
        //await check_artwork(artwork, author);
    }
    const res = await Promise.all(pages);
    if(!res[0]) {
        console.log(`❌ Not following ${author}`);
    }
}

await browser.close();