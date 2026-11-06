"use client";
import {useState} from "react";

import {fetch} from "@/core/api/fetcher";
import {buildArtifactViewerURL} from "@/core/artifacts/viewer";
import {getBackendBaseURL} from "@/core/config";
import {useI18n} from "@/core/i18n/hooks";

/** Save a new source, never overwrite the published delivery or imply rebuilt exports. */
export function SourceCopyEditor({threadId,filepath,content,sha256,truncated,isMock}:{threadId:string;filepath:string;content?:string;sha256?:string;truncated:boolean;isMock:boolean}){
 const {locale}=useI18n();const it=locale==="it-IT";const t=(a:string,b:string)=>it?a:b;
 const [draft,setDraft]=useState<{text:string;sha:string}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(""),[saved,setSaved]=useState("");
 const supported=/\.(md|markdown|txt|csv|tsv|json|yaml|yml|html|css|js|ts|py|sql|xml|svg)$/i.test(filepath);
 if(isMock||!supported||truncated||content===undefined||!sha256||!/^[0-9a-f]{64}$/.test(sha256)||new TextEncoder().encode(content).byteLength>1024*1024)return null;
 async function save(){if(!draft||busy)return;setBusy(true);setError("");try{
  const r=await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-source-edits`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({path:filepath,expected_sha256:draft.sha,content:draft.text})});
  const v=await r.json() as {path:string;detail?:string};if(!r.ok)throw Error(v.detail??String(r.status));setSaved(v.path);setDraft(null);
 }catch(e){setError(e instanceof Error?e.message:String(e));}finally{setBusy(false);}}
 return <section className="shrink-0 space-y-2 border-b p-3 text-sm" data-testid="source-copy-editor">
  {!draft?<button type="button" className="rounded border px-3 py-1" onClick={()=>{setDraft({text:content,sha:sha256});setSaved("");setError("");}}>{t("Modifica una copia","Edit a copy")}</button>:<>
   <p>{t("Il salvataggio crea una copia del sorgente. L’originale e le esportazioni restano conservati.","Saving creates a source copy. The original and exports are retained.")}</p>
   <textarea aria-label={t("Contenuto del sorgente","Source content")} className="h-[35dvh] w-full rounded border p-2 font-mono text-xs" value={draft.text} maxLength={1024*1024} onChange={e=>setDraft({...draft,text:e.target.value})}/>
   <div className="flex gap-2"><button type="button" className="rounded border px-3 py-1" disabled={busy} onClick={()=>void save()}>{t("Salva copia revisionata","Save revised copy")}</button><button type="button" disabled={busy} onClick={()=>setDraft(null)}>{t("Annulla","Cancel")}</button></div>
  </>}
  {saved&&<p role="status">{t("Copia salvata. Torna in chat per chiederne l’integrazione e rigenerare le esportazioni.","Copy saved. Return to chat to request integration and regenerate exports.")} <a className="underline" href={buildArtifactViewerURL({filepath:saved,threadId,isMock:false})}>{t("Apri la copia","Open the copy")}</a></p>}
  {error&&<p role="alert">{error}</p>}
 </section>;
}
