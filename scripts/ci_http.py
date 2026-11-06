"""Exercise the real RigHaven auth/CSRF middleware and RigHaven over the proxy."""
import http.cookiejar
import json
import os
import urllib.request
import urllib.error

base = 'http://127.0.0.1:2026'
passwords = urllib.request.HTTPPasswordMgrWithDefaultRealm()
passwords.add_password(None, base, 'admin', os.environ['RIGHAVEN_PASSWORD'])
cookies = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies),
                                    urllib.request.HTTPBasicAuthHandler(passwords))


def request(path, payload=None, method=None):
    headers = {'Origin': base, 'Content-Type': 'application/octet-stream' if isinstance(payload,bytes) else 'application/json'}
    for cookie in cookies:
        if cookie.name == 'csrf_token':
            headers['X-CSRF-Token'] = cookie.value
    data = payload if isinstance(payload,bytes) else None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with client.open(req, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as error:
        error.add_note(path + ': ' + error.read(2000).decode('utf-8', errors='replace'))
        raise


request('/api/v1/auth/initialize', {'email': 'harness-ci@example.com',
                                   'password': 'CiOnly-Strong-Login-P4ssword!78239'})
assert any(cookie.name == 'access_token' for cookie in cookies)
overview = request('/workspace')
assert b'From objective to outcome.' in overview and b'Build your toolbox' in overview
assert b'Tasks &amp; results' in overview or b'Tasks &amp;' in overview
assert b'righaven_core.tech' not in overview
# The chat welcome depends on browser-initialized composer state; ci_browser.mjs
# checks its visible heading after hydration instead of inspecting the SSR shell.
assert b'RigHaven' in request('/workspace/chats/new')
assert b'Deployment &amp; connections' in request('/workspace/cloud')
assert b'RigHaven' in request('/harness/')
# Native Agent management and managed capabilities must be available after login.
json.loads(request('/api/agents'))
skills = json.loads(request('/api/skills'))['skills']
assert any(s['name'] == 'skill-blender' and s['category'] == 'integrations' for s in skills)
assert len({s['name'] for s in skills}) == len(skills)
# Gallery activation must create a real native environment owned by this session.
activated = json.loads(request('/api/v1/gallery/packs/env-architecture-modeling-rig/activate', {}))
gallery_name = activated['installation']['native_name']
gallery_agent = json.loads(request('/api/agents/' + gallery_name))
assert 'skill-d2' in gallery_agent['skills'], gallery_agent
assert any(p['name'] == gallery_name for p in json.loads(request('/api/harness/environments'))['environments'])
request('/api/agents/' + gallery_name, method='DELETE')
for retired in ('auth/oauth/google', 'auth/recover'):
    try: request('/api/v1/cloud/' + retired, {'email':'unused@example.test','new_password':'must-not-change'})
    except urllib.error.HTTPError as error: assert error.code == 410, error
    else: raise AssertionError('Retired preview authentication remains enabled')
request('/api/agents', {'name':'ci-native-profile','description':'Native capability scope','skills':['skill-freecad']})
profile = json.loads(request('/api/agents/ci-native-profile'))
assert profile['skills'] == ['skill-freecad']
interfaces=json.loads(request('/api/harness/environments/ci-native-profile/editors'))['editors']
assert any(item['id']=='freecad' and not item['preload'] for item in interfaces),interfaces
request('/api/agents/ci-native-profile', method='DELETE')
# Custom environments are native Agents, not a duplicated purpose/skills store.
# Assert the actual page rather than a heading whose text depends on locale.
assert b'data-testid="environments-page"' in request('/workspace/environments')
assert b'data-testid="terminal-window"' in request('/terminal?environment=ci-custom-environment')  # Italian or English by locale
assert b'data-testid="editor-workspace"' in request('/edit?thread=ci-guided-project&session=fixture')
assert b'function' in request('/rh-terminal/xterm.js')
assert b'xterm' in request('/rh-terminal/xterm.css')
assert b'FitAddon' in request('/rh-terminal/addon-fit.js')
assert b'<!' in request('/rh-design/excalidraw/index.html')

environments=json.loads(request('/api/harness/environments'))
assert environments['dynamic'] and len(environments['presets'])>=9
assert environments['can_configure_resources']
monitor=environments['parallelism']['monitor']
assert set(monitor['active'])=={'worker','build','terminal','control','editor'}
assert set(monitor['waiting'])==set(monitor['active']) and monitor['editor_limit']==2
assert 'allocated_memory_mib' in monitor and 'observed_at' in monitor
# A recipe is a persisted owner-scoped project, not a prompt template.
request('/api/threads', {'thread_id':'ci-guided-project'})
guided='/api/threads/ci-guided-project/harness-journey'
journey=json.loads(request(guided, {'recipe_id':'data-pipeline','answers':{'goal':'Document the supplied schema and build a synthetic laboratory'},'expected_revision':0},method='PUT'))['journey']
assert journey['connections_optional'] and journey['current']=='understand'
assert json.loads(request(guided))['journey']['revision']==journey['revision']
assert any(p['id']=='claude' for p in json.loads(request('/api/harness/access-catalog'))['providers'])
# Exercise the editor through the real account, CSRF middleware and proxy.
import subprocess
owner=json.loads(request('/api/v1/auth/me'))['id']
subprocess.run(['docker','compose','exec','-T','gateway','python','-c',
    "import sys;from righaven_core.config.paths import get_paths;root=get_paths().sandbox_user_data_dir('ci-guided-project',user_id=sys.argv[1]);(root/'outputs').mkdir(parents=True,exist_ok=True);(root/'outputs/editor-probe.md').write_text('Original source')",owner],check=True)
files=json.loads(request('/api/threads/ci-guided-project/project-files?path=outputs'))
assert any(item['virtual_path']=='/mnt/user-data/outputs/editor-probe.md' and item['role']=='working_file' for item in files['entries']),files
editor_url='/api/threads/ci-guided-project/editors'
choices=json.loads(request(editor_url+'?path=/mnt/user-data/outputs/editor-probe.md'))['editors']
assert any(item['id']=='text' for item in choices),choices
draft=json.loads(request(editor_url,{'path':'/mnt/user-data/outputs/editor-probe.md','editor':'text'}))
draft_url=editor_url+'/'+draft['id']
assert request(draft_url+'/files/editor-probe.md')==b'Original source'
saved=json.loads(request(draft_url+'/files/editor-probe.md?expected_revision=0&entry=true',b'Edited source',method='PUT'))
assert saved['revision']==1 and request(draft_url+'/files/editor-probe.md')==b'Edited source'
revision=json.loads(request(draft_url+'/publish',{'expected_revision':1}))
assert revision['path'].startswith('/mnt/user-data/outputs/source-revisions/'),revision
assert json.loads(request(draft_url))['published_revision']==1
jupyter_draft=json.loads(request(editor_url,{'path':'/mnt/user-data/outputs/editor-probe.md','editor':'jupyter'}))
environment=json.loads(request(editor_url+'/'+jupyter_draft['id']+'/environment',{}))
registered=[p for p in json.loads(request('/api/harness/environments'))['environments'] if p['name']==environment['profile']]
assert len(registered)==1 and 'jupyter' in registered[0]['tools'],registered
assert registered[0]['deployment']['mode']=='on_demand' and registered[0]['deployment']['editor_for']=='jupyter'
assert json.loads(request(editor_url+'/'+jupyter_draft['id']))['environment_profile']==environment['profile']
again=json.loads(request(editor_url+'/'+jupyter_draft['id']+'/environment',{}));assert again==environment
assert json.loads(request('/api/harness/environments/'+environment['profile']+'/export'))['agent']['name']==environment['profile']
print('Editor environment registration OK: ordinary native Agent, same versions/configuration/export, owner-scoped idempotent attachment; no container started')
print('Authenticated editor workflow OK: capability discovery, private draft, raw save and explicit publication through the proxy')
request('/api/threads/ci-guided-project', method='DELETE')

# A single persisted policy backs both entry points; no restart or divergent settings.
resource_url='/api/harness/environments/resources/settings'
previous=json.loads(request(resource_url))['settings']
try:
    resource_change={**previous,'max_workers':3,'max_editors':1}
    saved=json.loads(request(resource_url,resource_change,method='PUT'))
    assert saved['settings']['max_workers']==3
    assert saved['settings']['max_editors']==1
    assert json.loads(request('/harness/api/runtime'))['settings']==saved['settings']
    assert json.loads(request('/api/harness/environments'))['parallelism']['monitor']['configured_limit']==3
    assert json.loads(request('/api/harness/environments'))['parallelism']['monitor']['editor_limit']==1
finally:
    request(resource_url,{**previous,'max_workers':previous.get('max_workers',2),'max_editors':previous.get('max_editors',2)},method='PUT')
live=json.loads(request('/api/harness/environments/resources/rebalance',{},method='POST'))
assert live['pending']==0 and 'updated' in live,live
print('Authenticated environment resources OK: shared persisted settings, live limit monitor and privileged live rebalancing')

definition={'name':'ci-custom-environment','display_name':'Custom CI','purpose':'Documented diagrams',
            'instructions':'Preserve editable sources','skills':['skill-d2','skill-quality-review'],'mode':'on_demand','ephemeral':False}
created=json.loads(request('/api/harness/environments',definition))
assert created['tools']==['d2'] and created['deployment']['mode']=='on_demand'
native=json.loads(request('/api/agents/ci-custom-environment'))
assert native['description']==definition['purpose'] and native['soul']==definition['instructions']
assert 'skill-d2' in native['skills']
request('/api/agents/ci-custom-environment',{'description':'Changed in native Agents'},method='PUT')
updated=next(p for p in json.loads(request('/api/harness/environments'))['environments'] if p['name']=='ci-custom-environment')
assert updated['purpose']=='Changed in native Agents'
exported=json.loads(request('/api/harness/environments/ci-custom-environment/export'))
assert exported['agent']['name']=='ci-custom-environment'
# Configuration restore and sharing use the real owner-scoped API and immutable preview.
history=json.loads(request('/api/harness/environments/ci-custom-environment/history'))['items']
assert history and history[0]['definition']['purpose']=='Documented diagrams'
restored_configuration=json.loads(request('/api/harness/environments/ci-custom-environment/restore/'+history[0]['id'],{},method='POST'))
assert restored_configuration['purpose']=='Documented diagrams'
sharing={'id':'ci-shared-environment','version':'1.0.0','title_en':'CI diagrams','description_en':'Editable diagrams',
         'title_it':'Diagrammi CI','description_it':'Diagrammi modificabili','revision':restored_configuration['revision']}
preview=json.loads(request('/api/harness/environments/ci-custom-environment/share',sharing))
assert preview['scope']=='instance'
published=json.loads(request('/api/harness/environments/ci-custom-environment/share',{**sharing,'confirm':True,'preview_hash':preview['preview_hash']}))
assert published['published'] and not published['pack']['verified']
assert 'skill-quality-review' in published['pack']['skills']
shared=json.loads(request('/api/v1/gallery/packs/ci-shared-environment/activate',{}))
assert 'skill-quality-review' in json.loads(request('/api/agents/'+shared['installation']['native_name']))['skills']
shared_profile=next(item for item in json.loads(request('/api/harness/environments'))['environments'] if item['name']==shared['installation']['native_name'])
assert shared_profile['deployment']['source_pack']['version']=='1.0.0'
request('/api/agents/'+shared['installation']['native_name'],method='DELETE')
publisher_comment=json.loads(request('/api/v1/gallery/packs/ci-shared-environment/feedback',{'version':'1.0.0','body':'Please share your experience'}))
assert publisher_comment['author_reply'] and publisher_comment['score'] is None
print('Authenticated environment lifecycle OK: history, restore, explicit preview, portable method activation and publisher discussion')

# The real authenticated API must prepare the actual selected runtime, not just save a flag.
definition.update(mode='preload',preload_tools=['d2'])
request('/api/harness/environments/ci-custom-environment',definition,method='PUT')
import time
for attempt in range(60):
    prepared=next(p for p in json.loads(request('/api/harness/environments'))['environments'] if p['name']=='ci-custom-environment')
    status=prepared['runtime']['status']
    if status=='ready':break
    assert status not in ('failed','invalid'), prepared['runtime']
    time.sleep(2)
assert status=='ready' and prepared['preloaded_tools']==['d2'],prepared['runtime']
# Regression: a clean first boot never reads persisted AgentConfig preloads.
# Recreate the container: restart alone cannot detect an ephemeral SQLite database.
from ci_environment_lifecycle import restart
before_restart=prepared
identity_before=json.loads(request('/api/v1/auth/me'))['id']
persistent_thread=json.loads(request('/api/threads',{'metadata':{'title':'Container recreation persistence'}}))['thread_id']
persistent_message='This checkpoint must survive replacing the Gateway container.'
request('/api/threads/'+persistent_thread+'/state',{'values':{'messages':[{'role':'user','content':persistent_message}]}})
restart(recreate=True)
assert json.loads(request('/api/v1/auth/me'))['id']==identity_before
assert json.loads(request('/api/threads/'+persistent_thread))['metadata']['title']=='Container recreation persistence'
recovered_state=json.loads(request('/api/threads/'+persistent_thread+'/state'))
assert any(message.get('content')==persistent_message for message in recovered_state['values']['messages']),recovered_state
restored=next(p for p in json.loads(request('/api/harness/environments'))['environments'] if p['name']=='ci-custom-environment')
assert restored['runtime']['status']=='ready',restored
assert restored['runtime']['id']==before_restart['runtime']['id'],restored
assert restored['runtime']['image_id']==before_restart['runtime']['image_id'],restored
assert restored['instructions']==definition['instructions'],restored
assert restored['revision']==before_restart['revision'],restored
print('Persistent container recreation OK: native AgentConfig instructions preserved, same ready Docker image reused, authenticated API available.')
def wait_for_terminal_cleanup(identifiers, timeout=20):
    """DELETE acknowledges cancellation; finished confirms container/resource cleanup."""
    pending=set(identifiers)
    deadline=time.monotonic()+timeout
    observed={}
    while pending and time.monotonic()<deadline:
        for identifier in list(pending):
            status=json.loads(request('/api/harness/environments/terminals/'+identifier+'/status'))
            observed[identifier]=status
            if status['finished']:
                assert not status.get('error'),status
                pending.remove(identifier)
        if pending:time.sleep(.1)
    assert not pending, {'message':'Terminal resources were not released','sessions':observed}


# Real interactive PTY through the authenticated proxy, not only browser fixtures.
import base64
terminal=json.loads(request('/api/harness/environments/ci-custom-environment/terminal',{},method='POST'))
terminal_base='/api/harness/environments/terminals/'+terminal['id']
try:
    request(terminal_base+'/input',{'text':"printf 'http-pty-%s\\n' ready\n"},method='POST')
    output=b'';cursor=0
    for _ in range(20):
        event=json.loads(request(terminal_base+'/status?after='+str(cursor)))
        output+=base64.b64decode(event['output_base64']);cursor=event['cursor']
        if b'http-pty-ready' in output:break
    assert b'http-pty-ready' in output,output[-2000:]
    request(terminal_base+'/resize',{'cols':100,'rows':35},method='POST')
    print('Authenticated HTTP terminal OK: separate page/assets routed to frontend; actual PTY input/output and resize passed')
finally:
    request(terminal_base,method='DELETE')
    wait_for_terminal_cleanup([terminal['id']])

# Per-window ownership and pending-start cancellation through real auth/CSRF.
import uuid
client_ids=[uuid.uuid4().hex,uuid.uuid4().hex]
owned=[json.loads(request('/api/harness/environments/ci-custom-environment/terminal',{'client_id':identifier},method='POST')) for identifier in client_ids]
assert owned[0]['id']!=owned[1]['id'],'Two windows unexpectedly share one terminal'
try:
    request('/api/harness/environments/terminal-clients/'+client_ids[0]+'/close',{},method='POST')
    for _ in range(40):
        closed=json.loads(request('/api/harness/environments/terminals/'+owned[0]['id']+'/status'))
        if closed['finished']:break
        time.sleep(.1)
    assert closed['finished'] and not closed.get('error'),closed
    other=json.loads(request('/api/harness/environments/terminals/'+owned[1]['id']+'/status'))
    assert not other['finished'] and not other['closing'],other
finally:
    for value in owned:request('/api/harness/environments/terminals/'+value['id'],method='DELETE')
    wait_for_terminal_cleanup([value['id'] for value in owned])
late=uuid.uuid4().hex
request('/api/harness/environments/terminal-clients/'+late+'/close',{},method='POST')
try:request('/api/harness/environments/ci-custom-environment/terminal',{'client_id':late},method='POST')
except urllib.error.HTTPError as error:assert error.code==409,error
else:raise AssertionError('A closed page allocated a new terminal')
print('Authenticated terminal lifecycle OK: legacy empty body, independent same-environment windows, scoped page close and pending-start cancellation.')

# Assignment software uses the very same terminal service and resource lane.
# Seed a controlled job in this isolated Compose candidate, never production.
import subprocess
assignment_job='rh-job-c1c1c1c1c1c1'
fixture_code="""
import sys
from righaven_core.config.paths import get_paths
from righaven import state,environment_runtime,assignment_environments
from righaven.progress import create_job,workspace_key
user,thread,job,environment=sys.argv[1:]
workspace=get_paths().sandbox_user_data_dir(thread,user_id=user);workspace.mkdir(parents=True,exist_ok=True)
(workspace/'terminal-project-probe.txt').write_text('project-probe\\n')
output=state.STATE/'task-staging'/workspace_key(workspace)/job/'output';output.mkdir(parents=True)
(output/'probe.txt').write_text('output-probe\\n')
create_job(workspace,job,'d2','codex','fixture-only')
assignment_environments.capture(workspace,job,['skill-workspace','skill-d2'],environment_runtime.read(environment))
"""
subprocess.run(['docker','compose','exec','-T','gateway','python','-c',fixture_code,
                identity_before,persistent_thread,assignment_job,restored['runtime']['id']],check=True,capture_output=True,text=True)
assignment_base='/api/harness/environments/assignments/'+persistent_thread+'/'+assignment_job
saved_assignment=json.loads(request(assignment_base+'/configuration'))
assert 'skill-d2' in saved_assignment['skills'] and 'provider-agy' not in saved_assignment['tool_versions']
request('/api/harness/environments',{**saved_assignment,'name':'ci-from-assignment','display_name':'Saved assignment'})
request('/api/agents/ci-from-assignment',method='DELETE')
assignment_client='c1'*16
inspection=json.loads(request(assignment_base+'/terminal',{'client_id':assignment_client},method='POST'))
inspection_base='/api/harness/environments/terminals/'+inspection['id']
try:
    command="cat /workspace/project/terminal-project-probe.txt /workspace/output/probe.txt; if touch /workspace/project/terminal-write-test; then printf 'BAD-write\\n'; else printf 'project-%s\\n' ro; fi; if touch /workspace/output/write-test; then printf 'BAD-write\\n'; else printf 'output-%s\\n' ro; fi\n"
    request(inspection_base+'/input',{'text':command},method='POST')
    output=b'';cursor=0
    for _ in range(20):
        event=json.loads(request(inspection_base+'/status?after='+str(cursor)))
        output+=base64.b64decode(event['output_base64']);cursor=event['cursor']
        if b'output-ro' in output.splitlines():break
    # Bash may place a carriage return after its bracketed-paste escape before
    # the first output line. Match complete PTY lines, not a fixed CRLF prefix.
    for expected in (b'project-probe',b'output-probe',b'project-ro',b'output-ro'):assert expected in output.splitlines(),output[-4000:]
    kept=json.loads(request(inspection_base+'/retention',{'minutes':10},method='POST'))
    assert kept['retained_until']>time.time() and kept['assignment']==assignment_job
    request('/api/harness/environments/terminal-clients/'+assignment_client+'/close',{},method='POST')
    assert not json.loads(request(inspection_base+'/status'))['finished']
    adopted=json.loads(request(inspection_base+'/reconnect',{'client_id':'c2'*16},method='POST'))
    assert adopted['id']==inspection['id']
    active=json.loads(request('/api/harness/environments'))['activity']['jobs']
    assert any(j.get('terminal_id')==inspection['id'] and j.get('retained_until') for j in active)
    request(inspection_base+'/retention',{'minutes':0},method='POST')
finally:
    request(inspection_base,method='DELETE');wait_for_terminal_cleanup([inspection['id']])
print('Assignment terminal OK: same real PTY service, exact prepared software, read-only project/staging mounts, save normal profile, explicit retention, page-close survival, reconnect, monitor and confirmed cleanup.')


definition.update(mode='on_demand',preload_tools=[])
request('/api/harness/environments/ci-custom-environment',definition,method='PUT')
assert json.loads(request('/api/harness/environments/ci-custom-environment/cache',method='DELETE'))['removed']
request('/api/agents/ci-custom-environment',method='DELETE')

request('/api/skills/skill-blender', {'enabled':False}, method='PUT')
assert json.loads(request('/harness/api/catalog'))['agents']['blender']['enabled'] is False
request('/api/skills/skill-blender', {'enabled':True}, method='PUT')
assert json.loads(request('/harness/api/catalog'))['agents']['blender']['enabled'] is True
request('/harness/api/agents/blender', {'engine':'inherit','enabled':False}, method='PUT')
assert next(s for s in json.loads(request('/api/skills'))['skills'] if s['name'] == 'skill-blender')['enabled'] is False
request('/api/skills/skill-blender', {'enabled':True}, method='PUT')
assert json.loads(request('/harness/api/catalog'))['agents']['blender']['enabled'] is True


catalog = json.loads(request('/harness/api/catalog'))
assert set(catalog['agents']) == {app['id'] for app in catalog['applications']}
saved = json.loads(request('/harness/api/agents/gridcraft',
                          {'engine': 'gemini', 'model': '', 'instructions': 'Preferisci euro',
                           'enabled': True}, method='PUT'))
assert saved['engine'] == 'gemini'
catalog = json.loads(request('/harness/api/catalog'))
assert catalog['agents']['gridcraft']['instructions'] == 'Preferisci euro'
assert b'Models &amp; resources' in request('/workspace/harness')
request('/api/harness/environments',{**definition,'name':'ci-private-history','mode':'on_demand','ephemeral':False})
request('/api/v1/auth/logout', {})
request('/api/v1/auth/register', {'email': 'harness-ci-user@example.com',
                                 'password': 'CiOnly-Regular-User-P4ssword!78239'})
for path, payload, method in [('/harness/api/catalog', None, 'GET'),
                              ('/api/v1/gallery/registries', None, 'GET'),
                              ('/api/v1/gallery/feedback-reports', None, 'GET'),
                              ('/api/v1/gallery/registries/untrusted', {'url':'https://example.test','sha256':'0'*64}, 'PUT'),
                              ('/harness/api/login/gemini', {}, 'POST'),
                              ('/harness/api/team', {'engine': 'gemini'}, 'PUT')]:
    try:
        request(path, payload, method)
    except urllib.error.HTTPError as error:
        assert error.code == 403, (path, error.code)
    else:
        raise AssertionError('Un utente ordinario ha accesso alla configurazione globale: ' + path)
print('OK: account, sessione, CSRF, configurazione amministratore; accesso globale negato agli utenti ordinari.')

# Ordinary users can review public packs but cannot edit the publisher's content or profiles.
feedback_path='/api/v1/gallery/packs/ci-shared-environment/feedback'
rating=json.loads(request(feedback_path,{'version':'1.0.0','body':'Clear reusable diagrams','score':4}))
updated_rating=json.loads(request(feedback_path,{'version':'1.0.0','body':'Guide improved','score':5}))
assert rating['id']==updated_rating['id']
request('/api/v1/gallery/feedback/'+publisher_comment['id'],method='DELETE')
discussion=json.loads(request(feedback_path))
assert discussion['total']==2 and discussion['ratings'][0]['count']==1 and discussion['ratings'][0]['average']==5
assert all('owner' not in item for item in discussion['items'])
try:request('/api/harness/environments/ci-private-history/history')
except urllib.error.HTTPError as error:assert error.code in (403,404)
else:raise AssertionError('Another account can inspect private environment history')
request('/api/v1/gallery/feedback/'+publisher_comment['id']+'/report',{'reason':'Example moderation report'})
request('/api/v1/auth/logout',{})
from urllib.parse import urlencode
login_headers={'Origin':base,'Content-Type':'application/x-www-form-urlencoded'}
for cookie in cookies:
    if cookie.name=='csrf_token':login_headers['X-CSRF-Token']=cookie.value
client.open(urllib.request.Request(base+'/api/v1/auth/login/local',data=urlencode({'username':'harness-ci@example.com','password':'CiOnly-Strong-Login-P4ssword!78239'}).encode(),headers=login_headers),timeout=30).read()
reports=json.loads(request('/api/v1/gallery/feedback-reports'))['items']
assert any(item['id']==publisher_comment['id'] for item in reports)
request('/api/v1/gallery/feedback/'+publisher_comment['id']+'/moderate',{'reason':'CI moderation workflow confirmed'})
assert json.loads(request(feedback_path))['total']==1
print('Authenticated reviews OK: versioned rating update, cross-account ownership, report and administrator moderation')

request('/api/agents/ci-private-history',method='DELETE')
