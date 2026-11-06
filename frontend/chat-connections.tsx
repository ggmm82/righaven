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
  <button type="button" className="rounded px-2 py-1 text-xs" disabled={disabled} onClick={()=>void show()} aria-label={tr("Connessioni utilizzabili","Usable connections")} data-testid="chat-connections-button">{tr("Connessioni","Connections")}{count?.thread===threadId&&count.value>0?` (${count.value})`:""}</button>
  {open&&<dialog ref={dialog} onCancel={close} onClose={close} aria-labelledby="chat-connections-title" className="bg-background text-foreground fixed inset-0 m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-xl overflow-y-auto rounded-xl border p-4 shadow-xl backdrop:bg-black/40">
   <header className="mb-3 flex items-center justify-between gap-3"><h3 id="chat-connections-title" className="font-semibold">{tr("Connessioni della conversazione","Conversation connections")}</h3><button type="button" className="rounded border px-3 py-1" onClick={close}>{tr("Chiudi","Close")}</button></header>
   <p className="mb-3 text-sm">{tr("Facoltative, anche senza ricetta. Seleziona solo gli accessi necessari al lavoro; file e competenze si scelgono separatamente.","Optional, including without a recipe. Select only access needed for the task; files and skills are selected separately.")}</p>
   {panel.error?<p role="alert">{panel.error}</p>:panel.ready?<ProjectConnections threadId={threadId} expanded onAssigned={ids=>setCount({thread:threadId,value:ids.length})}/>:<p role="status">{tr("Apertura della conversazione…","Opening the conversation…")}</p>}
  </dialog>}
 </>;
}
