/** Optional real-browser workflow check. Run `npm install`, `npx playwright install chromium`,
 * then `npm run test:browser`. Starts and stops its own Python server.
 */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const assert=require('node:assert/strict');
const path=require('node:path');
const port=8876,base=`http://127.0.0.1:${port}`;
const server=spawn(process.env.CURVEDESK_PYTHON||'python',['-m','curvedesk','serve','--port',String(port)],{cwd:path.resolve(__dirname,'..'),stdio:'inherit'});
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function ready(){for(let i=0;i<60;i++){try{if((await fetch(base+'/api/health')).ok)return;}catch{}await delay(100);}throw Error('Server did not start');}
(async()=>{let browser;try{
 await ready();browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1500,height:1100}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.waitForFunction(()=>!document.getElementById('export').disabled);
 assert.match(await page.locator('#status').innerText(),/SYNTHETIC DEMO/);
 assert.equal(await page.locator('#parChart polyline').count(),2);
 await page.locator('[data-tab="bond"]').click();await page.selectOption('#mode','clean');await page.fill('#value','98.25');await page.locator('#coupon').click();
 await page.waitForFunction(()=>!document.getElementById('export').disabled&&document.getElementById('bondMetrics').innerText.includes('98.2500'));
 await page.locator('[data-tab="scenarios"]').click();await page.locator('#plus100').click();await page.waitForFunction(()=>!document.getElementById('export').disabled&&document.getElementById('customPnl').innerText.includes('−$'));
 await page.locator('[data-tab="portfolio"]').click();const downloadPromise=page.waitForEvent('download');await page.locator('#portfolioExport').click();assert.equal((await downloadPromise).suggestedFilename(),'positions.csv');
 await page.locator('#portfolioFile').setInputFiles(path.join(__dirname,'../examples/positions.csv'));await page.waitForFunction(()=>!document.getElementById('export').disabled);
 await page.locator('[data-tab="methods"]').click();await page.locator('#curveFile').setInputFiles(path.join(__dirname,'../examples/synthetic_curve.csv'));await page.waitForFunction(()=>!document.getElementById('export').disabled&&document.getElementById('status').innerText.includes('IMPORTED CURVE'));
 // Network-independent failure test: no silent fallback or loss of source selection.
 await page.route('**/api/refresh',route=>route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({error:'Simulated offline; saved snapshot unchanged'})}));
 await page.locator('#refresh').click();await page.waitForFunction(()=>!document.getElementById('error').hidden);assert.equal(await page.inputValue('#source'),'custom');
 await page.selectOption('#source','demo');await page.waitForFunction(()=>!document.getElementById('export').disabled&&document.getElementById('status').innerText.includes('SYNTHETIC DEMO'));
 await page.locator('[data-tab="overview"]').click();await page.screenshot({path:'test-results/dashboard-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/dashboard-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);console.log('Browser workflows passed. Screenshots saved in test-results/.');
 }finally{if(browser)await browser.close();server.kill();}})().catch(e=>{console.error(e);process.exitCode=1;});
