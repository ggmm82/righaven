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
  // Exercise the native model console against API contracts, without paid calls.
  const fixture = {profiles:{coordinator:{engine:'codex',model:'gpt-6.1-sol',ready:true},squad:{engine:'deepseek',model:'deepseek-chat',ready:true}},connections:{codex:{credentials_present:true},gemini:{credentials_present:false},deepseek:{credentials_present:true},openai:{credentials_present:false}}};
  const reply = (route, value) => route.fulfill({contentType:'application/json',body:JSON.stringify(value)});
  await page.route('**/harness/api/catalog', route => reply(route,fixture));
  await page.route('**/harness/api/team/models*', route => reply(route,{models:['fixture-model']}));
  let assignment;
  await page.route('**/harness/api/team', route => {
    assignment = route.request().postDataJSON();
    fixture.profiles.squad={engine:assignment.engine,model:assignment.model,ready:true};
    return reply(route,{ok:true});
  });
  await page.goto('/workspace/harness');
  await page.getByRole('heading',{name:'Models & resources'}).waitFor();
  await page.getByLabel('Assign to',{exact:true}).selectOption('squad');
  await page.getByLabel('Provider',{exact:true}).selectOption('openai');
  await page.getByLabel('Endpoint URL',{exact:true}).fill('https://provider.example/v1');
  await page.getByLabel('API key',{exact:true}).fill('fixture-not-a-real-key');
  await page.getByRole('button',{name:'Load available models',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Model list refreshed.'}).waitFor();
  await page.getByLabel('Model ID',{exact:true}).fill('fixture-model');
  await page.getByRole('button',{name:'Check & save',exact:true}).click();
  await page.getByText('Connection checked and model assignments saved.',{exact:true}).waitFor();
  if(assignment?.scope!=='squad'||assignment?.base_url!=='https://provider.example/v1') throw Error('Native model scope or endpoint was lost');
  if(await page.getByLabel('API key',{exact:true}).inputValue()) throw Error('Private key was not cleared after saving');
  await page.getByText('gpt-6.1-sol',{exact:true}).waitFor();
  await page.screenshot({path:'reports/ui/models.png',fullPage:true});
  await page.getByLabel('Provider',{exact:true}).selectOption('codex');
  let loginCancelled=false;
  await page.route('**/harness/api/login/codex', route=>reply(route,{id:'fixture-session',engine:'codex',finished:false,text:''}));
  await page.route('**/harness/api/login-session/fixture-session', route=>{
    if(route.request().method()==='DELETE') loginCancelled=true;
    return reply(route,{id:'fixture-session',engine:'codex',finished:false,text:'Device code: ABCD-EFGH',authorization_url:'https://auth.openai.com/codex/device'});
  });
  await page.getByRole('button',{name:'Connect account',exact:true}).click();
  await page.getByRole('link',{name:'Open official sign-in',exact:true}).waitFor();
  await Promise.all([
    page.waitForResponse(response=>response.url().endsWith('/login-session/fixture-session')&&response.request().method()==='DELETE'),
    page.getByRole('button',{name:'Cancel sign-in',exact:true}).click(),
  ]);
  if(!loginCancelled)throw Error('Closing sign-in must release its session');
  await page.setViewportSize({width:390,height:844});
  await page.goto('/workspace');
  await page.getByRole('heading', {name:'From objective to outcome.'}).waitFor();
  if (await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)) throw Error('Mobile workspace overflows horizontally');
  await page.screenshot({path:'reports/ui/workspace-mobile.png',fullPage:true});
  if (errors.length) throw Error('Browser errors: '+errors.join('; '));
  console.log('RigHaven browser journey passed: login, overview, task, toolbox, deployment and mobile layout');
} finally { await context.close(); await browser.close(); }
