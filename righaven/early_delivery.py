"""Explicit early closure exposes saved work with honest, unverified metadata."""
import json
from pathlib import Path
import shutil

CONTROL={'handoff.json','delivery-manifest.json','quality-review.json'}
SOURCES={'.typ','.tex','.svg','.psd','.blend','.fcstd','.fcproj','.ecproj','.scraft','.otio','.mlp',
         '.py','.js','.ts','.html','.css','.md','.json','.yaml','.yml','.docx','.pptx','.xlsx','.scad','.ifc'}
REPORTS={'.txt','.md','.json','.yaml','.yml','.csv'}


def draft_handoff(output):
    output=Path(output).resolve()
    files=[p for p in sorted(output.iterdir()) if p.is_file() and not p.is_symlink() and p.stat().st_size
           and p.name not in CONTROL and not p.name.startswith('.') and p.suffix not in ('.tmp','.lock')][:40]
    if not files:raise ValueError('Nessun prodotto già salvato da consegnare; le consegne precedenti restano disponibili')
    previews=[p for p in sorted((output/'previews').glob('*')) if p.is_file() and not p.is_symlink() and p.stat().st_size][:8]
    entries=[]
    sources=False;exports=False
    note='Chiusura anticipata richiesta dall’utente: riapertura e completamento non certificati.'
    for path in files+previews:
        role='preview' if path in previews else 'source_archive' if path.suffix.lower()=='.zip' else 'editable_source' if path.suffix.lower() in SOURCES else 'report' if path.suffix.lower() in REPORTS else 'export'
        sources|=role in ('editable_source','source_archive');exports|=role=='export'
        entries.append({'path':str(path),'role':role,'format':path.suffix.lstrip('.') or 'file',
            'open_with':'Applicazione compatibile con il formato; apertura non verificata',
            'editability':'File salvato durante l’incarico; completezza e modificabilità da verificare',
            'reopen':{'status':'not_run','evidence':note},'limitations':[note]})
    original=output/'handoff.json'
    if original.is_symlink():raise ValueError('Manifest non valido')
    if original.is_file():
        (output/'work').mkdir(exist_ok=True)
        backup=output/'work/handoff-before-early-delivery.json'
        if backup.is_symlink():raise ValueError('Backup non valido')
        shutil.copyfile(original,backup)
    value={'task':'Consegna anticipata dei file già prodotti','source_files':[],
        'output_files':[str(p) for p in files],'previews':[str(p) for p in previews],
        'checks':[{'name':'Verifica completa del prodotto','status':'not_run','evidence':note}],
        'warnings':[note],'delivery':{'source_status':'included' if sources else 'unavailable' if exports else 'not_applicable',
        'source_note':note,'files':entries}}
    original.write_text(json.dumps(value,ensure_ascii=False,indent=2))
    return value
