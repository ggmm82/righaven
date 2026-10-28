---
name: skill-figcraft
description: "Design di interfacce, componenti, layout adattivi e prototipi. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Interfacce e prototipi

Specialista: `figcraft` per `harness_delegate`; nome della skill: `skill-figcraft`.
CLI: `figcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Design di interfacce, componenti, layout adattivi e prototipi. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities figcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa FigCraft per layout UI, componenti e prototipi. Per illustrazioni e loghi usa VectorCraft; un prototipo non equivale a un sito funzionante.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help figcraft` e consulta `/opt/righaven/reference/figcraft/help.txt`.
3. Salva il registro reale con `craft commands figcraft > "$RIGHAVEN_OUTPUT_DIR/work/figcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools figcraft --out "$RIGHAVEN_OUTPUT_DIR/work/figcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch figcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Definisci utenti, flussi, viewport desktop/mobile e contenuti reali. Inventaria frame, componenti, variabili e asset del file esistente.
2. Crea griglia, spaziature e token coerenti; usa componenti riutilizzabili e vincoli/auto layout supportati. Prevedi stati default, hover/focus, errore, vuoto e caricamento quando pertinenti.
3. Verifica testi lunghi, adattamento ai viewport e contrasto; collega i passaggi del prototipo richiesti. Non attestare conformità di accessibilità senza controlli specifici.

## Diagnosi e recupero CLI

- Se il layout non si adatta, verifica i vincoli e l’auto layout realmente disponibili nello schema. Una seconda immagine ridimensionata non dimostra un’interfaccia responsive.
- Se un prototipo non naviga, verifica ID di frame destinazione e collegamenti dopo la riapertura del sorgente; immagini e SVG non conservano necessariamente le interazioni.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri il sorgente e verifica struttura di frame/componenti, variabili e collegamenti del prototipo.
- Renderizza ogni viewport e stato rilevante; controlla overflow, dimensioni dei bersagli e contrasto misurato.
- Consegna sorgente editabile e anteprime con specifiche; dichiara i limiti dell’export .fig, delle interazioni e della resa responsive.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
figcraft-cli commands --json
figcraft-cli info input.figcraft --json
figcraft-cli render input.figcraft -o preview.png --scale 2
figcraft-cli export input.figcraft -o exports --format svg
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.figcraft` con frame, nodi, gerarchie, testo e componenti realmente presenti, insieme agli export PNG/SVG richiesti. Riapri il file con `open_file` e `inspect_document` in una nuova sessione FigCraft e verifica testo e gerarchie. `.fig` è un export sperimentale distinto: non garantirne l’apertura in Figma o FigCraft senza una prova nella destinazione reale. Un PNG o un mockup appiattito non è un’interfaccia modificabile per componenti.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/figcraft/tree/v0.10.0
- https://github.com/storytold/figcraft/releases

## Ruolo nella squadra

Progetta UI e prototipi con componenti, varianti e stili, usando gli asset di PhotoCraft/VectorCraft e i contenuti/dati dei colleghi. Verifica frame, collegamenti e risorse del progetto modificabile; non confondere un PNG con un prototipo funzionante.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
