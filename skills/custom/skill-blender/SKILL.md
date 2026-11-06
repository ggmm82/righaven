---
name: skill-blender
description: "Modellazione 3D, rig, materiali, simulazioni, animazione e rendering. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Blender: produzione 3D

Specialista `blender` per `harness_delegate`. Blender 5.2.3, checksum ufficiale fissato nel catalogo. Linux amd64, render CPU; non presupporre GPU, add-on, rete o asset esterni installati. Eredita il modello condiviso della squadra.

## Scelta dello strumento e capacità

Modellazione 3D, rig, materiali, simulazioni, animazione e rendering. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities blender` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Capacità e scelta degli strumenti

Usa Blender per volumi 3D, topologia, UV, materiali, rig, deformazioni, keyframe, camere, luci e render. Non sostituire un personaggio 3D richiesto con sagome, sprite o primitive prive dei dettagli necessari. Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md) e [QUALITY.md](references/QUALITY.md), inclusi nel contesto.

Scopri `craft help blender`, `craft commands blender` e `craft tools blender`. `blender-cli` è l'adattatore RigHaven; `blender` è l'eseguibile ufficiale. Non inventare comandi Craft per la CLI ufficiale. L'adattatore è senza stato: anche in `craft batch blender` ogni chiamata apre un nuovo processo. Salva su disco e passa esplicitamente il `.blend` successivo; i nomi MCP sono `blender.execute`, `blender.inspect`, `blender.render`, `blender.export_glb`, `blender.pack`.

## Procedura professionale

1. Leggi richiesta originale, criteri, riferimenti e file dei colleghi. Definisci scala, orientamento, durata, fps, risoluzione, stile e budget. La ricetta minima prova le API, non è il livello estetico della consegna.
2. Scrivi uno script `bpy` nel workspace. Parti da `bpy.ops.wm.read_factory_settings(use_empty=True)`; usa collezioni, nomi semantici, mesh/materiali e oggetti modificabili. Se occorrono asset di riferimento assenti, dichiaralo prima di renderizzare, senza imitazioni non autorizzate.
3. Per i personaggi costruisci gerarchie coerenti, pivot articolari, armatura, pesi e vincoli quando servono. Per movimento meccanico può bastare una gerarchia di oggetti rigidi. Evita intersezioni, slittamento dei piedi e movimenti simultanei indistinti; controlla pose chiave e silhouette da più viste. Un ballo richiede una coreografia riconoscibile, non solo oscillazioni casuali.
4. Materiali PBR con UV, scala e colore corretti. In Blender 4.5 usa socket reali dei nodi: `node.inputs.keys()` prima di assumere nomi. Per texture colore usa sRGB, per normal/roughness/metallic usa Non-Color. Collega le normal tramite Normal Map. Concorda con PhotoCraft texture e mappe specifiche; non considerarlo un generatore di immagini se non ne ha la capacità.
5. Crea un'anteprima economica da camera definitiva e frame inizio/metà/fine prima del render costoso. Stima il costo con un frame campione. Salva il progetto PRIMA del render, scrivi progressi e riprendi solo frame mancanti. Non abbassare risoluzione/durata richieste in silenzio per rientrare nel timeout.
6. Usa sequenze PNG/OpenEXR per l'animazione, non un unico render fragile. FilmCraft può montare frame e audio fornito da SoundCraft. Scegli collaboratori utili al brief; non coinvolgere tutti obbligatoriamente. Passa fps, range frame, risoluzione, alpha, color management, unità, spazio colore e percorsi reali.
7. Esporta GLB con `bpy.ops.export_scene.gltf`, FBX con `bpy.ops.export_scene.fbx` quando richiesto. Verifica import in un secondo processo e cosa resta: materiali, skin, animazione e assi possono cambiare. GLB non conserva tutti i modificatori o il rig di authoring; non descriverlo come sorgente equivalente al `.blend`.

## API e diagnosi

- `blender --background --factory-startup --disable-autoexec --threads 2 --python-exit-code 1 --python script.py` rende gli errori Python errori di processo. Non omettere `--python-exit-code` nei controlli.
- L'esecuzione automatica di script incorporati nei `.blend` è disabilitata; non aggirarla su input non fidati. Lo script esplicito scritto per il lavoro resta eseguibile nella sandbox.
- Usa Cycles CPU per render headless affidabili, campioni moderati per le bozze e denoise verificato. EEVEE può richiedere EGL/OpenGL non disponibili sul VPS: segnala il limite e prova Cycles CPU senza modificare lo stile richiesto.
- Blender 4.5 usa Actions con slot/layer: per debug esamina API reali e `animation_data`; non assumere il vecchio `action.fcurves`. Usa `keyframe_insert` per creare pose e verifica i valori valutati a frame diversi.
- In `bpy`, vincoli di contesto/selezione influenzano gli operatori. Preferisci data API per mesh/materiali; prima di operatori imposta modalità e oggetto attivo esplicitamente.
- Se un render fallisce, conserva `.blend`, log e frame; correggi il comando/risorsa. Non ripetere tutto alla cieca. Se uno script è terminato con output parziale, ispeziona i file prima di rilanciarlo.

## Consegna: sorgenti modificabili e compatibilità

Consegna `.blend` riaperto con Blender 5.2.3, export richiesti, anteprima e script di costruzione se utile. La geometria, i materiali, il rig e i keyframe devono restare modificabili. Usa `blender-cli pack input.blend consegna.blend` per incorporare texture/font/risorse supportate e poi `inspect` sul risultato. Per asset non incorporabili usa ZIP con percorsi relativi `//` e istruzioni di apertura; verifica dopo estrazione in una cartella diversa. Non distribuire riferimenti `/mnt/user-data` o `/tmp` irraggiungibili sul computer dell'utente.

