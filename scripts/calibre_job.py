#!/usr/bin/env python3
"""Trusted helper run by the pinned calibre-debug Python runtime, never model code."""
import json
import os
from pathlib import Path
import sys
import shutil
import subprocess


def check_css_without_webengine(sources,fix=False,disabled_rules=()):
    """Use the exact native rules/results, with Node instead of a GPU page."""
    from calibre.ebooks.oeb.polish.check.css import stylelint_js
    node=shutil.which('node')
    if not node:raise RuntimeError('Node necessario per le regole CSS native di Calibre')
    request={'scripts':stylelint_js(),'sources':sources,'fix':fix,'disabled_rules':list(disabled_rules)}
    result=subprocess.run([node,str(Path(__file__).with_name('calibre_css.cjs'))],
        input=json.dumps(request),capture_output=True,text=True,timeout=120)
    if result.returncode:raise RuntimeError('Controllo CSS nativo non riuscito: '+result.stderr[-1500:])
    values=json.loads(result.stdout)
    if not isinstance(values,list) or len(values)!=len(sources):raise ValueError('Risposta CSS nativa incompleta')
    return values


def issue_record(error, warn_level):
    # Calibre calls DanglingLink a warning, but delivering a navigation target
    # which does not exist breaks the publication's actual behavior. Preserve
    # the native severity and expose the adapter's blocking policy separately.
    native_error = error.level > warn_level
    return {'rule':error.rule_id, 'severity':'error' if native_error else 'warning',
            'blocking':native_error or error.rule_id == 'DanglingLink',
            'file':error.name, 'line':error.line, 'message':str(error)}


def main():
    import calibre
    # The pinned checker uses detect_ncpus for both CSS pages and parser threads.
    calibre._ncpus = max(1, min(8, int(os.environ.get('RIGHAVEN_CPU_THREADS', '2'))))
    from calibre.ebooks.oeb.polish.container import get_container
    action, book, output = sys.argv[1:]
    container = get_container(book)
    opf = container.opf
    def values(name):
        return [str(v) for v in opf.xpath('//*[local-name()="' + name + '"]/text()')]
    value = {'path': book, 'format': Path(book).suffix[1:].upper(),
             'title': values('title'), 'authors': values('creator'), 'languages': values('language'),
             'spine': [{'file': name, 'linear': linear} for name, linear in container.spine_names],
             'resources': len(container.mime_map), 'files': sorted(container.mime_map)}
    if action == 'check':
        from calibre.ebooks.oeb.polish.check import css
        css.pool.check_css=check_css_without_webengine
        from calibre.ebooks.oeb.polish.check.main import run_checks
        from calibre.ebooks.oeb.polish.check.base import WARN
        issues = run_checks(container)
        value['issues'] = [issue_record(e, WARN) for e in issues]
        value['status'] = 'failed' if any(e['blocking'] for e in value['issues']) or not value['spine'] else 'passed'
        value['css_engine']='calibre-bundled-stylelint-node'
        value['note'] = 'Controllo strutturale nativo Calibre; non prova qualità editoriale, resa su lettori o conformità EPUBCheck.'
    Path(output).write_text(json.dumps(value, ensure_ascii=False, indent=2))
    close = getattr(container, 'close', None)
    if close:
        close()


if __name__ == '__main__':
    main()
