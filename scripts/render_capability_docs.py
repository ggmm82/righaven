#!/usr/bin/env python3
"""Render the goal-oriented skill index from the audited, versioned tool map."""
import json
from pathlib import Path


def render(root):
    root=Path(root);data=json.loads((root/'config/tool-capabilities.json').read_text())
    index=['# Scegliere gli strumenti dal risultato', '',
        'I ruoli professionali si compilano dal progetto. Questa mappa descrive strumenti e confini, non una squadra obbligatoria.',
        'Consulta `craft capabilities` per la mappa compatta e `craft capabilities ID` per una sola app. Il catalogo completo è in `craft commands ID`; gli schemi esatti in `craft tools ID`.', '',
        '## Modello, realizzazione e confezionamento\n\nPrima di scegliere il programma per il formato finale, individua cosa deve essere costruito e quali sorgenti devono restare modificabili. Consulta gli ambienti disponibili per capacità e scopo; un profilo pronto riduce la preparazione, ma non obbliga a caricare tutti i suoi programmi. Assegna soltanto le capacità necessarie ai ruoli dinamici e descrivi la scelta in `capability_rationale`. Non confondere le competenze scritte nel titolo del ruolo con skill effettivamente assegnate.\n\nPer architetture software, valuta C4 con Structurizr e un renderer supportato; per processi con eventi, responsabilità ed eccezioni, BPMN; per relazioni o flussi informali, D2/Mermaid o una lavagna possono essere più appropriati. Typst o un editor di impaginazione possono integrare gli export nel documento, conservando anche i modelli originali. Semplici forme decorative non dimostrano la semantica di un modello C4/BPMN. Nessuna notazione è obbligatoria per ogni diagramma.\n\nLo stesso principio vale negli altri domini: contenitore e conversione non sostituiscono composizione musicale, modellazione CAD, analisi dei dati o authoring del prodotto. Non usare tutti gli strumenti per principio; spiega quando una soluzione più semplice conserva gli stessi requisiti e prova un campione pertinente.', '',
        'Un comando registrato non è un workflow collaudato: verifica prerequisiti, dati, unità, modelli/add-on e reale esecuzione. `enabled=false` può dipendere dalla selezione o dal documento aperto; non significa automaticamente funzione assente.', '',
        '| Strumento | Quando sceglierlo | Sorgenti da conservare |','|---|---|---|']
    rendered={}
    for app in data['applications']:
        skill=root/'skills/custom'/('skill-'+app['id']);ref=skill/'references/CAPABILITIES.md'
        index.append('| ['+app['id']+'](../../skill-'+app['id']+'/references/CAPABILITIES.md) | '+app['choose_for']+' | '+app['sources']+' |')
        lines=['# Capacità operative: '+app['id'], '',
            'Versione esaminata: **'+app['version']+'**. Audit del catalogo nativo: '+data['audited_date']+'.', '',
            '**Sceglilo per:** '+app['choose_for']+'.', '**Sorgenti:** '+app['sources']+'.', '',
            '## Dal risultato ai comandi', '', '| Obiettivo | ID presenti nella versione fissata |','|---|---|']
        for group in app['groups']:lines.append('| '+group['goal']+' | '+', '.join('`'+c+'`' for c in group['commands'])+' |')
        lines += ['', 'Gli ID sopra sono registrati dalla CLI, non una certificazione di ogni funzione. Scopri parametri, contesto e disponibilità prima di mutare il documento. Le prove minime ripetibili sono in `CLI-RECIPE.md`; la qualità di produzione è trattata in `QUALITY.md`.', '',
            '## Limiti e scelta del metodo', '',app['limits'], '',
            '## Scoperta mirata', '',
            '1. `craft capabilities '+app['id']+'`: selezione per obiettivo e confini.',
            '2. `craft commands '+app['id']+'`: registro integrale; cerca soltanto gli ID pertinenti.',
            '3. `craft tools '+app['id']+' --out "$RIGHAVEN_OUTPUT_DIR/work/'+app['id']+'-tools.json"`: schemi MCP della release.',
            '4. Apri un input pertinente, salva presto il sorgente e verifica una prova a finitura prevista. Riduci il perimetro prima della qualità.',
            '5. Verifica le proprietà salvate e un export effettivo; non trasformare il codice di uscita zero in una valutazione professionale.', '',
            'Catalogo esaminato: '+str(app['catalog_count'])+' ID unici (le integrazioni con adattatore descrivono le operazioni esposte, non l’intera API upstream). SHA256 della rilevazione: `'+app['catalog_sha256']+'`.',
            'Fonte: '+app['reference']+'. Il catalogo locale della versione fissata prevale sulla documentazione di versioni successive.','']
        rendered[ref]='\n'.join(lines)
    index += ['', '## Passaggi tra strumenti', '',
        'Per ogni passaggio specifica risultato atteso, formato, unità/scala, risoluzione, colore, frame rate/sample rate e riferimenti temporali pertinenti. L’integrazione conserva anche i sorgenti delle componenti, non soltanto il progetto che li contiene.',
        'Usa gli strumenti di authoring pertinenti prima di ridurre tutto a primitive o script usa-e-getta. Lo scripting rimane utile per costruzione e automazione, con ricetta e parametri conservati. La disponibilità di molte app non obbliga a usarle tutte.',
        'Se la prova non raggiunge la finitura, cambia il metodo o la competenza sul difetto osservato. Un campione breve può essere fedele al livello finale; un render lungo dello stesso asset rudimentale non lo migliora.','']
    rendered[root/'skills/custom/skill-harness/references/TOOL-SELECTION.md']='\n'.join(index)
    return rendered


def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    for path,text in render(root).items():
        if args.check:
            if not path.is_file() or path.read_text()!=text:raise SystemExit('Documento capacità non aggiornato: '+str(path))
        else:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    print('Capability docs OK:', len(render(root)) - 1, 'tools and goal-oriented coordinator index')


if __name__=='__main__':main()
