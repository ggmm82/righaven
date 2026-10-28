# Capacità operative: manim

Versione esaminata: **0.22.0**. Audit del catalogo nativo: 2026-10-25.

**Sceglilo per:** Animazioni didattiche, matematiche e dati costruite con Scene Python; EffectCraft resta il compositore generale..
**Sorgenti:** Scene Python, risorse, render-recipe.json e parametri riproducibili..

## Dal risultato ai comandi

| Obiettivo | ID presenti nella versione fissata |
|---|---|
| Render an explicit Scene with Cairo on CPU, retaining Python and supplied resources. Math can use SVG from the existing Typst tool; LaTeX is not bundled. | `manim.render` |

Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.

## Limiti e scelta del metodo

Renderer Cairo CPU. LaTeX non incluso: usare SVG generati con Typst già disponibile per formule. Non è un editor video né un sostituto di rig e animazione organica.

## Scoperta mirata

1. `craft capabilities manim`: selezione per obiettivo e confini.
2. `craft commands manim`: registro integrale; cerca soltanto gli ID pertinenti.
3. `craft tools manim --out "$RIGHAVEN_OUTPUT_DIR/work/manim-tools.json"`: schemi MCP della release.
4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.
5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.

Catalogo esaminato: 1 ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `b59ddc2863c49a3efe18af237328d75a679151070c37473825079621ea913050`.
Fonte: https://docs.manim.community/en/stable/. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.
