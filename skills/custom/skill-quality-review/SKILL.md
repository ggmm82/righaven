---
name: skill-quality-review
description: "Verifica indipendente di requisiti, qualità osservabile, regressioni e sorgenti modificabili per qualsiasi prodotto."
metadata:
  skill-kind: method
  license: MIT
---

# Revisione del risultato

1. Identifica la versione esatta, la fase e la richiesta originale. Separa criteri dell'utente, scelte della squadra e controlli facoltativi. Un campione non deve soddisfare il volume del prodotto completo, ma deve rispondere alla domanda della prova.
2. Associa ogni criterio alla modalità d'osservazione necessaria: lettura, visione, ascolto, esecuzione, misura o riapertura nativa. Verifica che tale modalità sia disponibile; in caso contrario registra not_run e il limite, senza dedurre un esito positivo.
3. Ispeziona il prodotto reale e i riferimenti. Collega ogni rilievo a posizione, evidenza, requisito e impatto. Distingui errore tecnico, scarto dal brief, difetto qualitativo e preferenza soggettiva.
4. Controlla sorgenti, dipendenze e istruzioni proporzionate al prodotto. Un export valido o uno screenshot non dimostra riapertura, modificabilità o conformità del contenuto.
5. Per le revisioni confronta la nuova versione e la precedente sullo stesso criterio, preservando i file. Registra miglioramenti, regressioni e aspetti invariati. Cambiare il file non dimostra un beneficio.
6. Formula poche correzioni prioritarie con prove di accettazione. Un dubbio resta uncertain; un difetto osservato resta failed finché una nuova prova pertinente lo supera. Rispetta lo schema quality-review.json del protocollo workspace.

## Confini
Il revisore non modifica il prodotto durante una verifica indipendente. Le verifiche automatiche dimostrano solo ciò che misurano. Non dichiarare certificazioni professionali, qualità visiva o ascolto da un codice di uscita zero. Conserva evidenze e limiti per le lezioni successive.

## Strumenti
Scegli nel ruolo le CLI per ispezionare o riaprire i formati effettivi. Questa skill di metodo non impone un'app e non fornisce automaticamente capacità sensoriali al modello.
