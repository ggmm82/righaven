import { chromium } from 'playwright';
import fs from 'node:fs/promises';

const browser = await chromium.launch({headless:true});
const context = await browser.newContext({
  baseURL: 'http://127.0.0.1:2026',
  httpCredentials: {username:'admin', password:process.env.RIGHAVEN_PASSWORD},
  viewport:{width:1440,height:1000},
});
try {
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  // Exercise the visible account flow, not an injected session cookie.
  await page.goto('/login');
  await page.locator('input[type="email"]').fill('harness-ci@example.com');
  await page.locator('input[type="password"]').fill('CiOnly-Strong-Login-P4ssword!78239');
  await page.getByRole('button', {name:'Sign In', exact:true}).click();
  await page.waitForURL('**/workspace');
  await page.getByRole('heading', {name:'From objective to outcome.'}).waitFor();
  await fs.mkdir('reports/ui', {recursive:true});
  await page.screenshot({path:'reports/ui/workspace.png',fullPage:true});
  await page.getByRole('link', {name:'New task',exact:true}).first().click();
  await page.getByRole('heading', {name:'What would you like to achieve?'}).waitFor();
  await page.screenshot({path:'reports/ui/new-task.png',fullPage:true});
  await page.goto('/workspace/cloud');
  await page.getByRole('heading', {name:'RigHaven Community'}).waitFor();
  await page.goto('/workspace/capabilities');
  await page.getByRole('heading', {name:'Tools & skills'}).waitFor();
  if (await page.getByRole('tab', {name:'Skills',exact:true}).getAttribute('data-state') !== 'active') throw Error('Skills must be the default capability surface');
  await page.setViewportSize({width:390,height:844});
  await page.goto('/workspace');
  await page.getByRole('heading', {name:'From objective to outcome.'}).waitFor();
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw Error('Mobile workspace overflows horizontally');
  await page.screenshot({path:'reports/ui/workspace-mobile.png',fullPage:true});
  if (errors.length) throw Error('Browser errors: '+errors.join('; '));
  console.log('RigHaven browser journey passed: login, overview, task, toolbox, deployment and mobile layout');
} finally { await context.close(); await browser.close(); }
