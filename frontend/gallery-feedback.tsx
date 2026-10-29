"use client";
import {useEffect,useState} from "react";
import {fetch} from "@/core/api/fetcher";
type Entry={id:string;version:string;parent:string|null;parent_excerpt?:string|null;score:number|null;body:string;display_name:string;mine:boolean;author_reply:boolean;created:number;updated:number};
type Discussion={versions:string[];items:Entry[];total:number;ratings:{version:string;count:number;average:number}[]};
const button="rounded-lg border px-3 py-2 text-sm disabled:opacity-50";
export default function GalleryFeedback({base,pack,version,locale}:{base:string;pack:string;version:string;locale:string}){
 const it=locale==="it";
 const [data,setData]=useState<Discussion|null>(null),[all,setAll]=useState(false),[offset,setOffset]=useState(0),[error,setError]=useState("");
 const [reviewVersion,setReviewVersion]=useState(version),[body,setBody]=useState(""),[score,setScore]=useState(""),[reply,setReply]=useState<Entry|null>(null),[busy,setBusy]=useState(false),[report,setReport]=useState<Entry|null>(null),[reason,setReason]=useState("");
 const path=`${base}/packs/${encodeURIComponent(pack)}/feedback`;
 async function load(signal?:AbortSignal){const response=await fetch(path+`?offset=${offset}${all?"":"&version="+encodeURIComponent(version)}`,{signal});const result=await response.json();if(!response.ok)throw Error(result.detail||"Feedback unavailable");if(!signal?.aborted)setData(result);}
 useEffect(()=>{const c=new AbortController();setData(null);setError("");void load(c.signal).catch(e=>{if(!c.signal.aborted)setError(String(e));});return()=>c.abort();},[path,all,offset,version]);
 async function action(url:string,method:string,value?:unknown){setBusy(true);setError("");try{const response=await fetch(url,{method,headers:{"Content-Type":"application/json"},...(value?{body:JSON.stringify(value)}:{})});if(!response.ok){const result=await response.json();throw Error(result.detail||"Operation failed");}await load();return true;}catch(e){setError(e instanceof Error?e.message:String(e));return false;}finally{setBusy(false);}}
 const currentRating=data?.ratings.find(r=>r.version===version);
 return <section className="space-y-4 border-t pt-4" aria-label={it?"Recensioni e commenti":"Ratings and comments"}>
  <h3 className="text-lg font-semibold">{it?"Recensioni e commenti":"Ratings and comments"}</h3>
  <p>{currentRating?`★ ${currentRating.average.toFixed(1)} / 5 · ${currentRating.count} ${it?"recensioni":"reviews"}`:(it?"Nessuna recensione per questa versione":"No reviews for this version")} · v{version}</p>
  <p className="text-xs text-muted-foreground">{it?"Esperienze dichiarate dagli utenti, non certificazioni. Un voto per utente e versione; puoi aggiornarlo. I preferiti sono separati dalle recensioni.":"Self-reported experiences, not certifications. One rating per user and version; you can update it. Favorites are separate from ratings."}</p>
  <label className="flex gap-2 text-sm"><input type="checkbox" checked={all} onChange={e=>{setAll(e.target.checked);setOffset(0);}}/>{it?"Mostra anche le altre versioni":"Include other versions"}</label>
  {!data&&!error&&<p>{it?"Caricamento…":"Loading…"}</p>}
  <ul className="space-y-3">{data?.items.map(item=><li key={item.id} className={`space-y-2 rounded border p-3 ${item.parent?"ml-3":""}`}>
   <p className="text-sm font-medium">{item.display_name}{item.author_reply?` · ${it?"Autore":"Publisher"}`:""} · v{item.version}{item.score?` · ★ ${item.score}/5`:""}</p>
   <p className="text-xs text-muted-foreground">{new Date(item.updated*1000).toLocaleString()}{item.parent?` · ${it?"Risposta":"Reply"}`:""}</p>
   {item.parent&&<blockquote className="border-l-2 pl-3 text-xs text-muted-foreground">{item.parent_excerpt??(it?"Commento originale non più disponibile":"Original comment no longer available")}</blockquote>}
   <p className="whitespace-pre-wrap break-words text-sm">{item.body}</p>
   <div className="flex flex-wrap gap-2">{!item.parent&&<button className={button} onClick={()=>{setReply(item);setScore("");}}>{it?"Rispondi":"Reply"}</button>}{item.mine?<><button disabled={busy} className={button} onClick={()=>void action(`${base}/feedback/${item.id}`,"DELETE")}>{it?"Elimina":"Delete"}</button>{item.score&&<button className={button} onClick={()=>{setReply(null);setReviewVersion(item.version);setScore(String(item.score));setBody(item.body);}}>{it?"Modifica recensione":"Edit review"}</button>}</>:<button className={button} onClick={()=>{setReport(item);setReason("");}}>{it?"Segnala":"Report"}</button>}</div>
  </li>)}</ul>
  {data&&data.total===0&&<p className="text-sm">{it?"Sii il primo a condividere la tua esperienza.":"Be the first to share your experience."}</p>}
  {data&&data.total>20&&<nav className="flex items-center gap-2"><button className={button} disabled={busy||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>{it?"Precedenti":"Previous"}</button><span>{offset+1}–{Math.min(offset+20,data.total)} / {data.total}</span><button className={button} disabled={busy||offset+20>=data.total} onClick={()=>setOffset(offset+20)}>{it?"Successivi":"Next"}</button></nav>}
  {report&&<form className="space-y-2 rounded border p-3" onSubmit={event=>{event.preventDefault();void action(`${base}/feedback/${report.id}/report`,"POST",{reason}).then(ok=>{if(ok)setReport(null);});}}><label className="block text-sm">{it?"Motivo della segnalazione":"Report reason"}<input required minLength={3} maxLength={1000} className="mt-1 w-full rounded border bg-background p-2" value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={busy} className={button}>{it?"Invia al moderatore":"Send to moderator"}</button><button type="button" className={button} onClick={()=>setReport(null)}>{it?"Annulla":"Cancel"}</button></form>}
  <form className="space-y-3 rounded border p-3" onSubmit={event=>{event.preventDefault();void action(path,"POST",{version:reply?.version??reviewVersion,body,score:reply||!score?null:Number(score),parent:reply?.id??null}).then(ok=>{if(ok){setBody("");setReply(null);if(reviewVersion!==version)setAll(true);}});}}>
   <h4 className="font-medium">{reply?(it?`Risposta a ${reply.display_name} · v${reply.version}`:`Reply to ${reply.display_name} · v${reply.version}`):(it?`La tua esperienza · v${reviewVersion}`:`Your experience · v${reviewVersion}`)}</h4>
   {!reply&&<label className="block text-sm">{it?"Versione provata":"Version tested"}<select aria-label={it?"Versione provata":"Version tested"} className="ml-2 rounded border bg-background p-2" value={reviewVersion} onChange={e=>{setReviewVersion(e.target.value);setScore("");setBody("");}}>{Array.from(new Set([version,...(data?.versions??[])])).map(v=><option key={v} value={v}>{v}</option>)}</select></label>}
   {reply?<><blockquote className="max-h-24 overflow-auto border-l-2 pl-3 text-sm">{reply.body}</blockquote><button type="button" className={button} onClick={()=>setReply(null)}>{it?"Annulla risposta":"Cancel reply"}</button></>:<label className="block text-sm">{it?"Valutazione":"Rating"}<select aria-label={it?"Valutazione":"Rating"} className="ml-2 rounded border bg-background p-2" value={score} onChange={e=>setScore(e.target.value)}><option value="">{it?"Solo commento":"Comment only"}</option>{[5,4,3,2,1].map(n=><option key={n} value={n}>{n} / 5</option>)}</select></label>}
   <textarea aria-label={it?"La tua esperienza":"Your experience"} required maxLength={4000} rows={3} className="w-full rounded border bg-background p-2" value={body} onChange={e=>setBody(e.target.value)} placeholder={it?"Per quale scopo lo hai usato? Cosa funziona e cosa miglioreresti?":"What did you use it for? What worked and what could improve?"}/>
   <button disabled={busy||!body.trim()} className={button}>{busy?(it?"Invio…":"Sending…"):(it?"Pubblica":"Post")}</button>
  </form>
  {error&&<p role="alert" className="rounded border p-3 text-sm">{error}</p>}
 </section>;
}

export function FeedbackModeration({base,locale}:{base:string;locale:string}){
 const [items,setItems]=useState<{id:string;pack:string;version:string;body:string;reports:number;reasons?:string}[]|null>(null),[error,setError]=useState(""),[reason,setReason]=useState("");
 const it=locale==="it";
 async function load(){const response=await fetch(base+"/feedback-reports");if(response.ok)setItems((await response.json()).items);else if(response.status!==403)throw Error("Moderation unavailable");}
 useEffect(()=>{void load().catch(e=>setError(String(e)));},[base]);
 if(items===null)return error?<p role="alert">{error}</p>:null;
 return <details className="rounded border p-3"><summary>{it?"Moderazione delle recensioni":"Review moderation"} ({items.length})</summary><p className="mt-2 text-sm">{it?"Solo amministratori. Le segnalazioni non nascondono automaticamente una recensione.":"Administrators only. Reports do not automatically hide a review."}</p><label className="block text-sm">{it?"Motivo della rimozione":"Reason for removal"}<input minLength={3} maxLength={1000} className="my-2 w-full rounded border bg-background p-2" value={reason} onChange={e=>setReason(e.target.value)}/></label>{items.map(item=><article className="my-2 space-y-2 rounded border p-3" key={item.id}><strong>{item.pack} · v{item.version} · {item.reports}</strong><p className="whitespace-pre-wrap text-sm">{item.body}</p><p className="whitespace-pre-wrap text-xs">{item.reasons}</p><button disabled={reason.trim().length<3} className={button} onClick={()=>{void fetch(`${base}/feedback/${item.id}/moderate`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({reason})}).then(async response=>{if(!response.ok)throw Error("Moderation failed");await load();}).catch(e=>setError(String(e)));}}>{it?"Nascondi":"Hide"}</button></article>)}{error&&<p role="alert">{error}</p>}</details>;
}
