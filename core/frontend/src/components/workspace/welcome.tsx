"use client";
import { useSearchParams } from "next/navigation";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

export function Welcome({className}: {className?: string; mode?: "ultra" | "pro" | "thinking" | "flash"}) {
  const { locale, t } = useI18n();
  const it = locale === "it-IT";
  const skill = useSearchParams().get("mode") === "skill";
  return <div className={cn("mx-auto w-full max-w-2xl space-y-4 px-6 py-8",className)}>
    <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">RigHaven / {skill ? "Skills" : it ? "Nuovo incarico" : "New task"}</p>
    <h1 className="text-3xl font-semibold tracking-tight">{skill ? t.welcome.createYourOwnSkill : it ? "Cosa vuoi realizzare?" : "What would you like to achieve?"}</h1>
    <p className="text-sm leading-relaxed text-muted-foreground">{skill ? t.welcome.createYourOwnSkillDescription : it ? "Descrivi il risultato atteso, a chi serve e in quale formato. Puoi allegare riferimenti o sorgenti. La squadra definirà le attività e gli strumenti per raggiungere l’obiettivo." : "Describe the outcome, who it is for and the delivery format. Attach references or sources if you have them. Your team will define the tasks and tools needed to reach your goal."}</p>
  </div>;
}
