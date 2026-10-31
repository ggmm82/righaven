"use client";

import Link from "next/link";

import { tr, useUiLanguage } from "@/core/i18n/ui-text";

import { setSettingsDialogOpen } from "./settings-dialog-store";

export function ModelSettingsPage() {useUiLanguage();
  return (
    <section className="space-y-4 p-4">
      <h2 className="text-lg font-semibold">{tr("Modelli del coordinatore e della squadra", "Coordinator and team models")}</h2>
      <p>
        {tr("Servizio, account e modello si configurano in RigHaven. Le impostazioni si possono applicare al coordinatore, alla squadra oppure a entrambi.", "Service, account and model are configured in RigHaven. The settings can apply to the coordinator, the team or both.")}
      </p>
      <Link
        onClick={() => setSettingsDialogOpen(false)}
        className="inline-block rounded-md bg-primary px-4 py-2 text-primary-foreground"
        href="/workspace/harness"
      >
        {tr("Configura la squadra →", "Configure the team →")}
      </Link>
    </section>
  );
}
