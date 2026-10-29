// Real browser evidence. No claim that automated accessibility checks are complete.
const fs=require('fs');
const path=require('path');
async function main(){
 const [root,url,output]=process.argv.slice(2);
 const {chromium}=require(path.join(root,'apps/axe-core/node_modules/playwright-core'));
 const AxeBuilder=require(path.join(root,'apps/axe-core/node_modules/@axe-core/playwright')).default;
 const browser=await chromium.launch({headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const context=await browser.newContext();const page=await context.newPage();await page.goto(url,{waitUntil:'networkidle',timeout:45000});
  const results=await new AxeBuilder({page}).analyze();
  fs.writeFileSync(output,JSON.stringify(results,null,2));
 }finally{await browser.close();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
