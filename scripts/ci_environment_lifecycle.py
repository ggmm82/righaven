#!/usr/bin/env python3
"""Authenticated lifecycle checks against an isolated published Compose candidate.

No generation provider credentials; never targets production. Run after ci_http.py.
"""
import io,json,os,subprocess,time,urllib.request,urllib.parse,urllib.error,http.cookiejar,uuid,zipfile
from contextlib import contextmanager
from pathlib import Path

BASE='http://127.0.0.1:2026'
API='/api/harness/environments'
REPORT=[]


class Session:
    def __init__(self,email):
        manager=urllib.request.HTTPPasswordMgrWithDefaultRealm();manager.add_password(None,BASE,'admin',os.environ['RIGHAVEN_PASSWORD'])
        self.cookies=http.cookiejar.CookieJar()
        self.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies),urllib.request.HTTPBasicAuthHandler(manager))
        password='CiOnly-Strong-Login-P4ssword!78239' if email=='harness-ci@example.com' else 'CiOnly-Regular-User-P4ssword!78239'
        self.request('/api/v1/auth/login/local',urllib.parse.urlencode({'username':email,'password':password}).encode(),content_type='application/x-www-form-urlencoded')
    def request(self,path,payload=None,method=None,content_type='application/json'):
        headers={'Origin':BASE,'Content-Type':content_type}
        for cookie in self.cookies:
            if cookie.name=='csrf_token':headers['X-CSRF-Token']=cookie.value
        body=payload if isinstance(payload,bytes) else json.dumps(payload).encode() if payload is not None else None
        try:
            with self.client.open(urllib.request.Request(BASE+path,data=body,headers=headers,method=method),timeout=30) as response:
                data=response.read()
                return json.loads(data) if data else None
        except urllib.error.HTTPError as exc:
            exc.add_note(path+': '+exc.read(2000).decode('utf-8',errors='replace'))
            raise
    def profile(self,name):
        return next(p for p in self.request(API)['environments'] if p['name']==name)
    def expect_error(self,code,path,payload=None,method=None):
        try:self.request(path,payload,method)
        except urllib.error.HTTPError as exc:assert exc.code==code,(path,exc.code)
        else:raise AssertionError('Expected HTTP '+str(code)+' from '+path)
    def ready(self,name):
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            value=self.profile(name)
            if value['runtime']['status']=='ready':return value
            time.sleep(.5)
        raise AssertionError('Environment did not become ready: '+str(value['runtime']))


def record(name,evidence):
    REPORT.append({'at':time.time(),'test':name,'status':'passed','evidence':evidence})
    print('OK:',name,flush=True)


def restart(*, recreate=False):
    command=['docker','compose','up','-d','--no-deps','--force-recreate','gateway'] if recreate else ['docker','compose','restart','gateway']
    subprocess.run(command,check=True,capture_output=True,text=True)
    deadline=time.monotonic()+180
    auth=urllib.request.HTTPPasswordMgrWithDefaultRealm();auth.add_password(None,BASE,'admin',os.environ['RIGHAVEN_PASSWORD'])
    opener=urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(auth))
    while time.monotonic()<deadline:
        try:
            with opener.open(BASE+'/health/ready',timeout=5) as response:
                if response.status==200:return
        except (OSError,urllib.error.URLError):pass
        time.sleep(1)
    raise AssertionError('Gateway did not recover after restart')


def no_preparer(key):
    value=subprocess.check_output(['docker','compose','exec','-T','runtime-docker','docker','ps','-aq','--filter','label=org.righaven.environment='+key],text=True).strip()
    assert not value,'Preparation container was left behind'


