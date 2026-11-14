const {JSDOM,VirtualConsole}=require('jsdom');
const fs=require('fs');const path=require('path');const {webcrypto}=require('crypto');const root=path.resolve(__dirname,'..');
const origin=process.env.SPECTRA_UI_URL||'http://127.0.0.1:8765';
const report={status:'RUNNING',mode:'DOM functional checks against live local HTTP and separate worker; no browser layout rendering',checks:[],errors:[]};
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function until(f,timeout=180000){let t=Date.now();while(Date.now()-t<timeout){if(f())return;await wait(100);}throw Error('Timed out: '+f.toString());}
(async()=>{
 const vc=new VirtualConsole();vc.on('jsdomError',e=>{if(e.message.includes('Could not load img: \"blob:test-')){report.rendering_not_tested=true;}else report.errors.push(e.message);});
 const dom=await JSDOM.fromURL(origin,{resources:'usable',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,beforeParse(w){
  w.fetch=(url,options)=>fetch(new URL(url,origin),options);
  w.URL.createObjectURL=()=> 'blob:test-'+Math.random();w.URL.revokeObjectURL=()=>{};
  Object.defineProperty(w.crypto,'subtle',{value:webcrypto.subtle});
  w.HTMLAnchorElement.prototype.click=function(){report.download=this.download;};
 }});
 const w=dom.window,d=w.document,$=id=>d.getElementById(id);
 await until(()=>$('loginForm') && $('loginForm').onsubmit!==null || d.readyState==='complete',10000);
 await wait(100);
 $('token').value='bad-token';$('loginForm').querySelector('button').click();
 await until(()=>!$('error').hidden,10000);report.checks.push('Invalid token rejected');
 $('token').value=fs.readFileSync(path.join(process.env.SPECTRA_UI_STATE||path.join(root,'state'),'operator-token.txt'),'utf8').trim();
 $('loginForm').querySelector('button').click();await until(()=>!$('controls').hidden,15000);
 report.checks.push('Authenticated dataset catalog loaded');
 $('mode').value='review';$('run').click();await until(()=>!$('downloads').hidden);
 if($('candidateCount').textContent!=='638')throw Error('Unexpected candidate count: '+$('candidateCount').textContent);
 if($('population').textContent!=='Unavailable')throw Error('Missing population mislabeled');
 report.checks.push('Live review-mode job completed: 638 candidates; population unavailable');
 d.querySelector('[data-view="review"]').click();if(!$('topImageClip').hidden)throw Error('Wrong overlay state');
 d.querySelector('[data-view="compare"]').click();$('swipe').value='25';$('swipe').dispatchEvent(new w.Event('input'));
 if(!$('topImageClip').style.clipPath.includes('75%'))throw Error('Slider failed');
 report.checks.push('Raster mode switch and before/after slider update DOM');
 [...$('files').querySelectorAll('button')].find(b=>b.textContent==='REPORT.md').click();
 await until(()=>report.download==='REPORT.md',15000);report.checks.push('Download passed client SHA-256 verification');
 if(!$('events').textContent.includes('RUNNING'))throw Error('Missing event timeline');
 $('disconnect').click();if($('login').hidden||!$('imageBox').hidden)throw Error('Disconnect failed');
 report.checks.push('Disconnect clears view and returns login');
 report.status=report.errors.length?'FAIL':'PASS_FUNCTIONAL_ONLY';report.rendering_note='Blob image rendering and layout were not tested by this DOM harness. Headless browser launch was unavailable.';dom.window.close();
 fs.writeFileSync(path.join(root,'reports/ui-check.json'),JSON.stringify(report,null,2));
 console.log(JSON.stringify(report));if(report.errors.length)process.exitCode=1;
})().catch(e=>{report.status='FAIL';report.errors.push(e.stack);fs.writeFileSync(path.join(root,'reports/ui-check.json'),JSON.stringify(report,null,2));console.error(e);process.exitCode=1;});
