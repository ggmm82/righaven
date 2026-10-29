#!/usr/bin/env python3
"""Native account, skill-edit and reset flows against the isolated CI candidate."""
import json
import urllib.parse
from pathlib import Path
from ci_environment_lifecycle import Session,record,REPORT,moderation_fixture

API='/api/harness/maintenance'


def main():
    admin=Session('harness-ci@example.com');user=Session('harness-ci-user@example.com')
    roles=admin.request('/api/v1/admin/users/roles')['roles']
    assert {'admin','user'}.issubset(roles)
    user.expect_error(403,'/api/v1/admin/users')
    user.expect_error(403,'/api/v1/admin/users',{'email':'denied@example.com','password':'CiOnly-Temporary-P4ssword!2958'})
    users='/api/v1/admin/users'
    email='ci-managed@example.com';temporary='CiOnly-Temporary-P4ssword!2958'
    created=admin.request(users,{'email':email,'password':temporary,'system_role':'user'})
    assert created['needs_setup'] and created['system_role']=='user'
    identifier=created['id'];path=users+'/'+identifier
    admin.expect_error(422,users,{'email':'bad-role@example.com','password':temporary,'system_role':'unknown'})
    admin.expect_error(409,path+'/credentials',{'confirmation':'wrong@example.com'})
    admin.request(path,{'disabled':True},'PATCH')
    admin.request(path,{'disabled':False},'PATCH')
    admin.request(path,{'system_role':'admin'},'PATCH')
    admin.request(path,{'system_role':'user'},'PATCH')
    # Only this isolated disposable account's sessions are revoked.
    session=Session.__new__(Session)
    import http.cookiejar,urllib.request,os
    session.cookies=http.cookiejar.CookieJar()
    passwords=urllib.request.HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password(None,'http://127.0.0.1:2026','admin',os.environ['RIGHAVEN_PASSWORD'])
    session.client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(session.cookies),urllib.request.HTTPBasicAuthHandler(passwords))
    session.request('/api/v1/auth/login/local',urllib.parse.urlencode({'username':email,'password':temporary}).encode(),content_type='application/x-www-form-urlencoded')
    assert session.request('/api/v1/auth/me')['id']==identifier
    admin.request(path+'/credentials',{'confirmation':email})
    session.expect_error(401,'/api/v1/auth/me')
    changed=admin.request(path+'/credentials',{'confirmation':email,'new_password':'CiOnly-Rotated-P4ssword!7854'})
    assert changed['needs_setup']
    record('Native user administration','Create, roles, suspend/reactivate, exact credential confirmation, session revocation and temporary password; non-admin denied')

    activated=user.request('/api/v1/gallery/packs/env-data-engineering-rig/activate',{})
    native_name=activated['installation']['native_name']
    profile=user.request('/api/agents/'+native_name)
    assert {'skill-usql','skill-dlt','skill-jupyter','skill-quarto','skill-typst'}.issubset(profile['skills'])
    user.request('/api/agents/'+native_name,method='DELETE')
    record('Data engineering Gallery activation','Native private profile includes managed connections, notebooks and reporting without eager software installation')

    # Integration instructions become personal copies, including referenced files.
    endpoint='/api/harness/skills/skill-d2/instructions'
    original=user.request(endpoint);admin_original=admin.request(endpoint)
    assert 'references/CLI-RECIPE.md' in original['files']
    modified=original['content']+'\n\nPreserve readable labels and validate the editable diagram.\n'
    ref=user.request(endpoint+'?file=references/CLI-RECIPE.md')
    updated_ref=ref['content']+'\nUse a clean output directory.\n'
    user.expect_error(400,endpoint,{'content':modified,'revision':original['revision']},'PUT')
    assert user.request(endpoint)['content']==original['content']
    # Simulate only the external moderation response, for these exact safe drafts.
    with moderation_fixture([modified,updated_ref]):
        saved=user.request(endpoint,{'content':modified,'revision':original['revision']},'PUT')
        assert saved['customized'] and saved['content']==modified
        assert admin.request(endpoint)['content']==admin_original['content']
        user.expect_error(409,endpoint,{'content':modified+'\nAgain','revision':original['revision']},'PUT')
        user.request(endpoint,{'file':ref['file'],'content':updated_ref,'revision':ref['revision']},'PUT')
    user.expect_error(422,endpoint+'?file=../outside.md')
    record('Native personal skill instructions','Integration and reference editing, copy-on-write isolation, stale revision refusal and path containment')

    name='ci-reset-profile'
    definition={'name':name,'display_name':'Reset fixture','purpose':'Disposable CI profile','skills':['skill-d2'],'mode':'on_demand'}
    user.request('/api/harness/environments',definition)
    inventory=user.request(API)
    assert any(t['id']==name for t in inventory['environments'])
    assert not any(t['id']==name for t in admin.request(API)['environments'])
    user.expect_error(403,API+'/preview',{'scopes':['models']})
    user.expect_error(404,API+'/preview',{'scopes':['environments'],'targets':{'environments':['not-owned']}})
    proposal=user.request(API+'/preview',{'scopes':['environments'],'targets':{'environments':[name]}})
    assert proposal['count']==1
    user.expect_error(409,API+'/confirm',{'id':proposal['id'],'phrase':'RESET'})
    result=user.request(API+'/confirm',{'id':proposal['id'],'phrase':proposal['confirmation_phrase']})
    assert result['completed']==[{'scope':'environments','id':name}]
    user.expect_error(409,API+'/confirm',{'id':proposal['id'],'phrase':proposal['confirmation_phrase']})
    user.expect_error(404,'/api/agents/'+name)
    proposal=user.request(API+'/preview',{'scopes':['skill_overrides'],'targets':{'skill_overrides':['skill-d2']}})
    user.request(API+'/confirm',{'id':proposal['id'],'phrase':proposal['confirmation_phrase']})
    restored=user.request(endpoint)
    assert restored['content']==original['content'] and not restored['customized']
    record('Native owner-scoped reset','Owner filtering, admin boundary, explicit typed preview, one-use confirmation, profile removal and restoration of shipped skill instructions')


if __name__=='__main__':
    output=Path('reports/workspace-management.json');output.parent.mkdir(parents=True,exist_ok=True)
    try:main()
    finally:output.write_text(json.dumps({'checks':REPORT,'scope':'Disposable CI candidate only; no production resets'},indent=2))