@contextmanager
def moderation_fixture(content):
    """Stub only the external LLM boundary; retain the native scanner/installer."""
    gateway=subprocess.check_output(['docker','compose','ps','-q','gateway'],text=True).strip()
    info=json.loads(subprocess.check_output(['docker','inspect',gateway],text=True))[0]
    network=next(iter(info['NetworkSettings']['Networks']))
    name='ci-moderation-'+uuid.uuid4().hex[:8]
    script=Path(__file__).with_name('ci_skill_moderation.py').resolve()
    subprocess.run(['docker','run','-d','--rm','--init','--name',name,'--network',network,
        '--read-only','--tmpfs','/tmp:rw,nosuid,size=16m','--cap-drop=ALL','--security-opt=no-new-privileges',
        '--memory=64m','--cpus=0.25','--pids-limit=32','--mount','type=bind,src='+str(script)+',dst=/fixture.py,readonly',
        '-e','CI_EXPECTED_SKILL='+content,'righaven-sandbox:0.1.0','python3','/fixture.py'],check=True,capture_output=True)
    configure='''
import sys,yaml
from pathlib import Path
p=Path('/righaven-state/config.yaml');backup=Path('/righaven-state/ci-moderation-backup.yaml')
backup.write_bytes(p.read_bytes());backup.chmod(0o600)
c=yaml.safe_load(p.read_text())
c['models'].append({'name':'ci-skill-moderation','use':'langchain_openai:ChatOpenAI','model':'ci-skill-moderation','api_key':'ci-local-fixture-only','base_url':sys.argv[1]+'/v1'})
c.setdefault('skill_evolution',{}).update(moderation_model_name='ci-skill-moderation',security_fail_closed=True)
t=p.with_suffix('.yaml.ci');t.write_text(yaml.safe_dump(c));t.chmod(0o600);t.replace(p)
'''
    try:
        subprocess.run(['docker','compose','exec','-T','gateway','python','-c',configure,'http://'+name+':8765'],check=True)
        restart()
        yield
        status=subprocess.check_output(['docker','compose','exec','-T','gateway','python','-c',
            'import urllib.request;print(urllib.request.urlopen('+repr('http://'+name+':8765/status')+').read().decode())'],text=True)
        assert json.loads(status)['allowed_fixture_requests']>=1,status
    finally:
        try:
            subprocess.run(['docker','compose','exec','-T','gateway','python','-c',
                "from pathlib import Path;p=Path('/righaven-state/ci-moderation-backup.yaml');p.exists() and p.replace('/righaven-state/config.yaml')"],check=True)
        finally:subprocess.run(['docker','rm','-f',name],check=False,capture_output=True)


