#!/usr/bin/env python3
"""Opt-in browser acceptance test against an isolated RigHaven deployment.

Credentials are environment variables. No HAR, trace, request bodies or keys
are recorded. --thread-url verifies and downloads an already completed test.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zipfile

from playwright.sync_api import expect, sync_playwright
from pypdf import PdfReader

PROMPT = ('Ho queste vendite e devo condividerle con un cliente. '
    'Prepara un foglio Excel modificabile con gli importi numerici e la formula del totale, '
    'poi una breve relazione in italiano sia Word sia PDF, con i risultati verificati. '
    'Usa i nomi vendite.xlsx, relazione.docx e relazione.pdf. '
    'Il lavoro deve essere essenziale e pronto da scaricare.')



def verify_team_ux(page, base_url, passed, snapshot):
    """UI-only checks; the read failure is deliberate, then retried against the real API."""
    page.goto(base_url + '/workspace/chats/new?settings=models', wait_until='domcontentloaded')
    expect(page.get_by_role('heading', name='Un solo modello per la squadra')).to_be_visible(timeout=30000)
    snapshot(page, '04-settings-one-place')
    page.get_by_role('link', name='Configura la squadra →').click()
    page.wait_for_url('**/workspace/harness', timeout=15000)
    expect(page.get_by_role('dialog')).to_have_count(0)
    frame = page.frame_locator('iframe[title="RigHaven"]')
    expect(frame.locator('#team-save')).to_be_enabled(timeout=15000)
    expect(frame.locator('#team-summary')).to_contain_text('Squadra pronta')
    passed('Impostazioni Modelli apre la configurazione unica e chiude la finestra')
    assert frame.get_by_role('combobox').count() == 2
    passed('Due soli menu visibili: servizio e modello della squadra')
    expect(frame.locator('#start-work')).to_be_in_viewport()
    passed('Accesso alla chat visibile accanto al salvataggio, senza cercarlo sotto la pagina')
    page.set_viewport_size({'width': 390, 'height': 844})
    assert frame.locator('html').evaluate('(e) => e.scrollWidth <= window.innerWidth')
    assert page.locator('html').evaluate('(e) => e.scrollWidth <= window.innerWidth')
    snapshot(page, '05-mobile-config')
    passed('Configurazione a 390 pixel senza scorrimento orizzontale')
    page.set_viewport_size({'width': 1440, 'height': 1100})
    def fail(route):
        route.abort('failed')
    page.route('**/harness/api/catalog', fail)
    try:
        page.reload(wait_until='domcontentloaded')
        frame = page.frame_locator('iframe[title="RigHaven"]')
        expect(frame.locator('#reload-config')).to_be_visible(timeout=15000)
        expect(frame.locator('#team-save')).to_be_disabled()
        expect(frame.locator('#status')).to_have_text('Connessione interrotta. Riprova tra poco.')
    finally:
        page.unroute('**/harness/api/catalog', fail)
    frame.locator('#reload-config').click()
    expect(frame.locator('#team-save')).to_be_enabled(timeout=15000)
    expect(frame.locator('#team-summary')).to_contain_text('Squadra pronta')
    snapshot(page, '06-config-retry')
    passed('Errore di lettura simulato: modulo protetto e riprova con risposta reale')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:2026')
    parser.add_argument('--output', type=Path, default=Path('reports/uat-browser'))
    parser.add_argument('--initialize-admin', action='store_true')
    parser.add_argument('--settings-only', action='store_true', help='Verifica configurazione, navigazione, mobile e riprova senza chiamate LLM')
    parser.add_argument('--thread-url', help='Riapre una conversazione completata e prova i download senza nuove chiamate LLM')
    parser.add_argument('--timeout', type=int, default=1800)
    args = parser.parse_args()
    args.base_url = args.base_url.rstrip('/')
    if args.thread_url and urlsplit(args.thread_url).netloc != urlsplit(args.base_url).netloc:
        parser.error('--thread-url deve appartenere all’istanza di collaudo')
    required = ['UAT_EMAIL', 'UAT_PASSWORD'] + ([] if args.thread_url or args.settings_only else ['DEEPSEEK_API_KEY'])
    if any(not os.getenv(name) for name in required):
        parser.error('Impostare ' + ', '.join(required) + ' nell’ambiente')
    args.output.mkdir(parents=True, exist_ok=True)
    report = {'base_url': args.base_url, 'cases': [], 'network': [], 'downloads': []}
    def passed(name):
        report['cases'].append({'name': name, 'status': 'passed'})
        print('PASS:', name, flush=True)
    def snapshot(page, name):
        page.screenshot(path=str(args.output / (name + '.png')), full_page=True, timeout=20000)
    def save_report():
        (args.output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    try:
        with tempfile.TemporaryDirectory(prefix='skill-uat-browser-') as profile, sync_playwright() as p:
            options = {'headless': True, 'viewport': {'width': 1440, 'height': 1100}, 'accept_downloads': True}
            if os.getenv('UAT_HTTP_PASSWORD'):
                options['http_credentials'] = {'username': os.getenv('UAT_HTTP_USER', 'admin'),
                                               'password': os.environ['UAT_HTTP_PASSWORD']}
            context = p.chromium.launch_persistent_context(profile, **options)
            page = context.new_page()
            page.on('response', lambda response: report['network'].append({
                'path': urlsplit(response.url).path, 'status': response.status,
                'method': response.request.method}) if '/api/' in response.url else None)
            created = False
            page.goto(args.base_url + '/workspace/chats/new', wait_until='domcontentloaded')
            page.locator('input[type=email], textarea').first.wait_for(timeout=30000)
            if page.locator('input[type=email]').count():
                page.locator('input[type=email]').fill(os.environ['UAT_EMAIL'])
                page.locator('input[type=password]').first.fill(os.environ['UAT_PASSWORD'])
                if page.locator('#confirmPassword').count():
                    if not args.initialize_admin:
                        raise ValueError('Istanza non inizializzata: usare --initialize-admin solo sul proprio ambiente di prova')
                    created = True
                    page.locator('#confirmPassword').fill(os.environ['UAT_PASSWORD'])
                    page.get_by_role('button', name='Create Admin Account', exact=True).click()
                    page.wait_for_url('**/workspace**', timeout=30000)
                    passed('Creazione del primo account amministratore')
                    context.clear_cookies()
                    page.goto(args.base_url + '/workspace/chats/new', wait_until='domcontentloaded')
                    page.locator('input[type=email]').fill(os.environ['UAT_EMAIL'])
                    page.locator('input[type=password]').first.fill(os.environ['UAT_PASSWORD'])
                    page.get_by_role('button', name='Sign In', exact=True).click()
                else:
                    page.get_by_role('button', name='Sign In', exact=True).click()
                page.wait_for_url('**/workspace**', timeout=30000)
            passed('Accesso utente dal browser')
            if created:
                page.wait_for_url('**/workspace/harness', timeout=30000)
                passed('Primo accesso guidato automaticamente alla configurazione della squadra')
            if args.settings_only:
                verify_team_ux(page, args.base_url, passed, snapshot)
                report['passed'] = True
                context.close()
                return 0
            if not args.thread_url:
                page.goto(args.base_url + '/workspace/harness', wait_until='domcontentloaded')
                frame = page.frame_locator('iframe[title="RigHaven"]')
                expect(frame.locator('#team-engine')).to_have_value('deepseek', timeout=30000)
                expect(frame.locator('#team-summary')).to_have_text(re.compile(r'^(Squadra pronta|Collega un servizio)'), timeout=30000)
                before = frame.locator('#team-summary').inner_text()
                frame.locator('#deepseek-key').fill('invalid-uat-key')
                frame.locator('#team-save').click()
                expect(frame.locator('#status')).to_have_text('Chiave DeepSeek rifiutata', timeout=40000)
                expect(frame.locator('#team-summary')).to_have_text(before)
                passed('Chiave errata rifiutata senza cambiare la squadra')
                frame.locator('#deepseek-key').fill(os.environ['DEEPSEEK_API_KEY'])
                frame.locator('#team-save').click()
                expect(frame.locator('#team-summary')).to_have_text(re.compile(r'^Squadra pronta'), timeout=40000)
                expect(frame.locator('#deepseek-key')).to_have_value('')
                passed('Un solo salvataggio collega la chiave e attiva la squadra')
                catalog = context.request.get(args.base_url + '/harness/api/catalog').json()
                report['team'] = catalog['team']
                assert set(catalog['effective_agents']) == {app['id'] for app in catalog['applications']}
                for identifier, settings in catalog['effective_agents'].items():
                    assert settings['engine'] == catalog['team']['engine'] == 'deepseek'
                    assert settings['model'] == catalog['team']['model']
                    assert 'skill-' + identifier in settings['skills']
                    assert 'skill-workspace' in settings['skills']
                assert os.environ['DEEPSEEK_API_KEY'] not in json.dumps(catalog)
                passed('Tutti gli specialisti ereditano il modello, con le proprie skills')
                page.reload(wait_until='domcontentloaded')
                frame = page.frame_locator('iframe[title="RigHaven"]')
                expect(frame.locator('#team-summary')).to_have_text(re.compile(r'^Squadra pronta'), timeout=15000)
                expect(frame.locator('#team-model')).to_have_value(catalog['team']['model'])
                expect(frame.locator('#deepseek-key')).to_have_value('')
                passed('Configurazione persistente e chiave non restituita al browser')
                frame.locator('#refresh-models').click()
                expect(frame.locator('#status')).to_have_text('Elenco aggiornato. Scegli il modello e salva la squadra.', timeout=40000)
                options = frame.locator('#team-model option').evaluate_all('(items) => items.map(o => o.value).filter(Boolean)')
                alternate = next((value for value in options if value != catalog['team']['model']), None)
                if alternate:
                    for model in (alternate, catalog['team']['model']):
                        frame.locator('#team-model').select_option(model)
                        frame.locator('#team-save').click()
                        expect(frame.locator('#status')).to_have_text('Squadra pronta. Modello applicato al coordinatore e a tutti gli specialisti.', timeout=40000)
                        updated = context.request.get(args.base_url + '/harness/api/catalog').json()
                        assert updated['team']['model'] == model
                        assert all(settings['model'] == model for settings in updated['effective_agents'].values())
                    passed('Cambio modello dal menu propagato agli specialisti senza reinserire la chiave')
                snapshot(page, '01-team-ready')
                verify_team_ux(page, args.base_url, passed, snapshot)
                frame = page.frame_locator('iframe[title="RigHaven"]')
                frame.locator('#start-work').click()
                page.locator('textarea').wait_for(timeout=30000)
                expect(page.get_by_role('button', name='RigHaven Harness', exact=True)).to_be_visible(timeout=15000)
                passed('Chat pronta con il modello della squadra, senza selezione manuale')
                sample = args.output / 'vendite-collaudo.csv'
                sample.write_text('Voce,Importo\nA,10\nB,20\nC,30\n')
                page.locator('input[type=file]').first.set_input_files(str(sample.resolve()))
                page.locator('textarea').fill(PROMPT)
                snapshot(page, '02-request')
                page.get_by_role('button', name='Submit', exact=True).click()
                page.wait_for_url(re.compile(r'/chats/(?!new)[^/]+$'), timeout=30000)
                passed('Caricamento CSV e invio richiesta')
                thread = page.url.rsplit('/', 1)[-1]
                deadline = time.monotonic() + args.timeout
                while time.monotonic() < deadline:
                    page.wait_for_timeout(2000)
                    # Passive observation only: the chat request is sent by the UI.
                    response = context.request.get(args.base_url + '/api/threads/' + thread + '/runs')
                    if response.ok:
                        runs = response.json()
                        if runs and runs[0]['status'] not in ('pending', 'running'):
                            report['run_status'] = runs[0]['status']
                            if runs[0]['status'] != 'success':
                                raise RuntimeError('Conversazione terminata con stato ' + runs[0]['status'])
                            break
                else:
                    raise TimeoutError('Timeout del collaudo utente')
                passed('Conversazione completata dal prodotto')
            else:
                page.goto(args.thread_url, wait_until='domcontentloaded')
            report['thread_url'] = page.url
            archive = page.get_by_role('button', name='Download current versions (3 files)', exact=True)
            expect(archive).to_be_visible(timeout=30000)
            snapshot(page, '03-delivered')
            with page.expect_download(timeout=60000) as pending:
                archive.click()
            download = pending.value
            downloaded = args.output / Path(download.suggested_filename).name
            download.save_as(downloaded)
            report['downloads'].append({'filename': downloaded.name, 'bytes': downloaded.stat().st_size})
            extracted = {}
            with zipfile.ZipFile(downloaded) as bundle:
                for suffix in ('.xlsx', '.docx', '.pdf'):
                    matches = [name for name in bundle.namelist() if name.endswith(suffix)]
                    if len(matches) != 1:
                        raise ValueError('Archivio senza un unico file ' + suffix)
                    expected = {'.xlsx': 'vendite.xlsx', '.docx': 'relazione.docx', '.pdf': 'relazione.pdf'}[suffix]
                    if Path(matches[0]).name != expected:
                        raise ValueError('Nome del prodotto diverso da quello richiesto: ' + Path(matches[0]).name)
                    content = bundle.read(matches[0])
                    extracted[suffix] = args.output / Path(matches[0]).name
                    extracted[suffix].write_bytes(content)
            passed('Download archivio con XLSX, DOCX e PDF dalla chat')
            link = page.locator('a[href*="/artifacts/"][href*=".xlsx"][href*="download=true"]').first
            with page.expect_download(timeout=30000) as pending:
                link.click()
            download = pending.value
            download.save_as(args.output / ('individual-' + Path(download.suggested_filename).name))
            passed('Download individuale XLSX')
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            numbers, formula_totals = [], []
            with zipfile.ZipFile(extracted['.xlsx']) as workbook:
                if workbook.testzip() is not None:
                    raise ValueError('XLSX corrotto')
                for name in workbook.namelist():
                    if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', name):
                        sheet = ET.fromstring(workbook.read(name))
                        for cell in sheet.findall('.//s:c', ns):
                            if cell.get('t') not in ('s', 'str', 'inlineStr'):
                                try:
                                    value = float(cell.findtext('s:v', namespaces=ns))
                                    numbers.append(value)
                                    formula = cell.findtext('s:f', namespaces=ns) or ''
                                    if 'SUM(' in formula.upper():
                                        formula_totals.append(value)
                                except (TypeError, ValueError):
                                    pass
            if not all(value in numbers for value in (10, 20, 30)) or 60 not in formula_totals:
                raise ValueError('XLSX senza dati numerici o formula con totale 60')
            passed('XLSX: importi numerici e formula con valore salvato 60')
            with zipfile.ZipFile(extracted['.docx']) as document:
                if document.testzip() is not None:
                    raise ValueError('DOCX corrotto')
                tree = ET.fromstring(document.read('word/document.xml'))
                docx_text = ' '.join(node.text or '' for node in tree.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
            pdf = PdfReader(extracted['.pdf'])
            pdf_text = '\n'.join(page.extract_text() or '' for page in pdf.pages)
            if not re.search(r'(?<!\d)60(?!\d)', docx_text) or not re.search(r'(?<!\d)60(?!\d)', pdf_text):
                raise ValueError('Totale 60 non trovato in DOCX/PDF')
            report['independent_checks'] = {'xlsx_numeric_values': [10, 20, 30],
                'xlsx_formula_cached_total': 60, 'pdf_pages': len(pdf.pages),
                'docx_contains_total': True, 'pdf_contains_total': True}
            passed('DOCX e PDF leggibili con totale 60')
            (args.output / 'conversation.txt').write_text(page.locator('body').inner_text())
            report['passed'] = True
            context.close()
    except Exception as error:
        message = str(error)
        for name in ('DEEPSEEK_API_KEY', 'UAT_PASSWORD', 'UAT_HTTP_PASSWORD'):
            if os.getenv(name):
                message = message.replace(os.environ[name], '[REDACTED]')
        report.update(passed=False, error=message)
        print('FAIL:', message, flush=True)
    finally:
        save_report()
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
