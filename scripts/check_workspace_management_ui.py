#!/usr/bin/env python3
"""Real React flows for instruction edits, reset confirmations and user management.

Declared API fixtures only; ci_workspace_management.py verifies native persistence.
"""
import argparse,json,subprocess,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=Path(args.node_modules).resolve()
    with tempfile.TemporaryDirectory(prefix='righaven-management-ui-') as folder:
        root=Path(folder)
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:"en-US"}}; export function useAuth(){return {user:{id:"admin",system_role:"admin"}}}')
        (root/'config.ts').write_text('export function getBackendBaseURL(){return ""}')
        (root/'fetch.ts').write_text('export const fetch=globalThis.fetch.bind(globalThis)')
        (root/'link.tsx').write_text('export default function Link(props:any){return <a {...props}/>;}')
        (root/'section.tsx').write_text('export function SettingsSection({title,description,children}:any){return <section><h1>{title}</h1><p>{description}</p>{children}</section>}')
        entry='''import React from 'react';import {createRoot} from 'react-dom/client';
import {SkillInstructions} from SKILL;
import Maintenance from MAINTENANCE;
import Inventory from INVENTORY;
import {UserSettingsPage} from USERS;
const kind=new URLSearchParams(location.search).get('page');
const profile={name:'docs',skills:['skill-d2'],disabled:[],runtime:{status:'ready'},version_inventory:[{tool:'d2',installed:'0.6',requested:'latest',target:'0.7',status:'update_available'}]};
createRoot(document.getElementById('root')!).render(kind==='skill'?<SkillInstructions name="skill-d2"/>:kind==='reset'?<Maintenance/>:kind==='inventory'?<Inventory base="/api/harness/environments" profile={profile} onChanged={async()=>{}}/>:<UserSettingsPage/>);'''
        for key,path in {'SKILL':repo/'frontend/skill-instructions.tsx','MAINTENANCE':repo/'frontend/maintenance-page.tsx','INVENTORY':repo/'frontend/environment-inventory.tsx','USERS':repo/'core/frontend/src/components/workspace/settings/user-settings-page.tsx'}.items():entry=entry.replace(key,json.dumps(str(path)))
        (root/'entry.tsx').write_text(entry)
        aliases={'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/auth/AuthProvider':str(root/'hooks.ts'),'@/core/config':str(root/'config.ts'),'@/core/api/fetcher':str(root/'fetch.ts'),'next/link':str(root/'link.tsx')}
        build={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'bundle.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases}
        javascript='const esbuild=require('+json.dumps(str(modules/'esbuild'))+');const options='+json.dumps(build)+';options.plugins=[{name:"section",setup(b){b.onResolve({filter:/^\\.\\/settings-section$/},()=>({path:'+json.dumps(str(root/'section.tsx'))+'}));}}];esbuild.build(options).catch(e=>{console.error(e);process.exit(1)});'
        subprocess.run(['node','-e',javascript],check=True,text=True)
        html='<html><body><div id="root"></div><script src="/bundle.js"></script></body></html>'
        instructions={'content':'---\nname: skill-d2\ndescription: Editable diagrams\n---\n\nKeep readable labels.','revision':'a'*64,'file':'SKILL.md','files':['SKILL.md','references/CLI-RECIPE.md'],'customized':False,'editable':True,'enabled':True,'environments':[{'name':'docs','display_name':'Documents','enabled':True}]}
        account={'id':'one','email':'existing@example.test','system_role':'user','disabled':False,'needs_setup':False};accounts=[account];calls=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1100,'height':1000});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(route):
                request=route.request;path=request.url.split('management.test',1)[1]
                if path=='/bundle.js':route.fulfill(content_type='text/javascript',body=(root/'bundle.js').read_text());return
                if path.startswith('/api/'):
                    body=request.post_data_json if request.method in ('PUT','POST') else None
                    calls.append((path,body))
                    if '/instructions' in path:
                        if request.method=='PUT':instructions.update(content=body['content'],revision='b'*64,customized=True)
                        value=instructions
                    elif path.endswith('/preview'):value={'id':'c'*32,'count':1,'targets':{'environments':[{'id':'docs','label':'Documents'}]},'confirmation_phrase':'RESET 1 ITEMS','expires_at':9999999999,'notice':'Preview'}
                    elif path.endswith('/confirm'):value={'completed':[{'scope':'environments','id':'docs'}]}
                    elif path=='/api/harness/maintenance':value={'chats':[],'environments':[{'id':'docs','label':'Documents'}],'skill_overrides':[],'personal_versions':[],'global_versions':[],'can_reset_shared':True}
                    elif path.endswith('/roles'):value={'roles':['admin','user']}
                    elif path=='/api/v1/admin/users':
                        if request.method=='POST':accounts.append({**account,**body,'id':'two','needs_setup':True})
                        value=accounts
                    else:value={}
                    route.fulfill(json=value);return
                route.fulfill(content_type='text/html',body=html)
            page.route('http://management.test/**',route)
            try:
                page.goto('http://management.test/?page=skill')
                editor=page.get_by_label('Instruction content');expect(editor).to_contain_text('Keep readable labels.')
                editor.fill(instructions['content']+'\nCheck actual label overlap.')
                page.get_by_role('button',name='Validate and save personal copy').click()
                expect(page.get_by_role('status')).to_contain_text('Personal copy saved')
                assert any(path.endswith('/instructions') and body for path,body in calls)
                page.goto('http://management.test/?page=inventory')
                expect(page.get_by_role('cell',name='0.6',exact=True)).to_be_visible()
                expect(page.get_by_role('cell',name='Aggiornamento disponibile')).to_be_visible()
                page.get_by_role('button',name='Skill e istruzioni').click()
                expect(page.get_by_role('link',name='Leggi o personalizza istruzioni')).to_have_attribute('href','/workspace/capabilities?tab=skills&skill=skill-d2')
                page.goto('http://management.test/?page=reset')
                page.get_by_role('button',name='Review preview').click()
                confirm=page.get_by_role('button',name='Confirm reset',exact=True);expect(confirm).to_be_disabled()
                page.get_by_role('textbox').fill('wrong');expect(confirm).to_be_disabled()
                page.get_by_role('textbox').fill('RESET 1 ITEMS');confirm.click()
                expect(page.get_by_role('status')).to_contain_text('Operations completed: 1')
                page.goto('http://management.test/?page=users')
                expect(page.get_by_text('existing@example.test',exact=True)).to_be_visible()
                page.get_by_role('button',name='Create user',exact=True).click()
                page.get_by_label('Email',exact=True).fill('new@example.test')
                page.get_by_label('Temporary password',exact=True).fill('Fixture-Strong-P4ssword-12958')
                page.get_by_role('button',name='Create account',exact=True).click()
                expect(page.get_by_text('new@example.test',exact=True)).to_be_visible()
                page.get_by_role('button',name='Revoke sessions').first.click()
                expect(page.get_by_role('button',name='Confirm',exact=True)).to_be_disabled()
                assert not errors,errors
            finally:browser.close()
        print('Management UI OK: instruction edit, observed versions, skill link, typed reset confirmation, account creation and credential confirmation')


if __name__=='__main__':main()