def main():
    owner=Session('harness-ci@example.com');other=Session('harness-ci-user@example.com')
    name='ci-lifecycle-'+uuid.uuid4().hex[:8]
    definition={'name':name,'display_name':'Lifecycle','purpose':'Preserve scope, editable sources and deployment preferences','instructions':'Use only the selected tools.','skills':['skill-d2','skill-pandoc'],'mode':'preload','ephemeral':False,'preload_tools':['d2']}
    created=owner.request(API,definition)
    # Change the preload while the first cold recipe is still being installed.
    definition['preload_tools']=['pandoc'];owner.request(API+'/'+name,definition,'PUT')
    ready=owner.ready(name)
    assert ready['preloaded_tools']==['pandoc'] and ready['runtime']['tools']==['pandoc'],ready
    first_image=ready['runtime']['image_id'];no_preparer(ready['runtime']['id'])
    record('Partial preload and edit during preparation',{'prepared':['pandoc'],'available':ready['tools']})
    assert name not in {p['name'] for p in other.request(API)['environments']}
    for tail,method in [('export','GET'),('log','GET'),('prepare','POST'),('cancel','POST'),('cache','DELETE')]:
        other.expect_error(404,API+'/'+name+'/'+tail,method=method)
    record('Authenticated user isolation','Another account cannot read, start, stop or evict this profile')
    owner.expect_error(409,API+'/'+name+'/cache',method='DELETE')
    record('Preloaded runtime pin','Cache eviction is refused while preload is selected')
    restart();ready=owner.ready(name)
    assert ready['runtime']['image_id']==first_image
    native=owner.request('/api/agents/'+name)
    assert native['soul']==definition['instructions'] and native['description']==definition['purpose']
    record('Gateway restart and reuse','Preferences, native instructions and the immutable cached image survive restart')
    # Removing an image externally must not leave a false ready status.
    definition.update(mode='on_demand',preload_tools=[])
    owner.request(API+'/'+name,definition,'PUT')
    subprocess.run(['docker','compose','exec','-T','runtime-docker','docker','image','rm','--no-prune',ready['runtime']['image']],check=True,capture_output=True,text=True)
    assert owner.profile(name)['runtime']['status']=='on_demand'
    owner.request(API+'/'+name+'/prepare',method='POST');ready=owner.ready(name);no_preparer(ready['runtime']['id'])
    record('Stale cache recovery','Missing Docker image is detected and rebuilt instead of being reported ready')
    # The native skill upload API must preserve a personal method and its requirements.
    skill='ci-method-'+uuid.uuid4().hex[:8];content='---\nname: '+skill+'\ndescription: Preserve editable diagram sources\nmetadata:\n  righaven-tools: [d2]\n---\nKeep the original model and verify the exported diagram.\n'
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,'w') as zipped:zipped.writestr(skill+'/SKILL.md',content)
    boundary='ci-'+uuid.uuid4().hex
    data=('--'+boundary+'\r\nContent-Disposition: form-data; name="archive"; filename="method.skill"\r\nContent-Type: application/zip\r\n\r\n').encode()+archive.getvalue()+('\r\n--'+boundary+'--\r\n').encode()
    try:owner.request('/api/skills/install/upload',data,content_type='multipart/form-data; boundary='+boundary)
    except urllib.error.HTTPError as exc:
        assert exc.code==400 and any('Security scan unavailable' in note for note in exc.__notes__),exc
    else:raise AssertionError('Skill upload must fail closed without moderation credentials')
    record('Native skill moderation fails closed','No model credentials: upload is blocked, not silently approved')
    with moderation_fixture(content):
        installed=owner.request('/api/skills/install/upload',data,content_type='multipart/form-data; boundary='+boundary)
    record('Native skill upload with declared model fixture','Real HTTP installer/scanner; only the external moderation response is simulated for this exact known content')
    assert installed['success'],installed
    method={**definition,'name':name+'-method','skills':[skill]}
    created=owner.request(API,method)
    assert created['tools']==['d2'] and 'skill-d2' in created['skills']
    owner.request('/api/skills/skill-d2',{'enabled':False},'PUT')
    invalid=owner.profile(method['name']);assert invalid['runtime']['status']=='invalid'
    owner.expect_error(409,API+'/'+method['name']+'/prepare',method='POST')
    owner.request('/api/skills/skill-d2',{'enabled':True},'PUT')
    restart();assert owner.profile(method['name'])['tools']==['d2']
    assert owner.request('/api/skills/custom/'+skill)['content']==content
    record('Personal method and global disable','Native upload, automatic requirements, explicit conflict and persistence after restart')
    # A queued cold preparation must be cancellable and retryable without residual processes.
    owner.request(API+'/'+name+'/cache',method='DELETE')
    definition.update(skills=['skill-d2'],preload_tools=[])
    owner.request(API+'/'+name,definition,'PUT')
    # D2 may have remained cached from the first preload; remove through the authorized API.
    owner.request(API+'/'+name+'/cache',method='DELETE')
    owner.request(API+'/'+name+'/prepare',method='POST')
    cancelled=owner.request(API+'/'+name+'/cancel',method='POST');assert cancelled['accepted']
    until=time.monotonic()+30
    while time.monotonic()<until:
        current=owner.profile(name)
        if current['runtime']['status'] not in ('queued','installing','adapters','checking'):break
        time.sleep(.25)
    no_preparer(current['runtime']['id'])
    owner.request(API+'/'+name+'/prepare',method='POST');owner.ready(name)
    record('Cancel and retry','Cancellation leaves no preparation container; the next explicit request succeeds')
    owner.request('/api/agents/'+name,method='DELETE');owner.request('/api/agents/'+method['name'],method='DELETE')
    owner.request('/api/skills/custom/'+skill,method='DELETE')
    record('Native cleanup','Test Agents and the personal skill are removed through their native APIs')


if __name__=='__main__':
    output=Path('reports/environment-lifecycle.json');output.parent.mkdir(parents=True,exist_ok=True)
    try:main()
    finally:output.write_text(json.dumps({'checks':REPORT,'scope':'Isolated candidate; no production access or model generation credentials'},indent=2))