`source_packages.py pack` prepara i formati Craft JSON, non i `.blend`: per Blender usa `blender-cli pack` e ZIP standard se serve. Il runtime riapre i `.blend` e controlla geometria e riferimenti anche negli ZIP. Simulazioni, cache di simulazione/bake o import di file nei Geometry Nodes, particelle, UDIM e sequenze/video richiedono collaudi specifici non ancora automatizzati: restano segnalati, non approvati automaticamente. Per la prima integrazione preferisci mesh, armature, keyframe e immagini singole incorporate, quando coerente col brief; altrimenti dichiara il limite senza sostituzioni arbitrarie.

Compila `handoff.json` con `delivery.files` per OGNI download: `.blend` come `editable_source`, ZIP come `source_archive`, GLB/video come `export`, PNG come `preview`. Indica `open_with: Blender 5.2.3, File > Open`, editabilità reale, riapertura e limiti. Metti sorgenti e archivi in `output_files`, fuori da `work/`. Se mancano sorgenti o verifiche, dichiara consegna parziale, non conclusa.

## Fonti

- https://docs.blender.org/manual/en/4.5/advanced/command_line/arguments.html
- https://docs.blender.org/api/4.5/
- https://docs.blender.org/manual/en/4.5/files/blend/packed_data.html
- https://download.blender.org/release/Blender4.5/

## Costo e supervisione del render

Usa `blender-cli profile SCENA.blend --frame 1` per la misura preventiva. `blender-cli render` lo fa automaticamente e pubblica i campioni osservati nel pannello; mantiene progetto, dimensioni e campioni finali. Per animazioni/script lunghi usa il supervisore comune in `skill-workspace`. Non sfuggire al controllo passando a Blender nativo in background dopo un timeout: verifica che il vecchio processo sia terminato e riprendi solo ciò che manca. I render nativi necessari devono usare lo stesso supervisore. Dopo un OOM confermato sospendi e conserva sorgenti; non tentare ripetutamente render interi o porzioni concorrenti con lo stesso budget.
