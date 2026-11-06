---
name: skill-gridcraft
description: "Fogli di calcolo, formule, tabelle, grafici, analisi e reporting. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Fogli di calcolo

Specialista: `gridcraft` per `harness_delegate`; nome della skill: `skill-gridcraft`.
CLI: `gridcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Fogli di calcolo, formule, tabelle, grafici, analisi e reporting. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities gridcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa GridCraft per dati, formule, tabelle, grafici e XLSX. Fornisci a DeckCraft dati verificati e definizioni delle metriche quando serve una presentazione.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help gridcraft` e consulta `/opt/righaven/reference/gridcraft/help.txt`.
3. Salva il registro reale con `craft commands gridcraft > "$RIGHAVEN_OUTPUT_DIR/work/gridcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools gridcraft --out "$RIGHAVEN_OUTPUT_DIR/work/gridcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch gridcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Inventaria fogli, intervalli, intestazioni, tipi, formule, righe nascoste e celle unite. Distingui zero, vuoto e dato mancante; registra duplicati e date ambigue prima della pulizia.
2. Mantieni importi e percentuali come numeri, date come date e unità nelle intestazioni. Usa la sintassi canonica delle funzioni/API; applica separatori italiani soltanto alla presentazione. Non convertire tutte le celle in testo.
3. Conserva dati originali in una copia o foglio dedicato. Inserisci formule con riferimenti corretti, ricalcola, controlla errori e riconcilia i totali con un calcolo indipendente. Non mascherare divisioni per zero senza spiegazione.

## Diagnosi e recupero CLI

- Se una formula restituisce un errore, verifica tipi delle celle, sintassi canonica, intervallo e ricalcolo. Non sostituire la formula con il risultato costante per far passare il controllo.
- Se un ID di documento o foglio diventa sconosciuto tra chiamate MCP, ricrea apertura, modifica e salvataggio in un unico craft batch; usa $result sul campo effettivo restituito e riapri poi il file salvato.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Riapri XLSX e verifica fogli, tipi, formule e valori ricalcolati; esegui check e controlla celle con errori.
- Riconcilia numero righe e totali prima/dopo; per grafici controlla intervalli, etichette e unità.
- Consegna XLSX con formule e dati verificati in CSV/JSON per i colleghi, specificando separatore, periodo, unità e definizioni.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
gridcraft-cli info input.xlsx --json
gridcraft-cli commands --json
gridcraft-cli functions --json
gridcraft-cli eval "=SUM(1,2,3)"
gridcraft-cli cat input.xlsx --range A1:D20 --csv
gridcraft-cli check input.xlsx --json
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il file XLSX modificabile con fogli, celle, formule, tabelle e grafici realmente presenti, oltre agli export richiesti. Riaprilo con GridCraft e verifica formule e valori ricalcolati; dichiara riferimenti esterni o dati da aggiornare. CSV/PDF/immagini non sostituiscono un workbook con formule e più fogli: non sostituire formule con i soli valori né presentare un CSV come sorgente equivalente.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/gridcraft/tree/v0.11.1
- https://github.com/storytold/gridcraft/releases

## Ruolo nella squadra

Prepara dati, formule e misure verificabili con unità e provenienza, poi passa XLSX e tabelle effettive a WordCraft, DeckCraft o DesignCraft. Non ricostruire testi o grafica specialistica per evitare il passaggio.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
