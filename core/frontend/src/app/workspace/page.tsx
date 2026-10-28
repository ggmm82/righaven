"use client";

import Link from "next/link";
import { ArrowUpRight, Layers, Wrench, Library, Plus, Folder } from "lucide-react";
import { useI18n } from "@/core/i18n/hooks";
import { useProjects } from "@/core/projects/hooks";
import { useAuth } from "@/core/auth/AuthProvider";

export default function WorkspacePage() {
  const { locale } = useI18n();
  const { user } = useAuth();
  const it = locale === "it-IT";
  const projects = useProjects("active");
  const cards = [
    { href: "/workspace/environments", icon: Layers, title: it ? "Ambienti" : "Environments", text: it ? "Prepara solo i programmi necessari. Controlla disponibilità e lavori in corso." : "Prepare only the software you need. Check availability and active work." },
    { href: "/workspace/capabilities", icon: Wrench, title: it ? "Strumenti e skill" : "Tools & skills", text: it ? "Scegli gli strumenti disponibili e le istruzioni che potenziano la squadra." : "Choose the tools and instructions available to your team." },
    { href: "/workspace/gallery", icon: Library, title: "Community Gallery", text: it ? "Aggiungi configurazioni di ambienti e skill condivise dalla community." : "Add environment configurations and skills shared by the community." },
  ];
  return <main className="flex-1 overflow-y-auto bg-muted/20">
    <div className="mx-auto max-w-6xl space-y-10 p-6 md:p-10">
      <header className="flex flex-wrap items-start justify-between gap-6 border-b pb-8">
        <div className="max-w-xl space-y-3"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">RigHaven / Workspace</p>
          <h1 className="text-3xl font-semibold tracking-tight md:text-4xl">{it ? "Dall’obiettivo al risultato." : "From objective to outcome."}</h1>
          <p className="text-muted-foreground">{it ? "Descrivi cosa vuoi ottenere. La squadra organizza ruoli e attività e richiama gli strumenti necessari." : "Describe what you want to achieve. Your team organizes roles and tasks, bringing in the tools it needs."}</p>
        </div>
        <Link href="/workspace/chats/new" className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-medium text-primary-foreground"><Plus className="size-4" />{it ? "Nuovo incarico" : "New task"}</Link>
      </header>
      <section aria-label={it ? "Come iniziare" : "Getting started"} className="grid gap-5 rounded-2xl border bg-background p-6 md:grid-cols-3">
        {[it ? "1. Definisci obiettivo, formato e vincoli." : "1. Define the objective, format and constraints.", it ? "2. Segui la squadra e rispondi alle scelte aperte." : "2. Follow your team and resolve open decisions.", it ? "3. Verifica risultati, sorgenti e lezioni riutilizzabili." : "3. Review results, sources and reusable lessons."].map(text => <p key={text} className="text-sm leading-relaxed">{text}</p>)}
      </section>
      <section className="space-y-4"><h2 className="text-xl font-semibold">{it ? "Progetti" : "Projects"}</h2>
        {projects.isLoading ? <p role="status">{it ? "Caricamento…" : "Loading…"}</p> : projects.isError ? <div role="alert"><p>{it ? "Non è stato possibile leggere i progetti." : "Projects could not be loaded."}</p><button className="underline" onClick={() => void projects.refetch()}>{it ? "Riprova" : "Retry"}</button></div> : projects.data?.length ? <div className="grid gap-3 md:grid-cols-2">{projects.data.map(project => <Link key={project.id} href={`/workspace/projects/${project.id}`} className="flex items-center gap-3 rounded-xl border bg-background p-5 hover:border-primary"><Folder className="size-5 text-muted-foreground" /><span className="truncate font-medium">{project.name}</span><ArrowUpRight className="ml-auto size-4" /></Link>)}</div> : <div className="rounded-xl border border-dashed p-6"><p className="text-muted-foreground">{it ? "Nessun progetto. Inizia con un incarico; usa i progetti nella barra laterale per raggruppare attività e documenti." : "No projects yet. Start a task; use Projects in the sidebar to group tasks and documents."}</p></div>}
      </section>
      <section className="space-y-4"><h2 className="text-xl font-semibold">{it ? "Prepara la tua cassetta degli attrezzi" : "Build your toolbox"}</h2><div className="grid gap-4 md:grid-cols-3">{cards.map(({href,icon:Icon,title,text}) => <Link key={href} href={href} className="group space-y-4 rounded-2xl border bg-background p-6 transition-colors hover:border-primary"><Icon className="size-6" /><h3 className="flex items-center justify-between font-semibold">{title}<ArrowUpRight className="size-4 text-muted-foreground" /></h3><p className="text-sm leading-relaxed text-muted-foreground">{text}</p></Link>)}</div></section>
      <footer className="flex flex-wrap items-center justify-between gap-3 border-t pt-5 text-sm text-muted-foreground"><span>{user?.email}</span><Link href="/workspace/cloud" className="underline">{it ? "Informazioni sull’installazione" : "Deployment information"}</Link></footer>
    </div>
  </main>;
}
