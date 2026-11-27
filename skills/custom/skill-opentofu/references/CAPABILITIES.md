# Capacità operative: opentofu

Versione esaminata: **v1.13.10**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Validare infrastruttura dichiarativa e preparare un piano per la revisione.
**Sorgenti:** Moduli .tf, input di esempio, lock dei provider se generato e rapporti verificati.

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Validazione e piano di revisione | `fmt`, `init`, `validate`, `plan`, `show`, `providers` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Pianificare su un target remoto può usare credenziali e contattare il backend. La prova nativa usa solo una fixture locale senza provider esterni e non applica cambiamenti.

## Scoperta mirata

1. `craft capabilities opentofu`: selezione per obiettivo e confini.
2. `craft commands opentofu`: registro integrale; cerca soltanto gli ID pertinenti.
3. Usa `craft run opentofu -- <comando>` per eseguire la CLI.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 24 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `a585be803c3fa80f79996f9bda6bc33ffb08ca9c90bf05130f69f3781a8eb121`.
Fonte: https://github.com/opentofu/opentofu/tree/v1.13.10. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
