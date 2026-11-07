"use client";
import {useEffect,useRef,useState} from "react";

import {ProjectConnections} from "@/components/workspace/messages/project-connections";
import {fetch} from "@/core/api/fetcher";
import {getBackendBaseURL} from "@/core/config";
import {tr,useUiLanguage} from "@/core/i18n/ui-text";
import {createThread} from "@/core/threads/api";

/** Prepare a native thread on demand, so connections can be selected before its first plan/message. */
export function ChatConnections({threadId,disabled,prepare}:{threadId:string;disabled:boolean;prepare?:()=>void|Promise<void>}){
 useUiLanguage();
 const [panel,setPanel]=useState<{thread:string;ready:boolean;error:string}|null>(null);
 const [count,setCount]=useState<{thread:string;value:number}|null>(null);
 const dialog=useRef<HTMLDialogElement>(null),owner=useRef(threadId),sequence=useRef(0);
 owner.current=threadId;
 const open=panel?.thread===threadId;
 useEffect(()=>{if(open&&!dialog.current?.open)dialog.current?.showModal();},[open]);
 const close=()=>{sequence.current++;setPanel(null);};
 // A write to a device asked in this chat waits for the owner: say so on the button and open the
 // panel with the approval the first time it appears, instead of leaving it behind «Connections».
 const [pending,setPending]=useState<{thread:string;ids:string[]}>({thread:threadId,ids:[]});
 const announced=useRef<Set<string>>(new Set());
 useEffect(()=>{if(disabled)return;let live=true;
  const load=()=>void fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/device-changes`).then(r=>r.ok?r.json() as Promise<{changes:{id:string;status:string}[]}>:{changes:[]})
   .then(v=>{if(!live)return;const ids=v.changes.filter(c=>c.status==="pending").map(c=>c.id);setPending({thread:threadId,ids});
    if(ids.some(id=>!announced.current.has(id))){ids.forEach(id=>announced.current.add(id));if(!dialog.current?.open)void show();}})
   .catch(()=>undefined);
  load();const timer=setInterval(load,8000);return()=>{live=false;clearInterval(timer);};
 // eslint-disable-next-line react-hooks/exhaustive-deps -- show() is stable for this thread
 },[threadId,disabled]);
 const waiting=pending.thread===threadId?pending.ids.length:0;
 async function show(){if(disabled)return;const request=++sequence.current;setPanel({thread:threadId,ready:false,error:""});
  try{await prepare?.();
   // The native project callback is a no-op for an ordinary blank chat.
   // Materialize only a missing thread, preserving existing project membership
   // and allowing existing-thread writers without thread-create permission.
   const response=await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/harness-connections`);
   if(response.status===404)await createThread(threadId);
   else if(!response.ok)throw Error(String(response.status));
   if(owner.current===threadId&&sequence.current===request)setPanel({thread:threadId,ready:true,error:""});
  }
  catch(e){if(owner.current===threadId&&sequence.current===request)setPanel({thread:threadId,ready:false,error:e instanceof Error?e.message:String(e)});}
 }
 return <>
  <button type="button" className="rounded px-2 py-1 text-xs" disabled={disabled} onClick={()=>void show()} aria-label={tr("Connessioni utilizzabili","Usable connections")} data-testid="chat-connections-button">{tr("Connessioni","Connections")}{count?.thread===threadId&&count.value>0?` (${count.value})`:""}{waiting>0&&<strong className="ml-1 rounded bg-amber-600 px-1 text-white" data-testid="chat-connections-pending">{waiting} {tr("da approvare","to approve")}</strong>}</button>
  {open&&<dialog ref={dialog} onCancel={close} onClose={close} aria-labelledby="chat-connections-title" className="bg-background text-foreground fixed inset-0 m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-xl overflow-y-auto rounded-xl border p-4 shadow-xl backdrop:bg-black/40">
   <header className="mb-3 flex items-center justify-between gap-3"><h3 id="chat-connections-title" className="font-semibold">{tr("Connessioni della conversazione","Conversation connections")}</h3><button type="button" className="rounded border px-3 py-1" onClick={close}>{tr("Chiudi","Close")}</button></header>
   <p className="mb-3 text-sm">{tr("Facoltative, anche senza ricetta. Seleziona solo gli accessi necessari al lavoro; file e competenze si scelgono separatamente.","Optional, including without a recipe. Select only access needed for the task; files and skills are selected separately.")}</p>
   {panel.error?<p role="alert">{panel.error}</p>:panel.ready?<ProjectConnections threadId={threadId} expanded onAssigned={ids=>setCount({thread:threadId,value:ids.length})}/>:<p role="status">{tr("Apertura della conversazione…","Opening the conversation…")}</p>}
  </dialog>}
 </>;
}
