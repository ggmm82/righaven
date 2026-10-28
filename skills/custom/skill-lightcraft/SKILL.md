---
name: skill-lightcraft
description: "Sviluppo fotografico/RAW, catalogazione, correzioni locali e serie coerenti. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Fotografia e RAW

Specialista: `lightcraft` per `harness_delegate`; nome della skill: `skill-lightcraft`.
CLI: `lightcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Sviluppo fotografico/RAW, catalogazione, correzioni locali e serie coerenti. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities lightcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa LightCraft per sviluppo fotografico RAW, esposizione, colore e serie di foto. Per maschere e compositing con molti livelli usa PhotoCraft.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help lightcraft` e consulta `/opt/righaven/reference/lightcraft/help.txt`.
3. Salva il registro reale con `craft commands lightcraft > "$RIGHAVEN_OUTPUT_DIR/work/lightcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools lightcraft --out "$RIGHAVEN_OUTPUT_DIR/work/lightcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch lightcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Inventaria originali, metadati, orientamento, profilo e sidecar. Non modificare o spostare i RAW originali. Definisci destinazione, spazio colore, dimensioni e convenzione dei nomi.
2. Sviluppa un’immagine rappresentativa: bilanciamento del bianco, esposizione, recupero luci, ombre e contrasto. Controlla istogramma e clipping prima di sincronizzare le impostazioni.
3. Dividi la serie per condizioni di luce quando necessario. Verifica campioni scuri e chiari; non applicare automaticamente la stessa esposizione a tutta la raccolta. Conserva ricetta/sidecar modificabili se supportati.

## Diagnosi e recupero CLI

- Se una serie produce risultati diversi, raggruppa gli input per profilo, orientamento e luce e verifica una ricetta per gruppo; non correggere sovrascrivendo RAW o sidecar originali.
- Se un RAW non è supportato, registra il formato e l’errore; non spacciare un JPEG incorporato per sviluppo del RAW. Verifica la reale capacità della release prima del lavoro in serie.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Confronta conteggio input/output e segnala gli scarti; riapri gli export e controlla risoluzione, orientamento e profilo colore.
- Confronta campioni prima/dopo per alte luci, ombre e dominanti. Dichiara ogni controllo visivo non eseguito.
- Consegna export, ricette disponibili e rapporto delle impostazioni senza includere falsi RAW modificabili.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
lightcraft-cli commands --json
lightcraft-cli render input.jpg -o output.jpg --set light.exposure=0.5
```

## Consegna: sorgenti modificabili e compatibilità

Consegna gli export e i materiali per riprendere lo sviluppo: copie degli originali necessari, ricetta eseguibile con i parametri realmente usati e sidecar/catalogo soltanto se la release ne supporta salvataggio e riapertura. Se usi un pacchetto originali+ricetta, dichiaralo come sorgente riproducibile: non è un progetto nativo apribile con un doppio clic. Riesegui la ricetta su una copia e confronta le impostazioni e l’output. Non chiamare un JPEG/PNG esportato «RAW modificabile», non inventare formati progetto e non modificare gli originali.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/lightcraft/tree/v0.13.0
- https://github.com/storytold/lightcraft/releases

## Ruolo nella squadra

Sviluppa gli input RAW e passa immagini con profilo colore, orientamento, esposizione e dimensioni dichiarati a PhotoCraft o DesignCraft. Non richiedere RAW se il brief non ne usa.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
