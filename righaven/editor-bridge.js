/* Trusted adapter loaded before a checksum-verified upstream WASM editor. */
(()=>{
'use strict';
// Scope the compatibility fallback to this iframe, before the upstream WASM
// module chooses its graphics backend. WebGL2 is an upstream-supported backend.
if(new URLSearchParams(location.search).get('rh-renderer')==='compatible'){
 try{Object.defineProperty(navigator,'gpu',{get:()=>undefined,configurable:true});}catch{}
}
const origin=location.origin,pending=new Map(),filmPaths=new Map();
let incoming=[],opened=false,opening=false,projectRoot="",loadingProject=false,manifest=[],fileBase="";
const send=(type,extra={})=>parent.postMessage({type,...extra},origin);
const asFiles=rows=>rows.map(row=>new File([row.bytes],row.name,{type:'application/octet-stream'}));
const walk=(value,transform)=>{if(Array.isArray(value)){value.forEach(v=>walk(v,transform));return;}if(value&&typeof value==='object')for(const key of Object.keys(value)){if(key==='sequence'&&value.type==='Footage'&&Array.isArray(value[key]))value[key]=value[key].map(ref=>typeof ref==='string'?transform(ref):ref);else if(['path','file_path','filename'].includes(key)&&typeof value[key]==='string'&&value[key])value[key]=transform(value[key]);else walk(value[key],transform);}};
function save(name,bytes){
 if(/\.(fcproj|ecproj)$/i.test(name)&&filmPaths.size){const doc=JSON.parse(new TextDecoder().decode(bytes));walk(doc,ref=>filmPaths.get(ref)||ref);bytes=new TextEncoder().encode(JSON.stringify(doc)).buffer;}
 return new Promise((resolve,reject)=>{const requestId=crypto.randomUUID();const timeout=setTimeout(()=>{pending.delete(requestId);reject(Error('RigHaven did not confirm the save; keep this editor open and retry.'));},30000);pending.set(requestId,{resolve,reject,timeout});send('rh-editor-save',{name,bytes,requestId});});
}
const italian=()=>navigator.language.toLowerCase().startsWith('it');
function destination(kind,name=''){
 return new Promise((resolve,reject)=>{
  const dialog=document.createElement('dialog');dialog.style.cssText='color:#e7eeee;background:#182326;border:1px solid #648078;border-radius:12px;padding:24px;max-width:85vw;font:16px system-ui';
  const title=document.createElement('h2');title.textContent=kind==='open'?(italian()?'Apri da':'Open from'):(italian()?'Salva con nome':'Save as');dialog.append(title);
  const field=document.createElement(kind==='open'?'select':'input');field.style.cssText='display:block;width:100%;margin-bottom:16px;font:inherit';
  if(kind==='open')for(const row of manifest){const option=document.createElement('option');option.value=option.textContent=row.name;field.append(option);}
  else field.value=name;
  dialog.append(field);
  const finish=value=>{dialog.close();dialog.remove();resolve({...value,name:field.value});};
  for(const [label,target] of [[italian()?'File della chat (server)':'Chat files (server)','server'],[italian()?'Questo dispositivo':'This device','device']]){
   const button=document.createElement('button');button.textContent=label;button.style.cssText='padding:10px;margin:4px;font:inherit';button.onclick=()=>finish({target});dialog.append(button);
  }
  const cancel=document.createElement('button');cancel.textContent=italian()?'Annulla':'Cancel';cancel.onclick=()=>{dialog.close();dialog.remove();reject(new DOMException('Cancelled','AbortError'));};dialog.append(cancel);
  dialog.addEventListener('cancel',()=>{dialog.remove();reject(new DOMException('Cancelled','AbortError'));});document.body.append(dialog);dialog.showModal();
 });
}
window.showSaveFilePicker=async options=>{
 const choice=await destination('save',options?.suggestedName||incoming[0]?.name||'document');
 const name=choice.name;if(!name)throw new DOMException('A filename is required','AbortError');
 return {kind:'file',name,async queryPermission(){return 'granted';},async requestPermission(){return 'granted';},async createWritable(){let blob=new Blob();let position=0;return {
 async write(data){if(data?.type==='seek'){position=data.position;return;}if(data?.type==='truncate'){blob=new Blob([blob.slice(0,data.size),new Uint8Array(Math.max(0,data.size-blob.size))]);position=Math.min(position,data.size);return;}if(data?.type==='write'){if(data.position!==undefined)position=data.position;data=data.data;}const part=new Blob([data]);blob=new Blob([blob.slice(0,position),new Uint8Array(Math.max(0,position-blob.size)),part,blob.slice(position+part.size)]);position+=part.size;},
 async close(){if(choice.target==='server')await save(name,await blob.arrayBuffer());else{const url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=name.split('/').pop();anchorClick.call(link);setTimeout(()=>URL.revokeObjectURL(url),60000);}},async abort(){blob=new Blob();}};}};
};
// Use the native file input instead of pretending a plain object is a browser
// FileSystemFileHandle (some upstream apps explicitly check its native class).
Object.defineProperty(window,'showOpenFilePicker',{value:undefined,configurable:true});
const inputClick=HTMLInputElement.prototype.click;
HTMLInputElement.prototype.click=function(){
 if(this.type!=='file')return inputClick.call(this);
 if(!opening){
  if(!fileBase)return inputClick.call(this);
  const input=this;
  destination('open').then(async choice=>{
   if(choice.target==='device'){inputClick.call(input);return;}
   send('rh-editor-select',{name:choice.name});
  }).catch(error=>{if(error.name!=='AbortError')send('rh-editor-error',{error:String(error)});});return;
 }
 if(!incoming.length)return;
 const transfer=new DataTransfer();for(const file of asFiles(this.multiple?incoming:incoming.slice(0,1)))transfer.items.add(file);
 this.files=transfer.files;opened=true;opening=false;queueMicrotask(()=>{this.dispatchEvent(new Event('input',{bubbles:true}));this.dispatchEvent(new Event('change',{bubbles:true}));send('rh-editor-opened');});
};
const anchorClick=HTMLAnchorElement.prototype.click;
HTMLAnchorElement.prototype.click=function(){
 if(this.download&&(this.href.startsWith('blob:')||this.href.startsWith('data:'))){
  const link=this,name=this.download;
  // Read before the upstream application revokes its temporary object URL.
  const bytes=fetch(this.href).then(r=>r.arrayBuffer());
  destination('save',name).then(async choice=>{
   const data=await bytes;
   if(choice.target==='server')await save(choice.name,data);
   else{const url=URL.createObjectURL(new Blob([data])),copy=document.createElement('a');copy.href=url;copy.download=choice.name;anchorClick.call(copy);setTimeout(()=>URL.revokeObjectURL(url),60000);}
  }).catch(error=>{if(error.name!=='AbortError')send('rh-editor-error',{error:String(error)});});return;
 }
 return anchorClick.call(this);
};
const referenceName=(ref,project)=>{
 let absolute=new URL(ref,'https://project.invalid/'+(projectRoot?projectRoot+'/':'')+project.name).pathname.slice(1);
 if(absolute.startsWith('mnt/user-data/'))absolute=absolute.slice('mnt/user-data/'.length);
 if(projectRoot){
  if(absolute.startsWith(projectRoot+'/'))return absolute.slice(projectRoot.length+1);
  if(['uploads/','outputs/','workspace/'].some(prefix=>absolute.startsWith(prefix)))return '@chat/'+absolute;
 }
 return absolute;
};
async function openEffect(){
 // These are cache budgets, not a hard cap on the WASM heap or decoded media.
 // Configure before importing/rendering so startup cannot fill multi-GB previews.
 await window.effectcraft.execute('prefs.set',{values:{'memory.layerCacheMb':64,'memory.mediaCacheMb':64,'memory.previewCacheMb':128,'previews.cacheFramesWhenIdle':false,'disk.diskCacheEnabled':false}});
 const project=incoming[0],paths=new Map(),folders=new Map();filmPaths.clear();
 for(const row of incoming.slice(1)){const folder=row.name.slice(0,row.name.lastIndexOf('/'));if(!folders.has(folder))folders.set(folder,folders.size);paths.set(row.name,await window.effectcraft.addFile(new File([row.bytes],'righaven-'+folders.get(folder)+'-'+row.name.split('/').pop())));}
 const doc=JSON.parse(new TextDecoder().decode(project.bytes));
 walk(doc,ref=>{const mapped=paths.get(referenceName(ref,project));if(mapped){filmPaths.set(mapped,ref);return mapped;}return ref;});
 await window.effectcraft.addFile(new File([JSON.stringify(doc)],project.name));
 // Relink through the native API: document-origin paths and files explicitly
 // imported into this browser session have different trust/resolution rules.
 // Replacing the media keeps item IDs, so layers retain their source links.
 for(const item of Object.values(doc.items||{})){
  const footage=item.kind;if(footage?.type!=='Footage'||!filmPaths.has(footage.path))continue;
  await window.effectcraft.execute('file.replaceFootage',{item:item.id,path:footage.path});
  const interpretation={items:[item.id],alpha:{Straight:'straight',Premultiplied:'premultiplied',Ignore:'ignore'}[footage.alpha],pixelAspect:footage.pixel_aspect,loop:footage.loop_count,matteColor:footage.premul_color};
  if(footage.kind!=='Still'&&footage.frame_rate?.den)interpretation.frameRate=footage.kind==='Video'&&!footage.native_rate?'file':footage.frame_rate.num/footage.frame_rate.den;
  if(typeof footage.color_profile==='string')interpretation.colorProfile=footage.color_profile.toLowerCase();
  if(typeof footage.fields==='string'){const fields={off:'off',none:'off',progressive:'off',upper:'upper',upperfirst:'upper',lower:'lower',lowerfirst:'lower'}[footage.fields.toLowerCase()];if(fields)interpretation.fields=fields;}
  if(footage.start_timecode!==undefined&&footage.start_timecode!==null){interpretation.overrideStart=true;interpretation.startTimecode=footage.start_timecode;}
  for(const [old,key] of [['invert_alpha','invertAlpha'],['linear_light','linearLight'],['preserve_rgb','preserveRgb']])if(footage[old]!==undefined)interpretation[key]=footage[old];
  await window.effectcraft.execute('file.interpretFootage',interpretation);
  await window.effectcraft.execute('project.rename',{item:item.id,name:item.name});
 }
 const proof=await window.effectcraft.execute('footage.check',{wait:true});
 if(proof.missing)throw Error('EffectCraft could not reopen '+proof.missing+' referenced media files; inspect the project assets before saving.');
 incoming=incoming.map(row=>({name:row.name,bytes:new ArrayBuffer(0)}));
 opened=true;send('rh-editor-opened');
}
async function openFilm(){
 const project=incoming[0],doc=JSON.parse(new TextDecoder().decode(project.bytes)),refs=new Set();
 walk(doc,ref=>{refs.add(referenceName(ref,project));return ref;});
 const media=incoming.filter(row=>refs.has(row.name));if(media.length!==refs.size)throw Error('FilmCraft media missing from the project folder');
 const imported=await window.filmcraft.importFiles(asFiles(media));if(imported.errors?.length)throw Error('FilmCraft media import failed: '+JSON.stringify(imported.errors));
 const mapping=new Map(media.map((row,i)=>[row.name,imported.paths[i]]));filmPaths.clear();
 walk(doc,ref=>{const mapped=mapping.get(referenceName(ref,project));if(mapped){filmPaths.set(mapped,ref);return mapped;}return ref;});
 await window.filmcraft.openProject(new File([JSON.stringify(doc)],project.name.split('/').pop()));opened=true;send('rh-editor-opened');
}
async function saveCurrent(){
 if(window.effectcraft?.saveToBrowser&&incoming[0]?.name.toLowerCase().endsWith('.ecproj')){
  await window.effectcraft.saveToBrowser('/'+incoming[0].name);
  const bytes=window.effectcraft.readFile('/'+incoming[0].name);
  if(!bytes)throw Error('EffectCraft did not return the saved project');
  await save(incoming[0].name,bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength));
  return;
 }
 const canvas=document.querySelector('canvas');canvas?.focus();
 for(const type of ['keydown','keyup'])(canvas||document).dispatchEvent(new KeyboardEvent(type,{key:'s',code:'KeyS',ctrlKey:true,bubbles:true}));
}
addEventListener('keydown',event=>{
 if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'&&window.effectcraft?.saveToBrowser){event.preventDefault();event.stopImmediatePropagation();saveCurrent().catch(error=>send('rh-editor-error',{error:String(error)}));}
},true);
addEventListener('message',event=>{
 if(event.source!==parent||event.origin!==origin)return;
 const data=event.data;
 if(data?.type==='rh-editor-native-save'){
  destination('save',data.name).then(async choice=>{
   if(choice.target==='server')await save(choice.name,data.bytes);
   else{const link=document.createElement('a'),url=URL.createObjectURL(new Blob([data.bytes]));link.href=url;link.download=choice.name;anchorClick.call(link);setTimeout(()=>URL.revokeObjectURL(url),60000);}
   send('rh-editor-destination-settled');
  }).catch(error=>{send('rh-editor-destination-settled',{cancelled:true});if(error.name!=='AbortError')send('rh-editor-error',{error:String(error)});});return;
 }
 if(data?.type==='rh-editor-resource'){if(window.effectcraft?.addFile){window.effectcraft.addFile(new File([data.bytes],data.name)).catch(error=>send('rh-editor-error',{error:String(error)}));return;}incoming=[data,...incoming.filter(row=>row.name!==data.name)];opening=true;const canvas=document.querySelector('canvas');canvas?.focus();for(const type of ['keydown','keyup'])(canvas||document).dispatchEvent(new KeyboardEvent(type,{key:'o',code:'KeyO',ctrlKey:true,bubbles:true}));return;}
 if(data?.type==='rh-editor-save-current')saveCurrent().catch(error=>send('rh-editor-error',{error:String(error)}));
 if(data?.type==='rh-editor-manifest'){manifest=data.manifest||[];return;}
 if(data?.type==='rh-editor-files'){incoming=data.files;projectRoot=data.projectRoot||'';manifest=data.manifest||[];fileBase=data.fileBase||'';}
 if(data?.type==='rh-editor-saved'){const ticket=pending.get(data.requestId);if(ticket){clearTimeout(ticket.timeout);pending.delete(data.requestId);data.error?ticket.reject(Error(data.error)):ticket.resolve();}send('rh-editor-dirty',{dirty:!!data.error});}
 if(data?.type==='rh-editor-open'){
  if(!incoming.length)return;
  if(window.effectcraft?.addFile&&incoming[0].name.toLowerCase().endsWith('.ecproj')){if(loadingProject)return;loadingProject=true;openEffect().catch(error=>send('rh-editor-error',{error:String(error)})).finally(()=>{loadingProject=false;});return;}
  if(window.filmcraft?.openProject&&incoming[0].name.toLowerCase().endsWith('.fcproj')){openFilm().catch(error=>send('rh-editor-error',{error:String(error)}));return;}
  if(window.vectorcraft?.openFile){window.vectorcraft.openFile(incoming[0].name,new Uint8Array(incoming[0].bytes));opened=true;send('rh-editor-opened');return;}
  opening=true;
  const canvas=document.querySelector('canvas');canvas?.focus();for(const type of ['keydown','keyup'])(canvas||document).dispatchEvent(new KeyboardEvent(type,{key:'o',code:'KeyO',ctrlKey:true,bubbles:true}));
 }
});
// A Trunk module can finish before its canvas runner accepts keyboard input.
const canvasReady=()=>{const canvas=document.querySelector('canvas');if(!canvas)return false;const loading=document.querySelector('[id$="_loading"],#loading');return !loading||getComputedStyle(loading).display==='none';};
let ticks=0;const probe=setInterval(()=>{ticks++;if(window.effectcraftLoad?.readyMs||window.filmcraftLoad?.readyMs||!window.effectcraftLoad&&!window.filmcraftLoad&&canvasReady()&&ticks>=4){send('rh-editor-ready');clearInterval(probe);}else if(ticks>240){send('rh-editor-error',{error:'Editor startup timed out; check browser WebGL/WebGPU support.'});clearInterval(probe);}},500);
let deviceLostHandled=false;
new MutationObserver(()=>{
 if(deviceLostHandled||!document.getElementById('device-lost'))return;
 deviceLostHandled=true;send('rh-editor-device-lost');
 (async()=>{
  if(!window.effectcraft?.saveToBrowser||!incoming[0]?.name.toLowerCase().endsWith('.ecproj'))throw Error('Recovery unavailable: save the project with the editor before reloading.');
  try{await window.effectcraft.execute('playback.stop',{});}catch{}
  await saveCurrent();
  send('rh-editor-device-lost',{error:'Graphics device lost. Your current project was saved to the chat; reopen the editor in Compatibility mode.'});
 })().catch(error=>send('rh-editor-device-lost',{error:'Graphics device lost. Recovery save was not confirmed: '+String(error)+'. Keep this page open and use Save Project to download a copy.'}));
}).observe(document,{childList:true,subtree:true});
send('rh-editor-adapter');
})();
