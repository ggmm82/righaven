---
name: skill-cadcraft
description: "Disegno tecnico, quote, blocchi, geometrie CAD e tavole di progetto. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Disegno CAD

Specialista: `cadcraft` per `harness_delegate`; nome della skill: `skill-cadcraft`.
CLI: `cadcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Disegno tecnico, quote, blocchi, geometrie CAD e tavole di progetto. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities cadcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa CADCraft per disegno tecnico, geometrie, layer, quote e DXF. Una rappresentazione grafica non sostituisce la verifica delle dimensioni.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help cadcraft` e consulta `/opt/righaven/reference/cadcraft/help.txt`.
3. Salva il registro reale con `craft commands cadcraft > "$RIGHAVEN_OUTPUT_DIR/work/cadcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools cadcraft --out "$RIGHAVEN_OUTPUT_DIR/work/cadcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch cadcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Definisci unità, scala, origine, sistema di coordinate e tolleranze. Se mancano misure essenziali non inventarle: esplicita le assunzioni o segnala il blocco.
2. Organizza layer e geometrie; verifica chiusura dei contorni, intersezioni, duplicati e coerenza delle quote. Distingui unità del modello e scala di stampa.
3. Misura entità e ingombri numericamente prima dell’export. Conserva geometria editabile e controlla le entità supportate dal formato di scambio.

## Diagnosi e recupero CLI

- Se le dimensioni differiscono, controlla unità del disegno, fattore di conversione e scala di stampa separatamente. Misura numericamente il DXF riaperto, senza inferire distanze dai pixel.
- Se un contorno non è chiuso, individua vertici estremi, tolleranze e duplicati; non unire automaticamente geometrie che cambiano misure o vincoli del brief.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri DXF e confronta unità, bounding box, conteggio entità e distanze campione con i requisiti e le tolleranze.
- Genera un’anteprima con quote leggibili, verificando scala e orientamento; la sola anteprima non prova accuratezza metrica.
- Consegna disegno sorgente, DXF e riepilogo delle misure; segnala spline, quote o layer persi in conversione.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
cadcraft-cli commands
cadcraft-cli info input.dxf
cadcraft-cli convert input.dxf output.svg
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il disegno DXF modificabile verificato con CADCraft, conservando layer, entità, unità e quote realmente supportate; DXF è il formato operativo verificato, non inventare un’estensione proprietaria. Riaprilo con `cadcraft-cli info` e una nuova sessione `cadcraft-cli run`, poi confronta entità e misure. Un GLB/GLTF o un viewer HTML è un export 3D, non la prova di un documento apribile in CADCraft. La ricetta collaudata copre DXF 2D: non promettere import GLB o modellazione parametrica/3D senza verificarli nella release reale. Se il brief richiede 3D e il registro non lo supporta, dichiara il limite al coordinatore; non sostituire il modello richiesto con una sagoma 2D, non rinominare GLB in DXF e non usare la sola validazione GLB come verifica CADCraft.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/cadcraft/tree/v0.12.0
- https://github.com/storytold/cadcraft/releases

## Ruolo nella squadra

Crea geometrie, layer e quote nel formato CAD realmente supportato. Passa viste o geometrie misurate agli altri ruoli solo quando richieste. Non presentarti come modellatore di personaggi 3D o sistema di rigging se la CLI installata non supporta il requisito; un GLB creato con uno script non prova compatibilità CADCraft.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.

## Scelta rispetto a FreeCAD

Per tavole e disegno 2D in DXF resta pertinente CADCraft. Per solidi 3D parametrici con quote modificabili, ricalcolo e sorgente `.FCStd`, valuta la skill `skill-freecad`. Non usare entrambe per principio: sceglile dai requisiti e conserva il sorgente dell’app realmente usata. STEP/GLB/DXF di scambio non ricostruiscono automaticamente l’albero parametrico. Per rendering e animazione valuta Blender.
