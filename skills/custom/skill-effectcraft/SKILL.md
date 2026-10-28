---
name: skill-effectcraft
description: "Animazione 2D/3D, motion graphics, compositing, camera/luci ed effetti. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Animazione ed effetti

Specialista: `effectcraft` per `harness_delegate`; nome della skill: `skill-effectcraft`.
CLI: `effectcraft-cli`. La release è fissata in `/opt/righaven/versions.lock.json`.

## Scelta dello strumento e capacità

Animazione 2D/3D, motion graphics, compositing, camera/luci ed effetti. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities effectcraft` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Quando usarla

Usa EffectCraft per composizioni, motion graphics, keyframe ed effetti. Il montaggio finale di molte clip appartiene a FilmCraft.

## Modifiche persistenti

Ogni invocazione diretta della CLI apre un processo nuovo. Per modificare un progetto esistente usa `--project FILE --save` con `set`, `run` o `script`, oppure `--save-as COPIA` per conservare la baseline. Un comando riuscito senza salvataggio può lasciare invariato il file. Riapri in un altro processo e verifica proprietà/keyframe e un fotogramma pertinente prima di renderizzare l’intera sequenza. Il valore statico di una proprietà non prevale necessariamente sulle sue tracce animate: controlla i valori ai tempi del difetto e modifica le chiavi responsabili.

## Ricetta operativa collaudata

Leggi [la ricetta CLI verificata](references/CLI-RECIPE.md), da consultare per la sintassi pertinente. Mantieni i controlli e adatta la procedura agli input reali.

## Avvio e scoperta

1. Leggi la skill comune `skill-workspace`.
2. Esegui `craft help effectcraft` e consulta `/opt/righaven/reference/effectcraft/help.txt`.
3. Salva il registro reale con `craft commands effectcraft > "$RIGHAVEN_OUTPUT_DIR/work/effectcraft-commands.txt"`.
4. Cerca nel registro solo i comandi pertinenti. I parametri non sono uniformi tra applicazioni.
5. Per i tool MCP nativi usa `craft tools effectcraft --out "$RIGHAVEN_OUTPUT_DIR/work/effectcraft-tools.json"`.
   È un processo locale nella sandbox: non occorre un server sempre acceso.
6. Per una sequenza MCP con stato usa `craft batch effectcraft sequenza.json`; tutte le chiamate della sequenza condividono la stessa sessione.
   La sequenza deve includere il salvataggio del documento prima dell'uscita.

## Procedura professionale

1. Definisci composizione principale, risoluzione, fps, durata e sfondo/alpha. Elenca livelli, media, font e dipendenze prima di impostare animazioni.
2. Organizza livelli e precomposizioni; imposta valori iniziali/finali, keyframe e interpolazione in unità temporali esplicite. Controlla punti di ancoraggio e trasformazioni.
3. Renderizza frame iniziale, centrale e finale e i punti di cambio prima della sequenza completa. Per loop verifica continuità; per alpha scegli un formato che lo conservi.

## Diagnosi e recupero CLI

- Se un’animazione è statica, verifica composizione esportata, livello, proprietà animata, intervallo temporale e interpolazione nello schema reale, prima di aggiungere altri keyframe.
- Se manca la trasparenza, controlla canale alpha e formato/codec effettivo; non dedurla dall’estensione. Per un loop confronta anche il raccordo tra ultimo e primo frame.
- Dopo un errore leggi il risultato e lo schema del solo tool coinvolto. Riparti dalla copia salvata più recente e verifica gli effetti già applicati prima di ripetere una mutazione.

## Controlli di accettazione

- Confronta durata e numero frame attesi con l’export; verifica fps, risoluzione e alpha tramite metadati e riapertura.
- Controlla dipendenze mancanti, bordi, testi e interpolazione sui frame campione; registra visione non eseguita.
- Consegna progetto modificabile, asset necessari ed export; indica effetti non supportati o sostituiti.

## Sintassi di riferimento

Gli esempi seguenti indicano la sintassi; i file `input.*` devono esistere e i percorsi vanno adattati alla cartella assegnata.
Il `--help`, il registro e gli schemi della release installata restano la fonte operativa.

```bash
effectcraft-cli commands
effectcraft-cli --project input.ecproj info
effectcraft-cli --project input.ecproj render --comp Main --out output.mp4
```

## Consegna: sorgenti modificabili e compatibilità

Consegna il progetto `.ecproj`, le risorse collegate necessarie e gli export richiesti (GIF/video/frame). Riapri con `effectcraft-cli --project ... info` e verifica composizioni, livelli e keyframe, non soltanto un frame renderizzato. Per media esterni prepara e prova un pacchetto autosufficiente estratto in una nuova cartella. Un video/GIF non conserva di per sé livelli o keyframe modificabili; registra font, plugin o effetti non disponibili.

Per ogni file consegnato compila `delivery.files` in `handoff.json` secondo `skill-workspace`: ruolo (sorgente/export/pacchetto), formato reale, `open_with` (app e modalità di apertura), `editability` (cosa resta modificabile), prova di riapertura e limiti. I sorgenti e gli archivi necessari devono comparire in `output_files`, fuori da `work/`, così il coordinatore può renderli scaricabili; `source_files` da solo non basta. Distingui originali in input dai nuovi sorgenti del risultato.

Riapri ogni sorgente salvato con l’app di destinazione in una nuova sessione e verifica la struttura modificabile, non solo estensione, header o viewer. Registra il comando/tool reale e il risultato; se la verifica manca usa `not_run`, se fallisce usa `failed`. Non dichiarare compatibilità con altre app per analogia. Se non è possibile fornire il sorgente equivalente, imposta `delivery.source_status: "unavailable"`, spiega il motivo in `source_note` e `warnings` e indica ciò che manca: la consegna è parziale, non un prodotto pienamente modificabile. Non inventare file nativi, non cambiare semplicemente l’estensione e non consegnare log/cataloghi come sorgenti.

## Fonti

- https://github.com/storytold/effectcraft/tree/v0.16.0
- https://github.com/storytold/effectcraft/releases

## Ruolo nella squadra

Importa gli asset di PhotoCraft/VectorCraft, conserva alpha e separazione delle parti, definisci rig, keyframe e movimento coerenti con il brief. Condividi durata, fps, BPM e cue con SoundCraft. Passa animazione e .ecproj con asset a FilmCraft. Per un robot 3D verifica le funzioni 3D reali della release: non degradare in silenzio il brief a un disegno isometrico. Non assorbire texture, colonna sonora e montaggio assegnati ai colleghi.

Applica le regole di collaborazione e checkpoint di `skill-workspace`. Se una dipendenza non si importa o manca, segnala il blocco e conserva quanto già salvato; non sostituirla con un segnaposto.

## Prova completa e revisioni mirate

Prima di un render lungo crea una breve sequenza con gli asset reali e pose campione: controlla soggetto grande e leggibile, proporzioni in rotazione, giunture, ritmo e continuità. Correggi su quella prova, poi estendi il render. Una revisione non richiede di riscrivere da zero un rig già valido.

## Qualità del prodotto

Applica [i criteri specifici della disciplina](references/QUALITY.md), da leggere per valutare il risultato. Le prove CLI minime non sono modelli estetici per la consegna.
