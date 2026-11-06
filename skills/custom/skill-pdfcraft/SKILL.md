---
name: skill-pdfcraft
description: "Ispezione e modifica PDF, pagine, testo, moduli, OCR e prestampa. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Documenti PDF

Specialista: `pdfcraft` per `harness_delegate`; nome della skill: `skill-pdfcraft`.
CLI: `pdfcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Ispezione e modifica PDF, pagine, testo, moduli, OCR e prestampa. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities pdfcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa PdfCraft per ispezione, estrazione, unione, pagine e moduli PDF. Per riscrivere un documento usa WordCraft; per impaginazione da stampa usa DesignCraft.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help pdfcraft` e consulta `/opt/righaven/reference/pdfcraft/help.txt`.
3. Salva il registro reale con `craft commands pdfcraft > "$RIGHAVEN_OUTPUT_DIR/work/pdfcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools pdfcraft --out "$RIGHAVEN_OUTPUT_DIR/work/pdfcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch pdfcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Rileva pagine, ordine, rotazione, dimensioni, testo, moduli, allegati, restrizioni e firme. Distingui PDF testuale e scansione; non inventare testo quando serve OCR non disponibile.
2. Esegui modifiche su una copia; mantieni una mappa delle pagine prima/dopo. Per moduli distingui valori compilati e campi interattivi; avvisa se una modifica invalida firme o appiattisce campi.
3. Per oscuramenti permanenti controlla che il contenuto sia rimosso da testo e oggetti: un rettangolo nero non basta. Non attestare redazione sicura se la release o i controlli non lo consentono.

## Diagnosi e recupero CLI

- Se il testo estratto è vuoto, verifica la presenza di pagine raster prima di dichiarare il PDF privo di contenuto. Distingui estrazione e OCR.
- Per un oscuramento ricontrolla il testo estratto e gli oggetti anche dopo aver riaperto il file finale; se il dato è recuperabile, il controllo è fallito anche con anteprima nera.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri il PDF, verifica conteggio/ordine pagine e valori dei campi; estrai il testo per confrontare i contenuti attesi.
- Renderizza tutte le pagine modificate e controlla tagli, rotazioni e leggibilità.
- Consegna PDF e rapporto con pagine coinvolte, controlli, firme/moduli alterati e limiti OCR o redazione.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
pdfcraft-cli info input.pdf
pdfcraft-cli tools
pdfcraft-cli combine input.pdf appendix.pdf --out output.pdf
pdfcraft-cli text output.pdf
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il PDF risultante, riaperto con PdfCraft, precisando quali operazioni restano possibili (pagine, annotazioni, moduli o testo secondo la release e il file). Se il lavoro parte da un documento Word, slide o impaginato creato dalla squadra, includi anche quel sorgente tramite lo specialista che lo ha prodotto. Un PDF è modificabile nei limiti di PdfCraft ma non equivale al progetto editoriale originale: non promettere stili Word, formule, livelli o font che non sono stati conservati. Per PDF scansionati o appiattiti dichiara espressamente i limiti.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/pdfcraft/tree/v0.13.0
- https://github.com/storytold/pdfcraft/releases

## Ruolo nella squadra

Ispeziona il PDF effettivamente esportato da WordCraft, DesignCraft o DeckCraft: pagine, testo, font, link e difetti di stampa/accessibilità pertinenti. Correggi il PDF senza dichiararlo sorgente dell’impaginazione originale.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
