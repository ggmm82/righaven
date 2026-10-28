# Ricetta nativa: Playwright

`playwright-cli commands` restituisce gli schemi supportati. Le operazioni sono stateless: ogni chiamata indica input e output espliciti. Sostituisci `JOB` con la cartella realmente assegnata; gli output devono essere nuovi.

```bash
craft help playwright
craft commands playwright
craft tools playwright --out "$RIGHAVEN_OUTPUT_DIR/work/playwright-tools.json"
playwright-cli call test '{"input":"/mnt/user-data/outputs/JOB/work/flow.test.cjs","output":"/mnt/user-data/outputs/JOB/work/browser-proof"}'
```

La stessa operazione può essere invocata via `craft batch playwright` con `name` completo e `arguments` conformi allo schema MCP.

Esempio minimo da adattare ai requisiti reali:

```javascript
const {test,expect}=require('@playwright/test');
test('interazione', async ({page}) => {
  await page.goto('file:///mnt/user-data/outputs/JOB/site/index.html');
  await page.getByRole('button', {name:'Salva'}).click();
  await expect(page.getByText('Salvato')).toBeVisible();
});
```

## Collaudo ripetibile

Il collaudo apre una pagina locale, clicca un bottone, verifica il nuovo testo e decodifica una screenshot reale. Un’asserzione errata deve fallire. Sono conservati JSON e trace degli errori; un esito zero senza test non è una prova. Il caso è in `scripts/acceptance_toolkit.py`, eseguito dalla CI nella stessa immagine di rilascio, senza rete e nel budget del worker.

Dopo `delivery` confronta il risultato con i requisiti e con i sorgenti trasferiti. Questa fixture prova l’integrazione tecnica, non garantisce finitura professionale su qualsiasi incarico.
