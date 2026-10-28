---
name: skill-deckcraft
description: "Presentazioni editabili, sistemi di slide, diagrammi, media e animazioni. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Presentazioni

Specialista: `deckcraft` per `harness_delegate`; nome della skill: `skill-deckcraft`.
CLI: `deckcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Presentazioni editabili, sistemi di slide, diagrammi, media e animazioni. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities deckcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa DeckCraft per presentazioni e PPTX. Analisi numerica e riconciliazione dei dati appartengono a GridCraft; loghi e illustrazioni a VectorCraft.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help deckcraft` e consulta `/opt/righaven/reference/deckcraft/help.txt`.
3. Salva il registro reale con `craft commands deckcraft > "$RIGHAVEN_OUTPUT_DIR/work/deckcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools deckcraft --out "$RIGHAVEN_OUTPUT_DIR/work/deckcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch deckcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Definisci pubblico, messaggio, durata, numero indicativo di slide e formato. Prepara una scaletta con un messaggio verificabile per slide e usa solo metriche e asset forniti o controllati.
2. Imposta griglia, gerarchia tipografica e palette coerenti. Crea grafici editabili quando supportati; registra fonte, unità, periodo e denominatore. Non trasformare tutte le slide in immagini se serve PPTX modificabile.
3. Mantieni testi brevi e leggibili, allineamenti e margini regolari. Usa note per dettagli e fonti; controlla font disponibili e contrasto. Non alterare numeri per adattarli alla narrazione.

## Diagnosi e recupero CLI

- Se un grafico non è modificabile, verifica il tipo di oggetto e i dati incorporati nel file finale; una bitmap con etichette non soddisfa il requisito di grafico editabile.
- Se l’export differisce dal render sorgente, controlla font e capacità PPTX della release. Verifica tutte le slide dopo la conversione e registra gli elementi rasterizzati.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri PPTX, controlla numero e ordine slide e confronta tutti i numeri con i dati di origine.
- Renderizza tutte le slide: controlla sovrapposizioni, testi tagliati, etichette, contrasto e leggibilità alla risoluzione finale.
- Consegna sorgente, PPTX e anteprime di tutte le slide; dichiara elementi rasterizzati, font sostituiti e limiti di animazioni.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
deckcraft-cli commands
deckcraft-cli info input.pptx
deckcraft-cli render input.pptx --all preview
deckcraft-cli convert input.deckcraft output.pptx
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.deckcraft` e il PPTX richiesto, oltre a PDF o anteprime se utili. Riapri il sorgente con DeckCraft e verifica slide, testi, forme e immagini modificabili; verifica separatamente il PPTX se consegnato, senza dedurne la compatibilità dal sorgente. Non presentare slide rasterizzate come testo/grafici modificabili. Includi media collegati necessari e dichiara font, animazioni o elementi persi in export.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/deckcraft/tree/v0.10.0
- https://github.com/storytold/deckcraft/releases

## Ruolo nella squadra

Assembla una presentazione coerente dai dati di GridCraft, testi di WordCraft e asset di PhotoCraft/VectorCraft. Conserva oggetti, grafici e testo modificabili nel PPTX; verifica slide e font dopo l’integrazione.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
