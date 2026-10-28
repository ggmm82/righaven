# gridcraft — ricetta CLI verificata

Questa ricetta è stata eseguita con la release fissata nel catalogo e viene inclusa automaticamente nel contesto dello specialista. Gli input di prova non sostituiscono quelli dell’utente. Adatta contenuti, dimensioni e percorsi al brief e alla cartella assegnata. Nei blocchi JSON sostituisci i percorsi di esempio; non lasciare il segnaposto RUN.

## Dati numerici, formula e cache XLSX
Lista verificata da adattare ai dati reali e passare a `craft batch gridcraft`:
```json
[
  {"name":"new_workbook","arguments":{}},
  {"name":"set_cell","arguments":{"cell":"A1","input":10}},
  {"name":"set_cell","arguments":{"cell":"A2","input":20}},
  {"name":"set_cell","arguments":{"cell":"A3","input":30}},
  {"name":"set_cell","arguments":{"cell":"A4","input":"=SUM(A1:A3)"}},
  {"name":"save_workbook","arguments":{"path":"/mnt/user-data/outputs/gridcraft/RUN/totali.xlsx"}}
]
```
```bash
gridcraft-cli check "$RIGHAVEN_OUTPUT_DIR/totali.xlsx" --json
```
Prova eseguita: il test legge indipendentemente `xl/worksheets/sheet1.xml` nel contenitore XLSX, trova formula `SUM(A1:A3)` e cache numerica 60. I numeri JSON sono numeri, non stringhe formattate. Non trasferire valori dimostrativi agli input reali e non sostituire una formula con una costante per far passare il controllo.

La prova ripetibile è in `/opt/righaven/acceptance.py`, caso `gridcraft`. È un banco di collaudo con fixture, non una scorciatoia per produrre la consegna dell’utente. Non dichiarare visione o ascolto sulla base dei soli controlli tecnici.


## Consegna della lavorazione

Consegna il file XLSX modificabile con fogli, celle, formule, tabelle e grafici realmente presenti, oltre agli export richiesti. Riaprilo con GridCraft e verifica formule e valori ricalcolati; dichiara riferimenti esterni o dati da aggiornare. CSV/PDF/immagini non sostituiscono un workbook con formule e più fogli: non sostituire formule con i soli valori né presentare un CSV come sorgente equivalente.
Compila `delivery` secondo `skill-workspace` e rendi scaricabili i sorgenti in `output_files`. La riapertura e la struttura modificabile devono riferirsi ai file effettivi del brief, non soltanto al collaudo di questa ricetta; segnala qualsiasi controllo `failed` o `not_run`.
