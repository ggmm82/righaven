---
name: skill-vectorcraft
description: "Illustrazione vettoriale, loghi, icone, lettering e diagrammi modificabili. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Grafica vettoriale

Specialista: `vectorcraft` per `harness_delegate`; nome della skill: `skill-vectorcraft`.
CLI: `vectorcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Illustrazione vettoriale, loghi, icone, lettering e diagrammi modificabili. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities vectorcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa VectorCraft per loghi, icone, illustrazioni e tracciati scalabili. Il ritocco fotografico appartiene a PhotoCraft; componenti UI e prototipi a FigCraft.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Creazione da zero: percorso rapido

Per illustrazioni nuove composte da forme, tracciati, gruppi e gradienti puoi scrivere un SVG XML originale con Python o heredoc come input. Non è un export binario fittizio: importalo subito con `vectorcraft-cli convert` nel sorgente `.vectorcraft`, poi usa la CLI per SVG finale e PNG. Evita di tradurre ogni singola forma in decine di chiamate MCP quando non devi modificare un documento preesistente. La ricetta contiene il flusso verificato. Realizza prima il soggetto completo, poi le verifiche; non fermarti a un rettangolo di prova.

Questa tecnica di authoring non è una garanzia di qualità figurativa. Per soggetti complessi verifica composizione, pose, proporzioni e riferimenti prima di moltiplicare tracciati e dettagli. Se il campione resta insufficiente, comunica il limite del metodo concreto e una diversa costruzione praticabile; non dedurre l'impossibilità dell'illustrazione o la necessità di asset esterni dal solo insuccesso di coordinate SVG generate. Uno stile scelto dalla squadra può essere rivalutato mantenendo qualità e contenuto richiesti; uno stile imposto dall'utente richiede il suo accordo per essere cambiato.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help vectorcraft` e consulta `/opt/righaven/reference/vectorcraft/help.txt`.
3. Salva il registro reale con `craft commands vectorcraft > "$RIGHAVEN_OUTPUT_DIR/work/vectorcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools vectorcraft --out "$RIGHAVEN_OUTPUT_DIR/work/vectorcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch vectorcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Definisci tavole, unità, viewBox, palette e ingombro finale. Per icone considera anche una versione alla dimensione minima richiesta.
2. Organizza gruppi e livelli con nomi; mantieni tracciati e testo modificabili. Usa geometrie coerenti, allineamenti e spessori controllati; evita immagini raster incorporate quando il requisito è vettoriale.
3. Conserva una copia con testo editabile prima di convertire caratteri in tracciati. Verifica font e licenze degli asset forniti; non sostituire silenziosamente il marchio.

## Diagnosi e recupero CLI

- Se un elemento scompare, controlla viewBox, trasformazioni dei gruppi, clipping e ordine degli oggetti prima di ricrearlo.
- Se il testo cambia dimensione o posizione, verifica il font installato e le metriche prima di convertirlo in tracciati. Mantieni anche una copia con testo modificabile.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri SVG/PDF e controlla viewBox, clipping, proporzioni e presenza di bitmap inattese.
- Renderizza su sfondo chiaro e scuro se è previsto alpha; verifica i tratti e la leggibilità alla dimensione d’uso.
- Consegna sorgente, SVG e varianti richieste; segnala font sostituiti, testo convertito e limiti dell’export.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
vectorcraft-cli commands
vectorcraft-cli run --in input.vectorcraft --export output.pdf
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.vectorcraft` insieme a SVG/PDF/PNG richiesti. Riapri il progetto e verifica oggetti, gruppi, tracciati e testo; per SVG controlla che il testo da modificare non sia stato convertito in contorni e che non sia una sola bitmap incorporata. Distingui sorgente nativo e formato di scambio; segnala font, immagini collegate e caratteristiche non conservate.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/vectorcraft/tree/v0.16.0
- https://github.com/storytold/vectorcraft/releases

## Ruolo nella squadra

Prepara loghi, icone e illustrazioni SVG con gruppi e tracciati modificabili; passa asset con dimensioni/viewBox e font esplicitati a PhotoCraft, DesignCraft, DeckCraft, FigCraft o EffectCraft.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
