// Explicit browser operations; scripts and assertions remain part of the sources.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

(async () => {
  const [url, output, width, height] = process.argv.slice(2);
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
  try {
    const page = await browser.newPage({ viewport: { width: Number(width), height: Number(height) } });
    await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.screenshot({ path: output, fullPage: true });
    console.log(JSON.stringify({ title: await page.title(), url: page.url(), output }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
