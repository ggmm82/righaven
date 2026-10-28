# Ricetta verificabile: Manim Community

1. Leggi `manim-cli commands` oppure `craft tools manim` per gli schemi della versione fissata.
2. Invoca `manim-cli call OPERAZIONE '{"input":"/mnt/user-data/...","output":"/mnt/user-data/..."}'` con i campi esatti dello schema. I nomi sono senza prefisso, per esempio `render`. Output sempre nuovi e separati dagli originali.
3. Le operazioni execute/render richiedono uno script `.py` esplicito; `resource_dir` raccoglie script e risorse relative. Non includere la directory di output fra gli input. Lo script usa `righaven_JOB_OUTPUT` per salvare i documenti.
4. Controlla il documento nativo e l’export, poi ripeti la riapertura dopo aver spostato lo ZIP. Un esito negativo resta un difetto, non una consegna.
5. Compila `delivery` con artifact, editable_source, source_archive, guida d’uso e componenti effettive. Non limitarti a un file piatto.

Fonte API: https://docs.manim.community/en/stable/. Prove native ripetibili: `scripts/acceptance_production.py`. La copertura è limitata alle prove eseguite, non a ogni funzione upstream.

## Scene riproducibili con Cairo

- Scrivi una classe `Scene` con `construct`, oggetti (`Text`, `Dot`, `Axes`, `SVGMobject`) e animazioni `self.play`, `Transform`, `Create`, `ValueTracker`, `always_redraw` quando servono relazioni dinamiche. Dichiara tempi, riferimenti e `rate_func`; non allungare una scena senza sviluppo visivo.
- `manim-cli call render '{"input":"/mnt/user-data/resources/scene.py","resource_dir":"/mnt/user-data/resources","output":"/mnt/user-data/rendered","scene":"MyScene","quality":"draft"}'` cattura risorse e script. Per il risultato finale scegli `standard` o `high` se richiesto dal brief.
- La CLI usa `manim render --renderer=cairo --disable_caching`, CPU e un’unica Scene nominata. Il video finale è sotto `Render/videos`; `Sources` e `render-recipe.json` sono i sorgenti riproducibili. Non consegnare cache/partial_movie_files come risultati.
- Riferisci le risorse a `Path(__file__).parent`; verifica un rerender dalla copia spostata. `MathTex` richiede LaTeX non installato: usa SVG prodotti da Typst o esplicita il prerequisito invece di tentare installazioni nascoste.
- Per compositing generale, sonorizzazione o montaggio passa il render agli strumenti esistenti con fps, durata e alpha dichiarati.
