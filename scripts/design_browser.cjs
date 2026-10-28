// The three diagram SDKs share the already installed Chromium, not a second browser.
const fs=require('node:fs'),path=require('node:path'),{createRequire}=require('node:module');
(async()=>{
 const [app,appRoot,webRoot,source,output]=process.argv.slice(2);
 const req=createRequire(path.join(appRoot,'package.json'));
 const {chromium}=req('playwright-core');
 let executablePath=process.env.RIGHAVEN_BROWSER_EXECUTABLE;
 if(!executablePath){const root=process.env.PLAYWRIGHT_BROWSERS_PATH||'/opt/righaven/playwright-browsers';const dir=fs.readdirSync(root).find(n=>n.startsWith('chromium_headless_shell-'));if(!dir)throw Error('Shared Chromium not installed');executablePath=path.join(root,dir,'chrome-linux/headless_shell');if(!fs.existsSync(executablePath))executablePath=path.join(root,dir,'chrome-headless-shell-linux64/chrome-headless-shell');}
 const browser=await chromium.launch({executablePath,headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}});page.on('pageerror',error=>console.error(error.message));page.on('console',msg=>{if(msg.type()==='error')console.error(msg.text());});
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url());if(url.origin!=='http://righaven.local')return route.abort();
  const file=path.resolve(webRoot,decodeURIComponent(url.pathname).replace(/^\//,'')||'index.html');
  if(!file.startsWith(path.resolve(webRoot)+path.sep))return route.abort();
  try{const ext=path.extname(file);await route.fulfill({status:200,body:fs.readFileSync(file),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2'})[ext]||'application/octet-stream'});}catch{return route.fulfill({status:404,body:''});}
 });
 await page.goto('http://righaven.local/');await page.waitForFunction(()=>!!window.righaven,{timeout:60000});
 const input=fs.readFileSync(source,'utf8');
 const result=await page.evaluate(async({app,input})=>window.righaven.render(app==='excalidraw'?JSON.parse(input):input),{app,input});
 if(!result.svg?.includes('<svg'))throw Error('SDK did not produce an SVG');
 fs.writeFileSync(path.join(output,'diagram.svg'),result.svg);
 if(result.model)fs.writeFileSync(path.join(output,'project.excalidraw'),JSON.stringify(result.model,null,2));
 fs.writeFileSync(path.join(output,'inspection.json'),JSON.stringify({status:'passed',elements:result.elements??null,engine:app,review:'Native syntax/import and rendering, not design quality'},null,2));
 await page.setContent(result.svg,{waitUntil:'load'});
 const svg=page.locator('svg').first();await svg.screenshot({path:path.join(output,'diagram.png'),timeout:60000});
 await page.addStyleTag({content:'html,body{margin:0;padding:0}svg{display:block}'});const bounds=await svg.boundingBox();
 if(!bounds||bounds.width>16000||bounds.height>16000)throw Error('Diagram exceeds the verified single-page PDF size; reduce the view scope');
 await page.pdf({path:path.join(output,'diagram.pdf'),printBackground:true,width:Math.ceil(bounds.width)+'px',height:Math.ceil(bounds.height)+'px',margin:{top:0,right:0,bottom:0,left:0}});
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
