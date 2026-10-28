---
name: skill-photocraft
description: "Ritocco, compositing raster e texture con livelli e maschere. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Immagini e ritocco

Specialista: `photocraft` per `harness_delegate`; nome della skill: `skill-photocraft`.
CLI: `photocraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Ritocco, compositing raster e texture con livelli e maschere. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities photocraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa PhotoCraft per ritocco raster, livelli, maschere e compositing. Per lo sviluppo RAW usa LightCraft; per loghi scalabili usa VectorCraft.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help photocraft` e consulta `/opt/righaven/reference/photocraft/help.txt`.
3. Salva il registro reale con `craft commands photocraft > "$RIGHAVEN_OUTPUT_DIR/work/photocraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools photocraft --out "$RIGHAVEN_OUTPUT_DIR/work/photocraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch photocraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Rileva dimensioni in pixel, orientamento EXIF, profilo colore, profondità, alpha e struttura dei livelli. Chiarisci il formato e la risoluzione di consegna; non confondere DPI e numero di pixel.
2. Duplica il documento e mantieni livelli nominati, maschere modificabili e originale intatto. Applica correzioni su un campione prima di operazioni estese; evita ricampionamenti ripetuti.
3. Esporta una copia nel profilo richiesto. Per JPEG scegli uno sfondo esplicito; per PNG controlla trasparenza e bordi. Non promettere funzioni PSD che la release non conserva.

## Diagnosi e recupero CLI

- Se un filtro non produce l’effetto atteso, verifica livello attivo, selezione, maschera e visibilità prima di ripeterlo. Non applicare lo stesso filtro due volte alla cieca.
- Se l’export perde alpha o livelli, confronta capacità del formato e modalità di esportazione nel registro. Conserva il progetto e dichiara l’eventuale appiattimento.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri sorgente ed export e confronta dimensioni, livelli e alpha attesi.
- Genera anteprima complessiva e dettagli al 100% di bordi, maschere e ritocchi; registra se non puoi ispezionarli visivamente.
- Consegna sorgente con livelli, immagine finale e anteprime; dichiara eventuali livelli appiattiti o variazioni del profilo.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
photocraft-cli info input.psd
photocraft-cli commands --filter blur
photocraft-cli convert input.psd output.png
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.pcraft` e gli export richiesti (per esempio PNG/JPEG); PSD è una consegna distinta da verificare se richiesta. Riapri il progetto con PhotoCraft e controlla livelli, maschere, visibilità, dimensioni e risorse. Dichiara quali elementi sono separatamente modificabili: un’immagine appiattita inserita in un progetto o in PSD non recupera livelli, parti del soggetto o effetti procedurali. Non presentare il PNG come sorgente a livelli.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/photocraft/tree/v0.15.1
- https://github.com/storytold/photocraft/releases

## Ruolo nella squadra

Prepara identità visiva, immagini, texture, sfondi e parti separate a livelli. Concorda dimensioni, alpha e palette con VectorCraft/EffectCraft/FilmCraft. Non sostituire animazione, suono e montaggio con un solo export immagine.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Prova completa e revisioni mirate

Prima di produrre tutti gli asset, prepara una prova riconoscibile del soggetto e della palette. Conserva separazione delle parti utili; verifica che il risultato sia leggibile nel prodotto, non soltanto che i PNG esistano.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
