#!/usr/bin/env python3
"""Browser verification of the single resource settings panel, with declared API fixtures."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright, expect

html = (Path(__file__).resolve().parents[1] / 'righaven/index.html').read_text()
value = {'settings': {'mode': 'auto', 'cpus': 1.5, 'memory_mib': 1536},
         'effective': {'cpus': 3.5, 'memory_mib': 4096}, 'host': {'detected': True}, 'warning': ''}
saved = []
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 390, 'height': 740})
    errors = [];page.on('pageerror', lambda e: errors.append(str(e)))
    def route(r):
        path = r.request.url
        if path.endswith('/harness/api/runtime'):
            if r.request.method == 'PUT':
                change = r.request.post_data_json
                saved.append(change);value['settings'] = change
                value['effective'] = {'cpus': change['cpus'], 'memory_mib': change['memory_mib']}
            data = value
        elif path.endswith('/harness/api/catalog'):
            data = {'team': {'engine': 'deepseek', 'model': 'fixture', 'ready': True}, 'connections': {'deepseek': {'credentials_present': True}}, 'applications': [], 'agents': {}, 'skills': []}
        else:
            r.fulfill(status=200, content_type='text/html', body=html);return
        r.fulfill(status=200, content_type='application/json', body=json.dumps(data))
    page.route('http://runtime.test/**', route)
    page.goto('http://runtime.test/harness')
    expect(page.locator('#runtime-effective')).to_contain_text('3.5 CPU · 4096 MiB')
    expect(page.locator('#runtime-manual')).to_be_hidden()
    page.locator('#runtime-mode').select_option('manual')
    page.locator('#runtime-cpus').fill('2')
    page.locator('#runtime-memory').fill('3072')
    page.get_by_role('button', name='Salva risorse').click()
    expect(page.locator('#status')).to_contain_text('Risorse salvate')
    assert saved == [{'mode': 'manual', 'cpus': 2, 'memory_mib': 3072, 'model_wait_seconds': 0, 'max_workers':2}]
    page.reload()
    expect(page.locator('#runtime-cpus')).to_have_value('2')
    expect(page.locator('#runtime-memory')).to_have_value('3072')
    expect(page.locator('#runtime-mode')).to_have_value('manual')
    assert not errors, errors
    browser.close()
print('Runtime panel OK: automatic budget, one shared manual save, persisted on reload, mobile layout.')
