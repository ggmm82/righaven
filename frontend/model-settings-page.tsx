"use client";

import Link from "next/link";

import { setSettingsDialogOpen } from "./settings-dialog-store";

export function ModelSettingsPage() {
  return (
    <section className="space-y-4 p-4">
      <h2 className="text-lg font-semibold">Modelli del coordinatore e della squadra</h2>
      <p>
        Servizio, account e modello si configurano in RigHaven. Le
        impostazioni si possono applicare al coordinatore, alla squadra oppure a entrambi.
      </p>
      <Link
        onClick={() => setSettingsDialogOpen(false)}
        className="inline-block rounded-md bg-primary px-4 py-2 text-primary-foreground"
        href="/workspace/harness"
      >
        Configura la squadra →
      </Link>
    </section>
  );
}
