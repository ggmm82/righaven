"use client";
import Link from "next/link";
import {useI18n} from "@/core/i18n/hooks";
import {AgentGallery} from "@/components/workspace/agents/agent-gallery";
export default function AgentsPage(){
 const {locale}=useI18n();const it=locale==="it-IT";
 return <><section className="mx-auto max-w-6xl px-6 pt-6"><p className="rounded-xl border p-4 text-sm">{it?"Editor avanzato degli stessi profili mostrati in Ambienti: non è una seconda squadra. Ogni profilo conserva scopo, istruzioni e skill; i programmi e la preparazione si gestiscono in Ambienti. I ruoli della squadra sono definiti dinamicamente nella chat di progetto.":"Advanced editor for the same profiles shown in Environments: this is not a second team. Each profile stores purpose, instructions and skills; software and preparation are managed in Environments. Team roles are defined dynamically in each project chat."} <Link className="underline" href="/workspace/environments">{it?"Gestisci ambienti":"Manage environments"}</Link> <Link className="underline" href="/workspace/chats/new">{it?"Nuovo progetto":"New project"}</Link></p></section><AgentGallery/></>;
}
