"""Small execution brief; protocols and CLI references remain native skill files."""
import json


def build_prompt(job, selected, output_dir):
    policy = {k: v for k, v in job.get('capability_policy', {}).items() if k in ('source', 'allowed', 'blocked', 'installed', 'available_on_request')}
    purpose = job.get('purpose', 'work')
    phase = {
        'preview': 'Produci soltanto la prova necessaria a decidere il metodo, con il sorgente riapribile e le risorse usate. '
            'Non preparare ZIP, manuali estesi o componenti estranei alla domanda della prova, salvo richiesta esplicita. '
            'Il runtime registra il pacchetto mancante come lavoro finale da completare; se consegni un archivio deve essere valido.',
        'review': 'Distingui la domanda della prova dal contratto finale. Per un campione dichiara scope checkpoint con '
            'question e requirement_ids pertinenti nel rapporto; conserva separatamente tutti i requisiti finali non soddisfatti. '
            'Non chiedere una rigenerazione per una modalità di osservazione indisponibile. Non modificare il prodotto. '
            'Usa review_version:2 e findings: per ogni bocciatura specifica requirement_id, severity blocking, '
            'location, evidence realmente osservata e impact sul risultato richiesto. Un gusto personale o un '
            'ritocco facoltativo è advisory e non fa fallire un requisito. Un dubbio è uncertain: verifica '
            'prima la causa con la prova meno costosa. Non dichiarare collisioni o errori senza riscontro.',
        'delivery': 'Completa il prodotto richiesto, pacchetti portabili, associazioni componenti e verifiche reali. '
            'Riusa i sorgenti della prova e correggi gli scarti rimasti; evita un nuovo campione equivalente.'
    }.get(purpose, 'Riusa i risultati disponibili e completa soltanto la parte affidata.')
    return '\n\n'.join([
        'Follow the user’s output language. Role: ' + (job.get('role') or {}).get('title', job['agent']) + '.',
        'Incarico del coordinatore:\n' + job['task'],
        *(['Versioni effettive (prevalgono sulle skill): '+json.dumps(job['tool_versions'])] if job.get('tool_versions') else []),
        'Disponibilità effettiva: ' + json.dumps(policy, ensure_ascii=False) +
        '. Rispetta gli esclusi anche via shell/Python. Non installare software o aggirare disattivazioni.' +
        (' installed: programmi presenti; available_on_request: richiedi al coordinatore un incarico con tools espliciti.' if 'installed' in policy else ''),
        'Esegui la parte affidata con le capacità pertinenti. Un solo strumento può bastare; aggiungine uno quando '
        'risolve un limite concreto senza perdere modificabilità o qualità. Le competenze del ruolo sono istruzioni, '
        'non capacità acquisite per il solo fatto di nominarle. Le ricette CLI dimostrano sintassi, non finitura.',
        'Prima di costruire identifica il risultato osservabile di questa fase e il criterio più rischioso. '
        'Riusa asset, sorgenti e metodo validi. Un difetto locale richiede una correzione locale: cambia strumento '
        'o riscrivi il prodotto soltanto per un limite osservato o un beneficio dimostrato su un piccolo confronto. '
        'Per una correzione isola prima il difetto prioritario con la prova meno costosa pertinente '
        '(per esempio un fotogramma, un caso di calcolo o una breve esecuzione), poi ripeti la produzione estesa. '
        'Un tool di rendering o compositing non crea automaticamente asset ben disegnati. '
        'Se mancano asset o capacità, registra il limite; non costruire un sostituto rudimentale per riempire la consegna.',
        'Fase: ' + purpose + '. Una prova riduce estensione o durata, conservando il livello di finitura richiesto. '
        'Confronta il risultato reale con richieste e riferimenti. Descrivi il difetto, la causa ipotizzata e la prova '
        'che distingue le cause prima di cambiare metodo. Non espandere un campione che sai essere insufficiente.',
        phase,
        'Progetto /mnt/user-data in sola lettura: copia gli input da revisionare. Scrivi solo nello staging ' + str(output_dir) +
        ' (RIGHAVEN_OUTPUT_DIR); non sovrascrivere gli input. Conserva sorgenti e checkpoint presto. '
        'Python: /usr/bin/python3; craft e CLI: /usr/local/bin. Scopri solo comandi pertinenti con craft help/tools/commands. '
        'Non delegare, pubblicare o accedere a credenziali e altre conversazioni. '
        'Non leggere /credentials né le cartelle .codex/.gemini/.deepseek/.openai.',
        'Le skills seguenti contengono la procedura. Leggi i riferimenti solo quando servono: '
        'CLI-RECIPE per sintassi o recupero, QUALITY per la verifica della disciplina, protocolli di consegna '
        'quando prepari handoff.json. Non avviare una ricetta minima come modello estetico del prodotto.',
        *selected, job.get('instructions', ''),
        'Concludi salvando handoff.json: file reali, sorgenti modificabili, riapertura effettiva, checks e limiti. '
        'Prima di chiudere esegui /usr/bin/python3 /opt/righaven-worker/handoff.py validate "' + str(output_dir) + '". '
        'Se fallisce correggi il manifest nella stessa sessione senza rifare i prodotti; '
        'lo schema effettivo è disponibile con /usr/bin/python3 /opt/righaven-worker/handoff.py schema. '
        'Per i dettagli usa i riferimenti di skill-workspace. Non scambiare export riuscito per qualità. '
        'Conserva failed e not_run. DELIVERY spiega historical/superseded_by per test superati da nuove prove; '
        'REVIEW spiega supplementary senza requirement_id per controlli facoltativi fuori contratto. '
        'Le osservazioni negative sono utili anche se non hai ancora trovato una soluzione: preservale nel handoff. '
        'Una lezione sul metodo può essere proposta con prove e limiti; non richiede un test CLI positivo. '
        'L’attivazione automatica delle sole conoscenze tecniche richiede invece il test documentato.',
        'Il budget vale per questa fase, non per tutto il progetto. Salva work/checkpoint.json con completed, files, '
        'remaining, next_action. Registra work/method.json con approach, steps, scripts, limits. '
        'Per la consegna salva work/guide.json: uso, file da modificare, passi provati e limiti; schema in GUIDE.md. '
        'Registra solo scoperte utili in work/tool-lessons.json; lo schema è nel riferimento LEARNING.md. '
        'Un errore riprodotto del verificatore o una correzione di uso della CLI può insegnare una regola tecnica: '
        'non scartarla come fatto specifico soltanto perché il prodotto non è ancora approvato. '
        'Una proposta senza test resta inattiva; la conoscenza tecnica verificata non richiede un beneficio estetico o tempi inventati. '
        'Aggiorna l’utente a ogni traguardo con report_progress oppure '
        '/usr/bin/python3 /opt/righaven-worker/progress.py --phase creating --summary "Risultato e prossimo controllo". '
        'Fasi: planning, creating, exporting, checking, finalizing. Nessuna percentuale inventata.'
    ])
