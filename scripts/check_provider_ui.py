#!/usr/bin/env python3
"""User-flow checks against declared API fixtures; real HTTP is covered separately."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

html=(Path(__file__).resolve().parents[1]/'righaven/index.html').read_text()
profiles={'coordinator':{'engine':'codex','model':'gpt-6.1-sol','ready':True},
          'squad':{'engine':'deepseek','model':'deepseek-chat','ready':True}}
connections={e:{'credentials_present':e!='openai'} for e in ('codex','gemini','deepseek','openai')}
saved=[]
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=['--no-sandbox'])
    page=browser.new_page(viewport={'width':390,'height':800})
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    def route(r):
        url=r.request.url
        if '/harness/api/catalog' in url:
            value={'team':profiles['coordinator'],'profiles':profiles,'connections':connections,'agents':{'blender':{'enabled':False},'freecad':{'enabled':True}},'applications':[{'id':'blender','name':'Blender','role':'3D'},{'id':'freecad','name':'FreeCAD','role':'CAD'}],'skills':[]}
        elif '/harness/api/team/models' in url:
            value={'models':['Acme/Model-X','Acme/Model-Y'] if r.request.method=='POST' else ['gpt-6.1-sol','deepseek-chat']}
        elif url.endswith('/harness/api/team'):
            body=r.request.post_data_json;saved.append(body)
            profile={'engine':body['engine'],'model':body['model'],'ready':True}
            if body['engine']=='openai':
                profile.update(base_url=body['base_url'],connection_id='a'*32)
                connections['openai']={'credentials_present':True,'base_url':body['base_url'],'connection_id':'a'*32}
            for target in ('coordinator','squad') if body['scope']=='both' else (body['scope'],):profiles[target]=dict(profile)
            value={'ok':True,'team':profiles['coordinator'],'profiles':profiles,'applied_to':body['scope'],'models':[]}
        elif url.endswith('/harness/api/runtime'):
            value={'settings':{'mode':'auto','cpus':1.5,'memory_mib':1536},'effective':{'cpus':1.5,'memory_mib':1536},'host':{'detected':True},'warning':''}
        else:r.fulfill(status=200,content_type='text/html',body=html);return
        r.fulfill(status=200,content_type='application/json',body=json.dumps(value))
    page.route('http://providers.test/**',route)
    page.goto('http://providers.test/harness')
    expect(page.locator('#team-summary')).to_contain_text('Coordinatore: OpenAI Codex')
    expect(page.locator('#team-summary')).to_contain_text('Squadra: DeepSeek')
    expect(page.get_by_role('link',name='Apri Capability Center')).to_have_attribute('href','/workspace/capabilities')
    expect(page.get_by_role('link',name='Apri Agents',exact=True)).to_have_attribute('href','/workspace/agents')
    expect(page.locator('#specialists input[type=checkbox]')).to_have_count(0)
    expect(page.locator('#specialists select')).to_have_count(0)
    expect(page.locator('#agents')).to_contain_text('Disabilitato nel Capability Center')

    page.locator('#team-scope').select_option('squad')
    expect(page.locator('#team-engine')).to_have_value('deepseek')
    page.locator('#team-engine').select_option('openai')
    expect(page.locator('#openai-fields')).to_be_visible()
    expect(page.locator('#account-fields')).to_be_hidden()
    page.locator('#openai-url').fill('https://provider.example/v1')
    page.locator('#openai-key').fill('fixture-private-browser-key')
    page.locator('#refresh-models').click()
    expect(page.locator('#team-model').locator('option',has_text='Acme/Model-X')).to_have_count(1)
    assert not saved
    page.locator('#custom-model').fill('Acme/Model-X')
    page.locator('#team-save').click()
    expect(page.locator('#status')).to_contain_text('la sola squadra')
    expect(page.locator('#openai-key')).to_have_value('')
    assert saved[-1]['scope']=='squad' and saved[-1]['model']=='Acme/Model-X'
    assert saved[-1]['base_url']=='https://provider.example/v1'
    assert saved[-1]['api_key']=='fixture-private-browser-key'
    assert profiles['coordinator']['engine']=='codex'
    assert 'fixture-private-browser-key' not in page.locator('body').inner_text()
    page.reload()
    page.locator('#team-scope').select_option('squad')
    expect(page.locator('#openai-url')).to_have_value('https://provider.example/v1')
    expect(page.locator('#custom-model')).to_have_value('Acme/Model-X')
    page.locator('#refresh-models').click()
    expect(page.locator('#status')).to_contain_text('Elenco aggiornato')
    page.locator('#team-model').select_option('Acme/Model-Y')
    expect(page.locator('#custom-model')).to_have_value('')
    page.locator('#team-save').click()
    expect(page.locator('#status')).to_contain_text('la sola squadra')
    assert 'api_key' not in saved[-1]
    assert saved[-1]['connection_id']=='a'*32
    page.locator('#team-scope').select_option('coordinator')
    expect(page.locator('#team-engine')).to_have_value('codex')
    expect(page.locator('#account-fields')).to_be_visible()
    page.locator('#team-save').click()
    expect(page.locator('#status')).to_contain_text('il solo coordinatore')
    assert profiles['squad']['model']=='Acme/Model-Y'
    page.locator('#team-scope').select_option('both')
    page.locator('#team-save').click()
    expect(page.locator('#status')).to_contain_text('coordinatore e squadra')
    assert profiles['coordinator']==profiles['squad']
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'mobile overflow'
    assert not errors,errors
    browser.close()
print('Provider UI OK: custom endpoint and manual ID, private key cleared, separate coordinator/team scopes, persistence and shared profile on mobile.')
