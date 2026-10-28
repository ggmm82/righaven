---
name: skill-calibre
description: "Produzione e conversione editoriale, EPUB/AZW3, metadati, risorse e librerie. Scelta dei comandi, limiti, sorgenti modificabili e verifiche native."
---

# Calibre: documenti e pubblicazioni digitali

Calibre **9.17.0**, release ufficiale e SHA-256 fissati nel catalogo. Questa skill descrive uno strumento: non definisce professioni, una squadra editoriale obbligatoria o una sequenza di progetto. Un ruolo compilato dinamicamente può selezionarla quando serve una sua capacità. Eredita provider e modello condivisi.

Leggi `skill-workspace`, [CLI-RECIPE.md](references/CLI-RECIPE.md) e [QUALITY.md](references/QUALITY.md). Scopri `craft help calibre`, `craft commands calibre`, `craft tools calibre`. `calibre-cli` è l’adattatore RigHaven; `ebook-convert`, `ebook-meta`, `ebook-polish`, `calibre-debug`, `calibredb`, `ebook-edit` sono le CLI ufficiali. Non inventare comandi e non confondere i nomi MCP con quelli nativi.

## Scelta dello strumento e capacità

Produzione e conversione editoriale, EPUB/AZW3, metadati, risorse e librerie. Consulta [la mappa operativa completa](references/CAPABILITIES.md) o `craft capabilities calibre` per scegliere i comandi dal risultato, con limiti e sorgenti. Le ricette minime sotto sono collaudi delle API, non il livello qualitativo da consegnare.

## Scelta e limiti

Conversione, struttura, risorse e metadati non sostituiscono scrittura, ricerca, revisione, progettazione grafica, accessibilità o controllo dei fatti. Usa input e criteri del progetto, coinvolgendo altri ruoli soltanto se utili. Non convertire un PDF complesso aspettandoti di ricostruire automaticamente un documento di authoring equivalente. Per una richiesta di stampa con abbondanze, PDF/X, CMYK o layout complesso valuta gli strumenti e le verifiche adatti: non promettere che una conversione Calibre li garantisca.

## Operazioni effettive

- `calibre.convert`: input e output assoluti nel workspace, output nuovo. Metadati, cover, CSS, XPath capitoli/indice e EPUB 2/3 sono opzioni esplicite. L’input resta intatto. Per opzioni avanzate leggi `ebook-convert INPUT OUTPUT --help`, che varia per formato; usa il supervisore comune anche per comandi nativi lunghi.
- `calibre.inspect`: riapre EPUB/AZW3 con Calibre e restituisce metadati, risorse e ordine di lettura. Non è una verifica visiva.
- `calibre.check`: controlli strutturali nativi, errori e avvisi distinti. Correggi gli errori; valuta e dichiara gli avvisi pertinenti. Non chiamarlo certificazione EPUBCheck o prova su dispositivi.
- `calibre.metadata`: nuova copia nello stesso formato. Autori multipli secondo la sintassi nativa `Nome & Nome`; lingua ISO, titolo, editore, tag e copertina. Controlla i dati dopo la modifica.
- `calibre.polish`: EPUB/AZW3 nello stesso formato, nuova copia; copertina/OPF, embedding/subset font o punteggiatura. Preferiscilo a una riconversione quando basta una rifinitura. Verifica licenze dei font e resa dei glifi.
- `calibre.unpack` e `calibre.pack`: esportano e ricostruiscono sorgenti EPUB/AZW3/DOCX/HTMLZ con `calibre-debug`. Conserva formato e `.righaven-source.json`; per cambiare formato usa convert. Il round-trip non garantisce che ogni formato conservi tutti gli aspetti di impaginazione: prova il prodotto ricostruito.
- `calibre.library`: `add`, `list`, `export` su una cartella locale esplicita del lavoro; IDs richiesti per export. Non tocca librerie personali o server remoti. Una libreria non è necessaria per convertire un file.

Le chiamate sono senza stato salvo i file indicati e l’eventuale libreria esplicita. Non esiste un documento corrente implicito nel batch. I processi sono supervisionati e pubblicano etichetta, log, tempi e risorse; il limite operativo non è una previsione di consegna. Dopo un errore conserva input, log e output parziali, controlla prima di riprovare e riprendi solo l’operazione necessaria. Non avviare processi duplicati o concorrenti per aggirare il budget.

## Consegna: sorgenti modificabili e compatibilità

Consegna prodotto richiesto, sorgente di authoring realmente usato e risorse complete. Per EPUB/AZW3 includi il contenitore modificabile e, se utile alla lavorazione, uno ZIP dei sorgenti XHTML/CSS/OPF/immagini/font estratti, con istruzioni e input originali pertinenti. Un PDF o un README da soli non sono il sorgente della pubblicazione. Non sostituire un DOCX originale complesso con XHTML se si perderebbe l’editabilità richiesta.

Prova estrazione, modifica di un contenuto campione e ricostruzione su una copia; riapri il risultato e controlla testo, indice, immagini e struttura. Per il pacchetto finale ripeti la riapertura dopo estrazione in una cartella diversa, senza dipendere da `/mnt/user-data`, cache o libreria locale. EPUB contiene già risorse interne: non necessita di una libreria Calibre per essere trasferito. Il runtime verifica EPUB/AZW3 anche negli ZIP con il checker nativo; non verifica automaticamente il layout del DOCX o la resa in tutte le app.

In `handoff.json` registra OGNI file in `delivery.files`: prodotto `export`, EPUB o documento di authoring `editable_source`, ZIP `source_archive`, prove `report`/`preview`. Per l’EPUB indica `open_with: Calibre 9.17.0, Modifica libro (ebook-edit)` e che XHTML/CSS/OPF restano modificabili; per DOCX indica l’app effettivamente provata. Riporta `reopen` con comando ed evidenza reali, gli avvisi e i limiti. Mantieni i download fuori da `work/`. Distingui riapertura CLI provata, GUI non provata e qualità da valutare. Nessuna consegna completa se mancano sorgenti o dipendenze necessari.

## Fonti

- https://manual.calibre-ebook.com/generated/en/cli-index.html
- https://manual.calibre-ebook.com/generated/en/ebook-convert.html
- https://manual.calibre-ebook.com/generated/en/calibre-debug.html
- https://manual.calibre-ebook.com/edit.html
- https://github.com/kovidgoyal/calibre/releases/tag/v9.17.0
