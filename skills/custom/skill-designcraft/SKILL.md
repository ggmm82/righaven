---
name: skill-designcraft
description: "Impaginazione multipagina, libri, riviste, fumetti e prestampa. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Impaginazione editoriale

Specialista: `designcraft` per `harness_delegate`; nome della skill: `skill-designcraft`.
CLI: `designcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Impaginazione multipagina, libri, riviste, fumetti e prestampa. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities designcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa DesignCraft per brochure, pubblicazioni multipagina e prestampa. Per testi strutturati DOCX usa WordCraft; per manipolare un PDF esistente usa PdfCraft.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help designcraft` e consulta `/opt/righaven/reference/designcraft/help.txt`.
3. Salva il registro reale con `craft commands designcraft > "$RIGHAVEN_OUTPUT_DIR/work/designcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools designcraft --out "$RIGHAVEN_OUTPUT_DIR/work/designcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch designcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Definisci formato finito, orientamento, margini, colonne, abbondanze e area sicura. Richiedi specifiche tipografiche quando PDF/X o profili CMYK sono vincoli di stampa.
2. Imposta pagine mastro e stili coerenti; collega immagini e testi verificati. Controlla font disponibili, risoluzione effettiva delle immagini e flusso del testo prima dell’export.
3. Risolvi overflow, righe isolate e immagini mancanti. Esporta separatamente PDF per schermo e stampa se richiesti, mantenendo il sorgente e le dipendenze.

## Diagnosi e recupero CLI

- Se un export taglia il testo, controlla overflow, font sostituiti, cornici e concatenamento delle pagine; ridurre tutto il corpo non è una correzione automatica accettabile.
- Se validate-pdf rifiuta il documento, conserva il rapporto e correggi il requisito specifico. Non cambiare il nome del file o la sola estensione per dichiarare PDF/X.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Renderizza tutte le pagine e controlla margini, allineamenti, numerazione e testo tagliato.
- Esegui il comando di registro `preflight.run` per i controlli editoriali. Per attestare PDF/X usa un validatore indipendente disponibile e registra il risultato; il profilo di export o un PDF apribile non dimostrano conformità.
- Consegna sorgente, PDF e rapporto di prestampa con font, abbondanze, immagini e limiti colore.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
designcraft-cli commands
designcraft-cli run --in input.designcraft --all-pages preview
designcraft-cli run --in input.designcraft --export output.pdf
designcraft-cli run --in input.designcraft --cmd 'preflight.run={}'
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.designcraft` con pagine, cornici, stili e collegamenti, oltre a PDF e anteprime. Riapri il progetto in una nuova sessione DesignCraft, controlla struttura e preflight e consegna le risorse esterne necessarie in un pacchetto provato dopo estrazione. Il PDF di stampa è un export, non il sorgente editoriale. Elenca font non redistribuibili, immagini mancanti o funzionalità perse senza allegare materiali di cui non è autorizzata la distribuzione.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/designcraft/tree/v0.12.0
- https://github.com/storytold/designcraft/releases

## Ruolo nella squadra

Impagina i testi verificati di WordCraft, i dati di GridCraft e gli asset di PhotoCraft/VectorCraft, conservando stili, font e collegamenti. Passa il PDF finale a PdfCraft quando serve controllo stampa o accessibilità.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
