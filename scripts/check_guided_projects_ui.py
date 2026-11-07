#!/usr/bin/env python3
"""Browser contract: outcome intake -> saved native thread -> reload -> phase approval.

HTTP fixtures exercise real React overlays and the journey storage engine.
Native auth/ownership are separately checked by test_journey_routes in Gateway CI.
"""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import re
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import connections,journeys,projects,recipes,state
from playwright.sync_api import sync_playwright,expect


SKILLS=['skill-harness','skill-duckdb','skill-data-pipeline']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=Path(args.node_modules).resolve()
    import base64,os
    from cryptography.fernet import Fernet
    claims=base64.urlsafe_b64encode(json.dumps({'preferred_username':'marco@contoso.com'}).encode()).decode().rstrip('=')
    polls=[]
    def microsoft(url,data,timeout):
        class Reply:
            headers={'content-type':'application/json'}
            def __init__(self,code,body):self.status_code,self.body=code,body
            def json(self):return self.body
        if url.endswith('/devicecode'):return Reply(200,{'device_code':'D','user_code':'ABCD-EFGH','verification_uri':'https://microsoft.com/devicelogin','expires_in':900,'interval':1})
        if data.get('grant_type')=='refresh_token':return Reply(200,{'access_token':'AT','expires_in':3600})
        polls.append(1)
        return Reply(400,{'error':'authorization_pending'}) if len(polls)%2 else Reply(200,{'refresh_token':'RT-secret','id_token':'h.'+claims+'.s'})
    def azure(url,headers,timeout):
        class Reply:
            headers={'content-type':'application/json'}
            def __init__(self,body):self.status_code,self.body=200,body
            def json(self):return self.body
        if url.endswith('/subscriptions?api-version=2022-12-01'):return Reply({'value':[{'subscriptionId':'s1','displayName':'Produzione'}]})
        return Reply({'value':[{'name':'vendite/master'},{'name':'vendite/erp','location':'westeurope'},{'name':'vendite/hr','location':'westeurope'}]})
    with tempfile.TemporaryDirectory() as directory,patch.object(state,'STATE',Path(directory)/'state'),\
         patch.object(connections,'folder',side_effect=lambda user:(Path(directory)/'users'/user).mkdir(parents=True,exist_ok=True) or Path(directory)/'users'/user),\
         patch.dict(os.environ,{'RIGHAVEN_CREDENTIALS_KEY':Fernet.generate_key().decode()}),patch('httpx.post',side_effect=microsoft),patch('httpx.get',side_effect=azure),\
         patch('righaven.agents.owned',side_effect=lambda user,agent:{'id':agent}):
        root=Path(directory);workspace=root/'work';workspace.mkdir()
        (root/'fetch.ts').write_text('export const fetch=window.fetch.bind(window);')
        (root/'config.ts').write_text('export function getBackendBaseURL(){return ""}')
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:"it-IT"}}')
        (root/'router.ts').write_text('export function useRouter(){return {push:(url:string)=>{window.location.href=url}}}')
        (root/'uploads.ts').write_text('export async function uploadFiles(id:string,files:File[]){(window as any).uploaded=files.map(f=>f.name);return {files:files.map(f=>({virtual_path:"/mnt/user-data/uploads/"+f.name}))}}')
        (root/'threads.ts').write_text('export async function createThread(id:string){return window.fetch("/api/threads",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({thread_id:id})}).then(r=>r.json())}')
        entry='''import React from 'react';import{createRoot}from'react-dom/client';import Recipes from PAGE;import Connections from CONNECTIONS;import{ProjectJourney,useJourney}from PANEL;
function Journey(){const id=location.pathname.split('/').pop()!;const state=useJourney(id);const [resumes,setResumes]=React.useState(0);return <><ProjectJourney threadId={id} state={state} onContinue={()=>setResumes(n=>n+1)}/><output data-testid="resume-count">{resumes}</output></>;}
createRoot(document.getElementById('root')!).render(location.pathname.includes('/chats/')?<Journey/>:location.pathname==='/connections'?<Connections/>:<Recipes/>);'''
        (root/'entry.tsx').write_text(entry.replace('PAGE',json.dumps(str(repo/'frontend/recipes-page.tsx'))).replace('PANEL',json.dumps(str(repo/'frontend/project-journey.tsx')))
                                      .replace('CONNECTIONS',json.dumps(str(repo/'frontend/connections-page.tsx'))))
        aliases={'@/core/api/fetcher':str(root/'fetch.ts'),'@/core/config':str(root/'config.ts'),'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/i18n/ui-text':str(repo/'frontend/ui-text.ts'),'@/components/workspace/concept-map':str(repo/'frontend/concept-map.tsx'),'@/core/threads/api':str(root/'threads.ts'),'@/core/uploads/api':str(root/'uploads.ts'),'next/navigation':str(root/'router.ts')}
        build={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'app.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps(build)+')'],check=True)
        MATTER=[];HOST={};AGENTS=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,body,kind='application/json',code=200):
                self.send_response(code);self.send_header('Content-Type',kind);self.end_headers();self.wfile.write(body if isinstance(body,bytes) else body.encode())
            def do_GET(self):
                if self.path=='/api/harness/connections':return self.send(json.dumps({'connections':connections.listing('owner'),'kinds':list(connections.KINDS)}))
                if self.path=='/api/harness/access-catalog':return self.send(json.dumps({'providers':[]}))
                if self.path=='/api/harness/agents':
                    # The PC appears at the first refresh after the code was shown, as when RigHaven Agent pairs.
                    shown=list(AGENTS) if len(AGENTS)>1 else []
                    if AGENTS:AGENTS.append('seen')
                    return self.send(json.dumps({'agents':[a for a in shown if a!='seen'],'server':'https://righaven.example.com',
                    'download':'https://github.com/ggmm82/righaven/releases/latest/download/RigHaven-Agent-windows-x64.exe',
                    'android':'https://github.com/ggmm82/righaven/releases/latest/download/RigHaven-android.apk'}))
                if self.path=='/api/harness/host?agent=ag_0123456789ab':return self.send(json.dumps({'connected':True,'platform':'windows','allowed':True,
                    'actions':['bluetooth-scan','wifi-scan','com-list','net-scan','lan-devices','pc-devices','net-listen','traffic-capture']}))
                if self.path=='/api/harness/connections/discovery?agent=ag_0123456789ab':return self.send(json.dumps({'networks':['192.168.50.0/24'],'ports':[80,6668],
                    'allowed':True,'bluetooth':None,'serial':[],'wifi':None}))
                if self.path=='/api/harness/host':return self.send(json.dumps({'connected':True,'platform':'windows','matter':True,
                    'actions':['bluetooth-scan','wifi-scan','usb-list','usb-install','usb-attach','usb-detach','com-list','com-share','matter-enable','matter-disable','ble-inspect','wifi-provision','wifi-explore','pc-devices','net-listen','traffic-capture','lan-devices']}))
                if self.path.startswith('/api/harness/host/requests/'):
                    job=HOST[self.path.rsplit('/',1)[1]]
                    return self.send(json.dumps({'id':job['id'],'status':'done','result':job['result']}))
                if self.path=='/api/harness/matter':return self.send(json.dumps({'available':True,'reachable':True,'url':'ws://172.30.42.1:5580/ws','nodes':MATTER}))
                if self.path=='/api/harness/connections/discovery':return self.send(json.dumps({'networks':['192.168.1.0/24'],'ports':[80,1883,6668],'allowed':True,
                    'bluetooth':{'scanned_at':'2026-11-05T20:00:00Z','devices':[{'name':'OBDII','address':'00:1D:A5:68:98:8B','port':'','kind':'classic','paired':True,'hint':'obd'},
                        {'name':'WH-CH710N','address':'74:45:CE:2B:D4:8B','port':'','kind':'classic','paired':True,'connected':True,'hint':''},
                        {'name':'ATC_AABBCC','address':'A4:C1:38:AA:BB:CC','port':'','kind':'ble','paired':False,'hint':'','sensor':{'format':'ATC/pvvx','readings':{'temperature':{'value':23.1,'unit':'°C'},'humidity':{'value':50,'unit':'%'}}}},
                        {'name':'LED Strip','address':'38:A5:C9:3C:2E:9F','port':'','kind':'ble','paired':False,'hint':''},
                        {'name':'Vecchio','address':'11:22:33:44:55:66','port':'','kind':'ble','paired':False,'present':False,'hint':''}],'warnings':['devices: radio busy']},
                    'serial':[{'name':'COM5','label':'OBDII (COM5)','host':'172.18.0.1','port':41005,'hint':'obd'}],
                    'wifi':{'scanned_at':'x','networks':[{'ssid':'SmartLife-1A2B','bssid':'10:d5:61:00:00:02','open':True,'signal':64,'hint':'tuya'},
                                                         {'ssid':'tasmota-1A2B3C','bssid':'aa:bb:cc:dd:ee:09','open':True,'signal':70,'hint':'tasmota'},
                                                         {'ssid':'DaikinAP72288','bssid':'aa:bb:cc:dd:ee:07','open':False,'signal':85,'hint':'daikin'},
                                                         {'ssid':'CasaRossi','bssid':'aa:bb:cc:dd:ee:01','open':False,'signal':88,'hint':''}]}}))
                if self.path.startswith('/api/harness/recipes/editor/options'):
                    return self.send(json.dumps({'skills':[{'name':s,'description':'Metodo '+s,'kind':'method'} for s in SKILLS],
                                                 'environments':[{'id':'dati','name':'Dati e analisi','purpose':'Analisi','tools':['duckdb','jupyter','quarto','gridcraft'],'skills':[]}]}))
                if '/draft' in self.path:return self.send(json.dumps({'draft':recipes.draft(self.path.split('/')[4],'it','owner')}))
                if self.path.startswith('/api/harness/recipes'):return self.send(json.dumps({'recipes':recipes.catalog('it','owner'),'can_share':False}))
                if self.path.endswith('/harness-journey'):return self.send(json.dumps({'journey':journeys.view(workspace)}))
                if self.path=='/app.js':return self.send((root/'app.js').read_bytes(),'text/javascript')
                return self.send('<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><div id="root"></div><script src="/app.js"></script>','text/html')
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or '{}')
                if self.path=='/api/threads':return self.send(json.dumps({'thread_id':body['thread_id']}))
                if self.path=='/api/harness/host/requests':
                    answers={'usb-list':{'usbipd':True,'devices':[{'busid':'1-4','name':'CP210x USB to UART (COM3)','state':'Not shared','serial':True,'attached':False},
                                                                     {'busid':'2-1','name':'Realtek Bluetooth 4.2 Adapter','state':'Shared','serial':False,'attached':False,'pc_bluetooth':True}]},
                             'usb-detach':{'ok':True},
                             'usb-attach':{'ok':True,'ports':['/dev/ttyUSB0']},'com-list':{'ports':[{'name':'COM5','label':'OBDII (COM5)','bluetooth':True,'shared':False}]},
                             'com-share':{'ok':True},'bluetooth-scan':{'ok':True},'wifi-scan':{'ok':True,'networks':2},'wifi-provision':{'ok':True,'home':'CasaRossi'},'wifi-explore':{'ok':True,'ssid':'DaikinAP72288','address':'192.168.127.1','info':'ret=OK,type=aircon'},
                             'net-listen':{'devices':[{'address':'192.168.1.30','names':['Sonos-Cucina'],'services':['_spotify-connect._tcp.local'],'server':'Linux UPnP/1.0 Sonos/70.3','kinds':['mDNS','UPnP']}]},
                             'traffic-capture':{'ok':True,'packets':3,'download':True,'dns':['a1.tuyaeu.com'],'conversations':[{'local':'192.168.137.50','remote':'18.185.1.2','name':'a1.tuyaeu.com','proto':'TCP','port':8883,'packets':2,'bytes':150}]},
                             'lan-devices':{'devices':[{'address':'192.168.1.44','mac':'10:D5:61:AA:BB:CC','vendor':'Tuya'},{'address':'192.168.1.77','mac':'DA:A1:19:00:00:01','private_mac':True}]},
                             'pc-devices':{'devices':[{'class':'Ports','name':'CP210x USB to UART (COM3)','bus':'usb','ok':True,'vidpid':'10c4:ea60','busid':'1-4'},
                                                      {'class':'USB','name':'Hub USB generico','bus':'usb','ok':True,'vidpid':'05e3:0610'},
                                                      {'class':'Other','name':'SAMSUNGDEVICE','bus':'bluetooth','ok':False},
                                                      {'class':'Keyboard','name':'Tastiera PS/2 standard','bus':'internal','ok':True}]},
                             'ble-inspect':{'name':'LED Strip','services':[{'uuid':'0000180a-0000-1000-8000-00805f9b34fb','characteristics':[{'uuid':'00002a29-0000-1000-8000-00805f9b34fb','properties':['Read'],'value':'4c4544','text':'LED'}]},
                                                                            {'uuid':'0000ffe0-0000-1000-8000-00805f9b34fb','characteristics':[{'uuid':'0000ffe1-0000-1000-8000-00805f9b34fb','properties':['WriteWithoutResponse','Notify']}]}]}}
                    identifier='%032x'%(len(HOST)+1)
                    HOST[identifier]={'id':identifier,'action':body['action'],'args':body['args'],'agent':body.get('agent'),'result':answers[body['action']]}
                    return self.send(json.dumps({'id':identifier,'status':'queued'}))
                if self.path=='/api/harness/matter/commission':
                    assert body=={'code':'3497-011-2332'},body
                    MATTER.append({'node_id':5,'available':True,'name':'Lampada studio','vendor':'IKEA','product':'TRADFRI','readings':{'on':{'value':False,'endpoint':1}},'switchable':[1]})
                    return self.send(json.dumps(MATTER[-1]))
                if self.path=='/api/harness/matter/nodes/5/command':
                    assert body=={'endpoint':1,'command':'On'},body
                    MATTER[-1]['readings']['on']['value']=True
                    return self.send(json.dumps({'node_id':5,'endpoint':1,'command':'On'}))
                if self.path=='/api/harness/connections/discovery/explore':
                    assert body=={'address':'192.168.1.44'},body
                    return self.send(json.dumps({'address':'192.168.1.44','ports':[80,6668],'name':'','title':'Smart IR','kind':'tuya','label':'Tuya / Smart Life','suggestion':{'protocol':'tuya','port':6668}}))
                if self.path=='/api/harness/agents/pairings':
                    assert body=={'name':'PC di casa'},body
                    AGENTS.append({'id':'ag_0123456789ab','name':'PC di casa','platform':'windows','version':'1.0.0','online':True,'networks':['192.168.50.0/24']})
                    return self.send(json.dumps({'code':'ABCDE-FGHJK','expires_in':600}))
                if self.path=='/api/harness/connections/discovery' and body.get('agent'):
                    assert body=={'network':'192.168.50.0/24','agent':'ag_0123456789ab'},body
                    return self.send(json.dumps({'network':body['network'],'ports':[80,6668],'devices':[{'address':'192.168.50.20','ports':[80],'name':'','kind':'web','label':'Termostato','suggestion':{'protocol':'http','port':80}}]}))
                if self.path=='/api/harness/connections/discovery':
                    assert body=={'network':'192.168.1.0/24'},body
                    from righaven.device_discovery import identify
                    return self.send(json.dumps({'network':body['network'],'ports':[80,1883,6668],'devices':[{'address':'192.168.1.44','ports':[6668],'name':'','kind':'tuya',**{k:v for k,v in identify('192.168.1.44',[6668]).items() if k!='kind'}}]}))
                if self.path=='/api/harness/connections':return self.send(json.dumps(connections.save('owner',body)))
                if self.path.endswith('/sign-in'):return self.send(json.dumps(connections.sign_in('owner',self.path.split('/')[4])))
                if self.path.endswith('/sign-in/poll'):return self.send(json.dumps(connections.complete_sign_in('owner',self.path.split('/')[4])))
                if self.path.endswith('/databases'):return self.send(json.dumps(connections.databases('owner',self.path.split('/')[4])))
                if self.path.endswith('/approach'):return self.send(json.dumps({'journey':journeys.simplify(workspace,body['expected_revision'])}))
                if self.path.endswith('/decision'):
                    value=(journeys.decide_many(workspace,body['stage_ids'],body['action'],body['expected_revision'],body['note']) if body.get('stage_ids')
                           else journeys.decide(workspace,body['stage_id'],None,body['expected_revision'],body['note'],body['action']));return self.send(json.dumps({'journey':value}))
                if self.path=='/api/harness/recipes':
                    return self.send(json.dumps({'recipe':recipes.card(recipes.create('owner',{k:v for k,v in body.items() if k!='expected_revision'},SKILLS),'it','owner')}))
                return self.send('{}',code=404)
            def do_PUT(self):
                body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
                if self.path.startswith('/api/harness/connections/'):return self.send(json.dumps(connections.save('owner',body,self.path.split('/')[4])))
                value=journeys.start(workspace,body['recipe_id'],body['answers'],body['expected_revision'],journeys.definition(body['recipe_id'],'owner'),mode=body.get('mode','complete'));return self.send(json.dumps({'journey':value}))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(args=['--no-sandbox'])
                for width in (1200,390):
                    # Each viewport gets an independent workflow fixture.
                    for name in ('journey.json','project.json'):(workspace/'.righaven-project'/name).unlink(missing_ok=True)
                    page=browser.new_page(viewport={'width':width,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/recipes')
                    page.get_by_test_id('recipe-data-pipeline').get_by_role('button',name='Usa questa ricetta',exact=True).click()
                    page.locator('input[name=approach]').nth(1).check()
                    page.get_by_label('Cosa vuoi realizzare? Descrivilo con parole tue.',exact=True).fill('Dai documenti al catalogo, ai dati sintetici e al report vendite')
                    documents=page.get_by_test_id('intake-documents')
                    expect(documents).to_contain_text('Per questa ricetta servono')
                    documents.locator('input[type=file]').set_input_files([{'name':'schema.sql','mimeType':'text/plain','buffer':b'CREATE TABLE ordini (id INT PRIMARY KEY);'}])
                    expect(documents).to_contain_text('schema.sql')
                    documents.get_by_label('Link a documentazione esterna (uno per riga)').fill('https://example.com/dizionario-dati')
                    page.get_by_role('button',name='Avanti',exact=True).click()
                    expect(page.get_by_test_id('intake-connections')).to_contain_text('Nessuna connessione registrata')
                    page.get_by_role('button',name='Rivedi e avvia',exact=True).click()
                    page.get_by_role('button',name='Crea progetto guidato',exact=True).click()
                    page.wait_for_url('**/workspace/chats/*')
                    notes=journeys.view(workspace)['answers']['notes']
                    assert '/mnt/user-data/uploads/schema.sql' in notes and 'https://example.com/dizionario-dati' in notes, notes
                    card=page.get_by_test_id('journey-card');panel=page.get_by_test_id('project-journey');expect(panel).to_be_visible()
                    expect(panel).to_contain_text('Pipeline dati end-to-end')
                    panel.get_by_role('button',name='Tutte le fasi',exact=True).click()
                    expect(card).to_contain_text('senza connessioni reali')
                    page.reload();expect(panel).to_be_visible()
                    projects.create_plan(workspace,'Catalogo',[{'id':'catalog','agent':'workspace','goal':'Read docs','depends_on':[]}])
                    artifact=workspace/'catalog.md';artifact.write_text('Schema and documented relationships')
                    plan=workspace/'.righaven-project'/'project.json';value=json.loads(plan.read_text())
                    value['steps'].append({'id':'review','agent':'workspace','goal':'Revisione indipendente','status':'completed','purpose':'review','depends_on':[],
                                           'attempts':[{'status':'completed','finished_at':'2999-01-01T00:00:00+00:00'}]});state.atomic_json(plan,value)
                    current=journeys.view(workspace);journeys.record(workspace,'understand',[str(artifact)],['catalog'],'Catalogo con provenienza pronto per la revisione',current['revision'])
                    page.reload()
                    decision=page.get_by_test_id('journey-decision')
                    expect(decision).to_contain_text('Tocca a te')
                    expect(decision.get_by_role('link',name='catalog.md')).to_be_visible()
                    expect(decision.get_by_role('button',name='Chiedi correzioni',exact=True)).to_be_disabled()
                    decision.get_by_role('button',name='Approva fase',exact=True).click()
                    progress=page.get_by_test_id('journey-progress')
                    expect(progress).to_contain_text('1/7');expect(decision).to_have_count(0)
                    expect(page.get_by_test_id('resume-count')).to_have_text('1')
                    # A coordinator proposal to skip waits for the owner; the owner skips from the card.
                    current=journeys.view(workspace);journeys.record(workspace,'design',[],[],'Per una demo con dati di esempio non serve una progettazione separata',current['revision'],propose_skip=True)
                    page.reload();expect(decision).to_contain_text('propone di saltare')
                    decision.get_by_role('button',name='Salta fase',exact=True).click()
                    expect(progress).to_contain_text('2/7')
                    page.reload();expect(progress).to_contain_text('2/7')
                    panel.get_by_role('button',name='Tutte le fasi',exact=True).click()
                    phases=page.get_by_test_id('journey-phase')
                    expect(phases.nth(1)).to_contain_text('Saltata')
                    expect(phases.nth(2)).to_contain_text('senza approvazione')
                    phases.nth(1).get_by_role('button',name='Riprendi questa fase',exact=True).click()
                    expect(progress).to_contain_text('1/7')
                    expect(panel.get_by_test_id('journey-goal')).to_contain_text('Dai documenti al catalogo')
                    # The team compares the goal with every phase and proposes the skips in one turn; one answer settles them.
                    current=journeys.view(workspace)
                    for stage in ('pipeline','package'):
                        current=journeys.record(workspace,stage,[],[],'Per una demo con dati di esempio non serve',current['revision'],propose_skip=True)
                    page.reload()
                    proposals=page.get_by_test_id('journey-proposals')
                    expect(proposals).to_contain_text('propone di saltare 2 fasi')
                    proposals.get_by_role('button',name='Salta queste 2 fasi',exact=True).click()
                    expect(progress).to_contain_text('3/7');expect(proposals).to_have_count(0)
                    page.once('dialog',lambda dialog:dialog.accept())
                    panel.get_by_role('button',name='Semplifica il percorso conservando i file',exact=True).click()
                    expect(progress).to_contain_text('0/1')
                    assert journeys.view(workspace)['previous_paths']
                    assert artifact.read_text()=='Schema and documented relationships'
                    assert not errors,errors
                    page.close()
                for name in ('journey.json','project.json'):(workspace/'.righaven-project'/name).unlink(missing_ok=True)
                page=browser.new_page(viewport={'width':390,'height':900})
                page.goto(f'http://127.0.0.1:{server.server_port}/recipes')
                page.get_by_role('button',name='Usa questa ricetta',exact=True).first.click()
                expect(page.locator('input[name=approach]').first).to_be_checked()
                page.get_by_label('Cosa vuoi realizzare? Descrivilo con parole tue.',exact=True).fill('Una dashboard semplice con dati di esempio')
                page.get_by_role('button',name='Avanti',exact=True).click()
                page.get_by_role('button',name='Rivedi e avvia',exact=True).click()
                expect(page.get_by_test_id('guided-intake')).to_contain_text('risultato da provare')
                page.get_by_role('button',name='Crea progetto guidato',exact=True).click()
                page.wait_for_url('**/workspace/chats/*')
                expect(page.get_by_test_id('journey-progress')).to_contain_text('0/1')
                assert journeys.view(workspace)['mode']=='first_result'
                assert [s['id'] for s in journeys.view(workspace)['stages']]==['preview']
                page.close()
                # Personal Microsoft account: device code with MFA on Microsoft's page, then usable by SQL Server connections.
                page=browser.new_page(viewport={'width':390,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/connections')
                # PC peripherals: the page asks, the launcher on the PC lists, attaches and shares.
                pc=page.get_by_test_id('pc-devices')
                pc.get_by_role('button',name='Mostra periferiche USB',exact=True).click()
                pc.get_by_test_id('usb-list').get_by_role('button',name='Collega a RigHaven',exact=True).click()
                expect(pc.get_by_role('status')).to_have_text('Collegata: /dev/ttyUSB0')
                expect(pc.get_by_test_id('usb-list')).to_contain_text('collegata a RigHaven')
                expect(pc.get_by_role('button',name='Crea connessione su /dev/ttyUSB0',exact=True)).to_be_visible()
                expect(pc.get_by_test_id('usb-pc-bluetooth')).to_contain_text('Windows perde il Bluetooth')
                pc.get_by_test_id('usb-list').locator('li',has_text='Realtek').get_by_role('button',name='Esplora',exact=True).click()
                expect(pc.get_by_test_id('usb-details')).to_contain_text('adattatore Bluetooth del PC')
                assert pc.get_by_test_id('usb-list').get_by_role('button',name='Collega a RigHaven',exact=True).count()==0
                pc.get_by_test_id('usb-list').get_by_role('button',name='Restituisci a Windows',exact=True).click()
                expect(pc.get_by_role('status')).to_contain_text('Restituita a Windows')
                pc.get_by_role('button',name='Mostra tutti i dispositivi del PC',exact=True).click()
                every=pc.get_by_test_id('pc-all-devices')
                expect(every).to_contain_text('si può collegare a RigHaven (busid 1-4)')
                expect(every).to_contain_text('parte di un’altra periferica o hub')
                every.get_by_text('Bluetooth (1)').click()
                expect(every).to_contain_text('SAMSUNGDEVICE · Other · servizio del dispositivo associato senza driver')
                expect(every).to_contain_text('Debug wireless')
                pc.get_by_role('button',name='Mostra porte COM',exact=True).click()
                pc.get_by_test_id('com-list').get_by_role('button',name='Condividi con RigHaven',exact=True).click()
                expect(pc.get_by_test_id('com-list')).to_contain_text('condivisa')
                pc.get_by_test_id('com-list').get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Server della porta seriale',exact=True)).to_have_value('172.18.0.1')
                page.get_by_role('button',name='Annulla',exact=True).click()
                assert [j['action'] for j in HOST.values()]==['usb-list','usb-attach','usb-detach','pc-devices','com-list','com-share'],HOST
                assert list(HOST.values())[1]['args']=={'busid':'1-4'}
                page.get_by_test_id('device-discovery').get_by_role('button',name='Cerca dispositivi Bluetooth',exact=True).click()
                expect(page.get_by_test_id('device-discovery').get_by_role('button',name='Cerca dispositivi Bluetooth',exact=True)).to_be_enabled()
                assert list(HOST.values())[-1]['action']=='bluetooth-scan'
                wifi=page.get_by_test_id('wifi-discovery')
                expect(wifi.get_by_test_id('wifi-setup')).to_contain_text('SmartLife-1A2B · 64% · 🔓 aperta')
                expect(wifi.get_by_test_id('wifi-setup')).to_contain_text('DaikinAP72288 · 85% · 🔒 protetta')
                expect(wifi.get_by_test_id('wifi-setup')).to_contain_text('app Smart Life')
                wifi.get_by_role('button',name='Cerca reti Wi-Fi',exact=True).click()
                expect(wifi.get_by_role('button',name='Cerca reti Wi-Fi',exact=True)).to_be_enabled()
                assert list(HOST.values())[-1]['action']=='wifi-scan'
                # Matter: join a device shared from another app with its pairing code, switch it on, create a connection.
                matter=page.get_by_test_id('matter-devices')
                matter.get_by_label('Codice di abbinamento Matter',exact=True).fill('3497-011-2332')
                matter.get_by_role('button',name='Aggiungi dispositivo Matter',exact=True).click()
                nodes=matter.get_by_test_id('matter-nodes')
                expect(nodes).to_contain_text('Lampada studio · IKEA TRADFRI · nodo 5')
                expect(nodes).to_contain_text('on no')
                nodes.get_by_role('button',name='Accendi',exact=True).click()
                expect(nodes).to_contain_text('on sì')
                nodes.get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Protocollo',exact=True)).to_have_value('matter')
                expect(form.get_by_test_id('matter-hint')).to_contain_text('nodo 5')
                expect(form.get_by_label('Indirizzo (host o IP)',exact=True)).to_have_value('172.30.42.1')
                page.get_by_role('button',name='Annulla',exact=True).click()
                # Find devices without knowing their address: the PC's network, then a connection prefilled from the result.
                discovery=page.get_by_test_id('device-discovery')
                expect(discovery.get_by_label('Rete da cercare',exact=True)).to_have_value('192.168.1.0/24')
                expect(discovery.get_by_test_id('discovery-consent')).to_contain_text('80, 1883, 6668')
                expect(discovery.get_by_test_id('bluetooth-discovery')).to_contain_text('Periferiche del PC')
                expect(discovery.get_by_test_id('bluetooth-warning')).to_have_text('Ricerca dei dispositivi Bluetooth vicini e associati non riuscita: radio busy')
                expect(discovery.get_by_test_id('ble-readings')).to_have_text('ATC/pvvx: temperatura 23.1 °C · umidità 50 %')
                expect(discovery.get_by_role('link',name='Scarica lo storico delle letture (CSV)',exact=True)).to_have_attribute('href','/api/harness/connections/discovery/ble-history.csv')
                # A Tasmota in setup mode: the home Wi-Fi is given to it from the page, the password goes only to the launcher.
                setup=discovery.get_by_test_id('wifi-setup')
                assert setup.get_by_role('button',name='Porta nel Wi-Fi di casa',exact=True).count()==1  # not for Tuya
                setup.get_by_role('button',name='Porta nel Wi-Fi di casa',exact=True).click()
                form=setup.get_by_test_id('wifi-provision')
                expect(form.get_by_role('button',name='Configura',exact=True)).to_be_disabled()
                form.get_by_label('Password del Wi-Fi di casa',exact=True).fill('segreta123')
                form.get_by_role('button',name='Configura',exact=True).click()
                expect(discovery.get_by_test_id('wifi-provision-done')).to_contain_text('tasmota-1A2B3C si sta collegando a CasaRossi')
                sent=list(HOST.values())[-1]
                assert sent['action']=='wifi-provision' and sent['args']=={'ssid':'tasmota-1A2B3C','hint':'tasmota','password':'segreta123','home':''},sent
                # Devices that announce themselves, and a bounded recording of the PC's traffic.
                traffic=discovery.get_by_test_id('network-traffic')
                traffic.get_by_role('button',name='Ascolta la rete',exact=True).click()
                expect(traffic.get_by_test_id('announced')).to_contain_text('Sonos-Cucina · 192.168.1.30')
                traffic.get_by_label('Durata della registrazione',exact=True).select_option('30')
                traffic.get_by_role('button',name='Registra il traffico',exact=True).click()
                expect(traffic.get_by_test_id('traffic-summary')).to_contain_text('a1.tuyaeu.com (18.185.1.2)')
                expect(traffic.get_by_role('link',name='Scarica la registrazione (.pcapng, per Wireshark)')).to_have_attribute('href','/api/harness/connections/discovery/capture.pcapng')
                assert list(HOST.values())[-1]['args']=={'seconds':'30'}
                # Any Wi-Fi network the owner chooses: joined for a few seconds with the key typed here, read, then a connection.
                daikin=setup.locator('li',has_text='DaikinAP72288')
                daikin.get_by_role('button',name='Esplora',exact=True).click()
                explorer=daikin.get_by_test_id('wifi-explorer')
                explorer.get_by_label('Password della rete',exact=True).fill('0123456789')
                explorer.get_by_role('button',name='Collegati e leggi',exact=True).click()
                expect(explorer).to_contain_text('ret=OK,type=aircon')
                sent=list(HOST.values())[-1]
                assert sent['action']=='wifi-explore' and sent['args']=={'ssid':'DaikinAP72288','hint':'daikin','key':'0123456789'},sent
                explorer.get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Indirizzo (host o IP)',exact=True)).to_have_value('192.168.127.1')
                page.get_by_role('button',name='Annulla',exact=True).click()
                # A Bluetooth LE device: explored straight from the search, then a connection prefilled with its address.
                ble=discovery.get_by_test_id('bluetooth-discovery')
                remembered=ble.get_by_test_id('bluetooth-remembered')  # remembered by Windows, not heard now: in a closed list
                expect(remembered.locator('li',has_text='Vecchio')).to_be_hidden()
                remembered.get_by_text('Ricordati da Windows, non sentiti ora (1)').click()
                expect(remembered.locator('li',has_text='Vecchio')).to_be_visible()
                remembered.get_by_text('Ricordati da Windows, non sentiti ora (1)').click()
                expect(ble.locator('li',has_text='WH-CH710N')).to_contain_text('collegato ora')
                expect(ble.locator('li',has_text='OBDII')).to_contain_text('associato (non collegato ora)')
                led=ble.locator('li',has_text='LED Strip')
                led.get_by_role('button',name='Esplora',exact=True).click()
                ble.get_by_role('button',name='Leggi servizi e valori',exact=True).click()
                explorer=ble.get_by_test_id('ble-explorer')
                expect(explorer).to_contain_text('Produttore (2a29) · Read · LED')
                expect(explorer).to_contain_text('Seriale BLE (HM-10 e simili) (ffe0)')
                assert list(HOST.values())[-1]['action']=='ble-inspect' and list(HOST.values())[-1]['args']=={'address':'38:A5:C9:3C:2E:9F'}
                assert ble.locator('li',has_text='OBDII').get_by_role('button',name='Esplora',exact=True).count()==1  # every device, paired ones too
                led.get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Collegamento del dispositivo',exact=True)).to_have_value('bluetooth')
                expect(form.get_by_label('Indirizzo Bluetooth',exact=True)).to_have_value('38:A5:C9:3C:2E:9F')
                expect(form.get_by_label('Nome',exact=True)).to_have_value('LED Strip')
                page.get_by_role('button',name='Annulla',exact=True).click()
                discovery.get_by_role('button',name='Cerca in questa rete',exact=True).click()
                results=discovery.get_by_test_id('discovery-results')
                expect(results).to_contain_text('Tuya / Smart Life · 192.168.1.44')
                expect(results).to_contain_text('MAC 10:D5:61:AA:BB:CC (Tuya)')
                expect(results).to_contain_text('Telefono, tablet o PC (indirizzo MAC privato) · 192.168.1.77 · nessuna porta aperta')
                tuya=results.locator('li',has_text='192.168.1.44')
                tuya.get_by_role('button',name='Esplora',exact=True).click()
                expect(results.get_by_test_id('net-explorer')).to_contain_text('«Smart IR»')
                expect(results.get_by_test_id('net-explorer')).to_contain_text('Porte che rispondono: 80, 6668')
                expect(results).to_contain_text('local key')
                tuya.get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Indirizzo (host o IP)',exact=True)).to_have_value('192.168.1.44')
                expect(form.get_by_label('Protocollo',exact=True)).to_have_value('tuya')
                expect(form.get_by_test_id('tuya-hint')).to_contain_text('ID virtuale')
                expect(form.get_by_label('Versione del protocollo',exact=True)).to_have_value('3.3')
                page.get_by_role('button',name='Annulla',exact=True).click()
                # A Windows COM port shared by RigHaven.exe serial (Bluetooth OBD-II adapter): a raw TCP serial connection.
                shared=page.get_by_test_id('shared-serial')
                expect(shared).to_contain_text('OBDII (COM5) · adattatore OBD-II')
                shared.get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Tipo di server seriale',exact=True)).to_have_value('socket')
                expect(form.get_by_label('Server della porta seriale',exact=True)).to_have_value('172.18.0.1')
                page.get_by_role('button',name='Annulla',exact=True).click()
                # A device attached to this machine: with no device offered, the form says how to offer one
                # and cannot be saved; a one-letter or capitalised ID is saved in its normalised form.
                # New connection to a service: where it is first. The internet offers no serial or Bluetooth service.
                chooser=page.get_by_test_id('new-connection')
                expect(chooser.get_by_label('Dove si trova il servizio',exact=True)).to_have_value('cloud')
                expect(chooser.get_by_test_id('new-serial')).to_have_count(0)
                expect(chooser.get_by_test_id('new-entra')).to_have_count(1)
                chooser.get_by_label('Dove si trova il servizio',exact=True).select_option('server')
                expect(chooser.get_by_test_id('new-bluetooth')).to_have_count(1)
                expect(chooser.get_by_test_id('new-entra')).to_have_count(0)
                chooser.get_by_test_id('new-device').click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Dove si trova il servizio',exact=True)).to_have_value('server')
                form.get_by_label('Nome',exact=True).fill('UsbRW')
                form.get_by_label('ID (facoltativo)',exact=True).fill('A')
                expect(form.get_by_test_id('connection-id-hint')).to_contain_text('Sarà salvato come a')
                form.get_by_label('Collegamento del dispositivo',exact=True).select_option('local')
                expect(form.get_by_test_id('no-local-devices')).to_contain_text('Mostra periferiche USB')
                expect(form.get_by_role('button',name='Salva',exact=True)).to_be_disabled()
                form.get_by_label('Collegamento del dispositivo',exact=True).select_option('network')
                form.get_by_label('Indirizzo (host o IP)',exact=True).fill('192.168.1.40')
                form.get_by_role('button',name='Salva',exact=True).click()
                expect(page.get_by_test_id('connections-server').get_by_test_id('connection-a')).to_contain_text('UsbRW')
                assert connections.listing('owner')[0]['id']=='a'
                connections.delete('owner','a')
                page.reload()
                page.get_by_role('button',name='Nuova: Microsoft Entra ID',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Tipo di accesso',exact=True)).to_have_value('user')
                expect(form.get_by_label('Segreto client',exact=False)).to_have_count(0)
                form.get_by_label('Nome',exact=True).fill('Il mio account')
                form.get_by_role('button',name='Salva',exact=True).click()
                row=page.get_by_test_id('connection-il-mio-account')
                expect(row).to_contain_text('Accesso Microsoft da completare')
                row.get_by_role('button',name='Accedi con Microsoft',exact=True).click()
                signing=row.get_by_test_id('microsoft-sign-in')
                expect(signing).to_contain_text('ABCD-EFGH')
                expect(signing.get_by_role('link',name='https://microsoft.com/devicelogin')).to_be_visible()
                expect(signing).to_contain_text('Accesso completato: marco@contoso.com',timeout=10000)
                expect(row).to_contain_text('Account marco@contoso.com')
                assert 'RT-secret' not in json.dumps(connections.listing('owner'))
                # SQL Server with my Microsoft account: paste the connection string, sign in, pick the database from the list.
                page.get_by_role('button',name='Nuova: SQL Server / Azure SQL / Fabric',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Autenticazione',exact=True)).to_have_value('microsoft')
                form.get_by_label('Nome',exact=True).fill('Vendite Azure')
                form.get_by_label('Server, URL o stringa di connessione',exact=True).fill('Server=tcp:vendite.database.windows.net,1433;Initial Catalog=;User ID=marco@contoso.com;Encrypt=True;')
                form.get_by_label('Utente (email dell’account Microsoft)',exact=True).fill('marco@contoso.com')
                form.get_by_label('Confermo che l’account ha solo permessi di lettura').check()
                form.get_by_role('button',name='Salva',exact=True).click()
                sql=page.get_by_test_id('connection-vendite-azure')
                expect(sql).to_contain_text('vendite.database.windows.net:1433')
                expect(sql.get_by_role('button',name='Elenca database',exact=True)).to_be_disabled()
                sql.get_by_role('button',name='Accedi con Microsoft',exact=True).click()
                expect(sql.get_by_test_id('microsoft-sign-in')).to_contain_text('Accesso completato: marco@contoso.com',timeout=10000)
                sql.get_by_role('button',name='Elenca database',exact=True).click()
                listing=sql.get_by_test_id('database-list')
                expect(listing).to_contain_text('erp');expect(listing).not_to_contain_text('master')
                listing.get_by_role('listitem').filter(has_text='erp').get_by_role('button',name='Usa questo database').click()
                expect(sql).to_contain_text('vendite.database.windows.net:1433 / erp')
                assert connections._read('owner','vendite-azure')['refresh_token']=='RT-secret','choosing the database keeps the sign-in'
                # RigHaven Agent: pair a PC with a code, act on it, search its home network and connect a device through it.
                agents=page.get_by_test_id('agents')
                agents.get_by_label('Nome del PC da collegare',exact=True).fill('PC di casa')
                agents.get_by_role('button',name='Collega un PC',exact=True).click()
                pairing=agents.get_by_test_id('agent-pairing')
                expect(pairing.get_by_test_id('android-download').get_by_role('link')).to_have_attribute('href','https://github.com/ggmm82/righaven/releases/latest/download/RigHaven-android.apk')
                expect(pairing).to_contain_text('https://righaven.example.com')
                expect(pairing).to_contain_text('ABCDE-FGHJK')
                expect(pairing).to_contain_text('«PC di casa» è collegato',timeout=10000)
                agents.get_by_label('Agisci sul PC',exact=True).select_option('ag_0123456789ab')
                discovery=page.get_by_test_id('device-discovery')
                expect(discovery.get_by_label('Rete da cercare',exact=True)).to_have_value('192.168.50.0/24')
                discovery.get_by_role('button',name='Cerca in questa rete',exact=True).click()
                found=discovery.get_by_test_id('discovery-results')
                expect(found).to_contain_text('Termostato · 192.168.50.20')
                found.locator('li',has_text='Termostato').get_by_role('button',name='Crea connessione',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Dove si trova il servizio',exact=True)).to_have_value('ag_0123456789ab')  # the PC being worked on
                expect(form.get_by_label('Collegamento del dispositivo',exact=True)).to_have_value('network')
                expect(form.get_by_label('Indirizzo come lo vede quel PC (IP privato o nome interno)',exact=True)).to_have_value('192.168.50.20')
                form.get_by_role('button',name='Salva',exact=True).click()
                onsite=page.get_by_test_id('connections-ag_0123456789ab')
                expect(onsite).to_contain_text('On premise · tramite PC di casa')
                expect(onsite.get_by_test_id('connection-termostato')).to_contain_text('HTTP · 192.168.50.20:80')
                saved=connections._read('owner','termostato')
                assert (saved['transport'],saved['agent'],saved['host']) == ('network','ag_0123456789ab','192.168.50.20'),saved
                # On-premise gateway: a SQL Server of the office network, reached through the same PC.
                chooser=page.get_by_test_id('new-connection')
                expect(chooser.get_by_label('Dove si trova il servizio',exact=True)).to_have_value('ag_0123456789ab')
                expect(chooser.get_by_test_id('new-serial')).to_contain_text('Porta COM / USB del PC')
                expect(chooser.get_by_test_id('new-network')).to_have_count(0)  # networks to map are scanned from the server
                chooser.get_by_role('button',name='Nuova: SQL Server / Azure SQL / Fabric',exact=True).click()
                form=page.get_by_test_id('connection-form')
                expect(form.get_by_label('Dove si trova il servizio',exact=True)).to_have_value('ag_0123456789ab')
                expect(form.get_by_label('Autenticazione',exact=True)).to_have_count(0)  # through an agent: user and password
                form.get_by_label('Nome',exact=True).fill('ERP ufficio')
                form.get_by_label('Server, URL o stringa di connessione',exact=True).fill('sql01.ufficio.local')
                form.get_by_label('Database',exact=True).fill('erp')
                form.get_by_label('Utente',exact=True).fill('lettore')
                form.get_by_label('Password',exact=True).fill('segreta-123')
                form.get_by_label('Confermo che l’account ha solo permessi di lettura').check()
                form.get_by_role('button',name='Salva',exact=True).click()
                expect(onsite.get_by_test_id('connection-erp-ufficio')).to_contain_text('sql01.ufficio.local:1433 / erp · lettore')
                saved=connections._read('owner','erp-ufficio')
                assert (saved['agent'],saved['authentication'],saved['host']) == ('ag_0123456789ab','password','sql01.ufficio.local'),saved
                assert not errors,errors
                page.close()
                # Recipe editor: the user composes skills, environment and phases into a new recipe, then starts it.
                page=browser.new_page(viewport={'width':1200,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}/recipes')
                concepts=page.get_by_test_id('concept-map');concepts.locator('summary').click()
                expect(concepts.get_by_test_id('concept-flow')).to_contain_text('incarico → squadra: ogni ruolo usa skill + ambiente')
                expect(concepts).to_contain_text('Ricetta · sei qui')
                expect(concepts.get_by_role('link',name='Ambiente')).to_have_attribute('href','/workspace/environments')
                page.get_by_role('button',name='Nuova ricetta',exact=True).click()
                editor=page.get_by_test_id('recipe-editor')
                editor.get_by_label('Nome della ricetta',exact=False).fill('Dashboard demo')
                editor.get_by_label('Che risultato produce',exact=False).fill('Una dashboard semplice con dati sintetici')
                editor.get_by_label('Quando conviene usarla',exact=False).fill('Per mostrare un’idea con dati di esempio')
                editor.get_by_label('Cosa si ottiene alla fine',exact=False).fill('Dashboard HTML con i sorgenti')
                editor.get_by_label('Allegati necessari (se servono)',exact=False).fill('Elenco degli indicatori')
                editor.get_by_role('button',name='Avanti',exact=True).click()
                editor.get_by_label('Nome fase 1',exact=True).fill('Indicatori')
                editor.get_by_label('Risultato fase 1',exact=True).fill('Misure e dimensioni concordate')
                editor.get_by_role('button',name='Aggiungi fase',exact=True).click()
                editor.get_by_label('Nome fase 2',exact=True).fill('Dashboard')
                editor.get_by_label('Risultato fase 2',exact=True).fill('Report consultabile')
                expect(editor.get_by_test_id('recipe-phase').nth(1).get_by_label('Mi fermo per l’approvazione')).not_to_be_checked()
                editor.get_by_role('button',name='Avanti',exact=True).click()
                editor.get_by_label('Dati e analisi',exact=False).check()
                expect(editor.get_by_test_id('recipe-tools')).to_contain_text('duckdb, jupyter')
                editor.get_by_text('Cambia le competenze (facoltativo)',exact=True).click()
                editor.get_by_label('duckdb',exact=False).check()
                editor.get_by_role('button',name='Avanti',exact=True).click()
                expect(editor.get_by_test_id('recipe-preview')).to_contain_text('Indicatori — Misure e dimensioni concordate')
                editor.get_by_role('button',name='Salva ricetta',exact=True).click()
                mine=page.locator('[data-testid^="recipe-dashboard-demo"]')
                expect(mine).to_contain_text('tua')
                expect(mine.get_by_test_id(re.compile('recipe-blocks-'))).to_contain_text('duckdb')
                expect(mine).to_contain_text('automatica')
                mine.get_by_role('button',name='Duplica',exact=True).click()
                expect(page.get_by_test_id('recipe-editor').get_by_label('Nome della ricetta',exact=False)).to_have_value('Copia di Dashboard demo')
                page.get_by_test_id('recipe-editor').get_by_role('button',name='Annulla',exact=True).click()
                assert not errors,errors
                page.close()
                browser.close()
            print('Guided UI OK: desktop/mobile, saved native thread, inline owner approval, skip/resume, personal Microsoft sign-in, recipe editor and duplicate')
        finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
