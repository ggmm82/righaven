#!/usr/bin/env python3
"""Real React flows for the Policy Book lifecycle and the project governance panel.

Declared API fixtures only; tests/test_policy_book.py verifies the native routes.
"""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

BUILTIN={'id':'quality_standard','title':'Standard quality review','version':1,'summary':'Every delivery','mandatory':True,
         'rules':['Respect the request'],'handoff_checks':[],'final_checks':'acceptance','depends_on':[],'applies_to':['work','preview','integration','delivery']}


class Book:
    """Minimal in-memory mirror of the lifecycle API used by the page."""
    def __init__(self):self.records={}
    def overview(self,admin):
        rows=[{'id':'quality_standard','title':BUILTIN['title'],'summary':'','source':'builtin','status':'active','mandatory':True,'active_version':1,'has_draft':False}]
        for r in self.records.values():
            current=r['versions'][-1]['sheet'] if r['active_version'] else r['draft']
            rows.append({'id':r['id'],'title':current['title'],'summary':'','source':'organization','status':r['status'],'mandatory':current['mandatory'],
                         'active_version':r['active_version'],'has_draft':r['draft'] is not None})
        return {'sheets':rows,'can_manage':admin,'default_sheet':'quality_standard'}
    def detail(self,identifier):
        if identifier=='quality_standard':
            return {'id':identifier,'source':'builtin','status':'active','active_version':1,'draft':None,
                    'versions':[{'version':1,'sheet':{**BUILTIN},'revision':'r','published_at':'','published_by':'RigHaven'}],'history':[]}
        return {**self.records[identifier],'source':'organization'}
    def event(self,record,action,version=None):
        record['history'].append({'at':'2026-10-30T12:00:00','actor':'admin@example.test','action':action,**({'version':version} if version else {})})
    def handle(self,method,path,body):
        parts=path.split('/api/harness/policy-book',1)[1].strip('/').split('/')
        if parts==['']:return None
        identifier=parts[1]
        if len(parts)==2:return self.detail(identifier)
        if parts[2]=='draft' and method=='PUT' and not body['title'].strip():return 400,{'detail':'Policy sheet: titolo entro 140 caratteri'}
        record=self.records.setdefault(identifier,{'id':identifier,'status':'draft','active_version':None,'draft':None,'versions':[],'history':[]})
        action=parts[2]
        if action=='draft' and method=='PUT':
            record['draft']={**body,'saved_at':'2026-10-30T12:00:00','saved_by':'admin@example.test'};self.event(record,'draft_saved')
        elif action=='publish':
            number=len(record['versions'])+1;sheet={**{k:v for k,v in record['draft'].items() if k not in ('saved_at','saved_by')},'id':identifier,'version':number}
            record['versions'].append({'version':number,'sheet':sheet,'revision':'r'+str(number),'published_at':'2026-10-30T12:00:00','published_by':'admin@example.test'})
            record.update(status='active',active_version=number,draft=None);self.event(record,'published',number)
        elif action=='retire':record['status']='retired';self.event(record,'retired',record['active_version'])
        elif action=='reactivate':record['status']='active';self.event(record,'reactivated',record['active_version'])
        elif action=='restore':
            sheet=record['versions'][body['version']-1]['sheet'];record['draft']={k:v for k,v in sheet.items() if k not in ('id','version')}
            self.event(record,'restored_to_draft',body['version'])
        return self.detail(identifier)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--node-modules',required=True);args=parser.parse_args()
    repo=Path(__file__).resolve().parents[1];modules=Path(args.node_modules).resolve()
    with tempfile.TemporaryDirectory(prefix='righaven-policy-ui-') as folder:
        root=Path(folder)
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:"en-US"}}')
        (root/'config.ts').write_text('export function getBackendBaseURL(){return ""}')
        (root/'fetch.ts').write_text('export const fetch=globalThis.fetch.bind(globalThis)')
        governance={'phase':'validation','settled':True,'planned_at':'2026-10-30T14:03:29','selected_by':'coordinator','optional_available':[],
                    'product':{'path':'/mnt/user-data/outputs/brochure.pdf','integrity':'passed','issue':''},'last_validation':{'at':'2026-10-30T15:00:00','status':'failed'},
                    'checkpoints':{'enabled':True,'pending':{'steps':['impaginazione'],'at':'2026-10-30T14:40:00'},'discussed':2},
                    'sheets':[{'id':'quality_standard','title':'Standard quality review','version':1,'mandatory':True,'reason':'Obbligatoria nel Policy Book','steps':[],'depends_on':[],
                               'final':'acceptance','handoff':{'required':0,'declared':0,'violations':[]},'status':'needs_review','reviewed_at':'2026-10-30T14:30:00',
                               'findings':[{'requirement_id':'pr5_inclusa','status':'not_run','criterion':'PR #5 inclusa','evidence':'Riferimento non disponibile'}]},
                              {'id':'security','title':'Security','version':2,'mandatory':False,'reason':'Documento pubblico','steps':['draft'],'depends_on':[],
                               'final':1,'handoff':{'required':1,'declared':0,'violations':['no_secrets']},'status':'failed','reviewed_at':'2026-10-30T14:31:00',
                               'findings':[{'requirement_id':'secret_scan','status':'failed','criterion':'No credentials','evidence':'Token found on page 2'}]}]}
        choices=[{'id':'pdf','decision':'PDF layout','recommended':'typst','recommendation_reason':'Readable source, reproducible build','chosen':'',
                  'options':[{'id':'typst','label':'Typst','tools':['typst'],'pros':['Fast'],'cons':['Less common']},
                             {'id':'pandoc','label':'Pandoc','tools':['pandoc'],'pros':['Many formats'],'cons':['Limited typography']}]}]
        entry='''import React from 'react';import {createRoot} from 'react-dom/client';
import PolicyBook from PAGE;
import {GovernanceStrip,ToolChoices} from PANEL;
const kind=new URLSearchParams(location.search).get('page');
function Panel(){const [g,setG]=React.useState(GOVERNANCE as any);return <><ToolChoices decisions={CHOICES as any}/><GovernanceStrip governance={g} threadId="t1" onChanged={setG}/></>;}
createRoot(document.getElementById('root')!).render(kind==='project'?<Panel/>:<PolicyBook/>);'''
        entry=entry.replace('PAGE',json.dumps(str(repo/'frontend/policy-book-page.tsx'))).replace('PANEL',json.dumps(str(repo/'frontend/project-governance.tsx'))).replace('GOVERNANCE',json.dumps(governance)).replace('CHOICES',json.dumps(choices))
        (root/'entry.tsx').write_text(entry)
        aliases={'@/core/i18n/hooks':str(root/'hooks.ts'),'@/core/config':str(root/'config.ts'),'@/core/api/fetcher':str(root/'fetch.ts')}
        build={'entryPoints':[str(root/'entry.tsx')],'outfile':str(root/'bundle.js'),'bundle':True,'jsx':'automatic','nodePaths':[str(modules)],'alias':aliases}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').build('+json.dumps(build)+').catch(e=>{console.error(e);process.exit(1)})'],check=True,text=True)
        html='<html><body><div id="root"></div><script src="/bundle.js"></script></body></html>'
        book=Book();role={'admin':True};calls=[]
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True);page=browser.new_page(viewport={'width':1200,'height':1100});errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            def route(route):
                request=route.request;path=request.url.split('policy.test',1)[1]
                if path=='/bundle.js':route.fulfill(content_type='text/javascript',body=(root/'bundle.js').read_text());return
                if path.startswith('/api/'):
                    body=request.post_data_json if request.method in ('PUT','POST') and request.post_data else None
                    calls.append((request.method,path,body))
                    if path=='/api/threads/t1/harness-checkpoints':
                        route.fulfill(json={'governance':{**governance,'checkpoints':{'enabled':body['enabled'],'pending':None,'discussed':2}}});return
                    value=book.overview(role['admin']) if path=='/api/harness/policy-book' else book.handle(request.method,path,body)
                    if isinstance(value,tuple):route.fulfill(status=value[0],json=value[1])
                    else:route.fulfill(json=value)
                    return
                route.fulfill(content_type='text/html',body=html)
            page.route('http://policy.test/**',route)
            try:
                page.goto('http://policy.test/')
                page.wait_for_timeout(1500);print('PAGE ERRORS',errors) if errors else None
                sheets=page.get_by_role('navigation',name='Policy sheets')
                expect(sheets.get_by_text('Built into RigHaven')).to_be_visible()
                sheets.get_by_role('button',name='Standard quality review').click()
                expect(page.get_by_text('Separate review of the product against the project acceptance contract.')).to_be_visible()
                expect(page.get_by_role('button',name='Prepare a new version')).to_have_count(0)  # built-in sheets are read-only
                # Guided setup: each step explains its choices and blocks incomplete input.
                page.get_by_role('button',name='New guided policy').click()
                form=page.get_by_role('form',name='Guided setup')
                expect(form).to_contain_text('the coordinator reads this description')
                form.get_by_label('Identifier').fill('Security')
                expect(form.get_by_text('Choose an identifier')).to_be_visible()
                expect(form.get_by_role('button',name='Next')).to_be_disabled()
                form.get_by_label('Identifier').fill('security')
                expect(form.get_by_text('Give the policy a title.')).to_be_visible()
                form.get_by_label('Title').fill('Security')
                form.get_by_label('What it is for').fill('No secrets in delivered products')
                form.get_by_label(re.compile('^When relevant')).check()
                form.get_by_role('button',name='Next').click()
                expect(form.get_by_role('heading',name='2. Working rules')).to_be_visible()
                form.get_by_label('Rules (one per line)').fill('No credentials in files\nRotate exposed tokens')
                form.get_by_role('button',name='Next').click()
                expect(form).to_contain_text('If a blocking check is missing or fails, the activity goes back to revision')
                form.get_by_role('button',name='Add a check').click()
                form.get_by_label('What must be true').first.fill('No credentials in delivered files')
                form.get_by_role('button',name='Next').click()
                form.get_by_label('This policy’s own criteria').check()
                form.get_by_role('button',name='Add a criterion').click()
                form.get_by_label('What must be true').first.fill('Product contains no credentials')
                form.get_by_label('How it is verified').select_option('technical')
                expect(form).to_contain_text('Automated tools: scans, counts, validators.')
                form.get_by_role('button',name='Next').click()
                expect(form.get_by_label('Final delivery')).to_be_checked()
                form.get_by_label('Samples and trials').uncheck()
                form.get_by_role('button',name='Next').click()
                summary=form.get_by_test_id('policy-summary')
                expect(summary).to_contain_text('Applies when the coordinator finds it relevant and explains why.')
                expect(summary).to_contain_text('No credentials in delivered files · blocking: if missing, the activity goes back to revision')
                expect(summary).to_contain_text('Product contains no credentials · Technical measurement · blocking')
                expect(summary).not_to_contain_text('Samples and trials')
                form.get_by_role('button',name='Save as draft').click()
                expect(page.get_by_role('status')).to_have_text('Draft saved')
                saved=[b for m,pth,b in calls if m=='PUT'][-1]
                assert saved['rules']==['No credentials in files','Rotate exposed tokens'],saved
                assert saved['handoff_checks']==[{'id':'no_credentials_in_delivered_files','requirement':'No credentials in delivered files','critical':True}],saved
                assert saved['final_checks']==[{'id':'product_contains_no_credentials','requirement':'Product contains no credentials','method':'technical','critical':True}],saved
                assert saved['applies_to']==['work','integration','delivery'],saved
                expect(sheets.get_by_role('button',name='Security')).to_contain_text('Draft')
                expect(page.get_by_text('No published version: projects do not use it yet.')).to_be_visible()
                # Publish, retire, reactivate and restore: every step is visible in history.
                page.get_by_role('button',name='Publish draft').click()
                expect(page.get_by_role('status')).to_have_text('Published')
                expect(sheets.get_by_role('button',name='Security')).to_contain_text('Active v1')
                expect(page.get_by_role('article',name='Active version')).to_contain_text('Rotate exposed tokens')
                page.get_by_role('button',name='Retire').click()
                expect(sheets.get_by_role('button',name='Security')).to_contain_text('Retired v1')
                page.get_by_role('button',name='Reactivate').click()
                expect(sheets.get_by_role('button',name='Security')).to_contain_text('Active v1')
                page.get_by_role('button',name='Restore to draft').click()
                expect(page.get_by_text('the active version keeps applying until you publish it')).to_be_visible()
                # A new version reuses the guided steps and keeps existing codes.
                page.get_by_role('button',name='Continue the draft').click()
                form.get_by_role('button',name='6. Summary').click()
                form.get_by_role('button',name='Save and publish').click()
                expect(page.get_by_role('status')).to_have_text('Published')
                expect(sheets.get_by_role('button',name='Security')).to_contain_text('Active v2')
                history=page.get_by_role('heading',name='History').locator('..')
                for label in ('Draft saved','Published v1','Retired v1','Reactivated v1','Restored to draft v1','Published v2'):
                    expect(history).to_contain_text(label)
                # Team members read the book without management controls.
                role['admin']=False;page.goto('http://policy.test/')
                expect(page.get_by_role('button',name='New guided policy')).to_have_count(0)
                page.get_by_role('navigation',name='Policy sheets').get_by_role('button',name='Security').click()
                expect(page.get_by_role('article',name='Active version')).to_contain_text('No credentials in files')
                expect(page.get_by_role('button',name='Prepare a new version')).to_have_count(0)
                expect(page.get_by_role('button',name='Restore to draft')).to_have_count(0)
                # The project panel names the pinned sheets and their validation verdicts.
                page.goto('http://policy.test/?page=project')
                choices=page.get_by_test_id('tool-choices')
                expect(choices).to_contain_text('PDF layout · waiting for your choice: reply in the chat')
                expect(choices.get_by_role('listitem').filter(has_text='Typst')).to_contain_text('Typst · recommended')
                expect(choices.get_by_role('listitem').filter(has_text='Pandoc')).to_contain_text('Cons: Limited typography')
                expect(choices).to_contain_text('Why we recommend it: Readable source, reproducible build')
                panel=page.get_by_test_id('project-governance')
                expect(panel).to_contain_text('Final policy validation · 2 applied (1 to fix · 1 incomplete)')
                expect(page.get_by_text('There are violations to fix before delivery.')).to_be_hidden()  # collapsed by default
                expect(page.get_by_test_id('checkpoint-pending')).to_contain_text('Waiting for your reply on phase impaginazione')
                panel.locator('summary').click()
                expect(panel.get_by_test_id('checkpoint-settings')).to_contain_text('Pause after each phase is on')
                expect(panel.get_by_test_id('checkpoint-settings')).to_contain_text('Phases discussed: 2')
                expect(panel).to_contain_text('There are violations to fix before delivery.')
                expect(panel.get_by_role('listitem').filter(has_text='Security v2')).to_contain_text('Selected: Documento pubblico · only for draft')
                expect(panel).to_contain_text('Not passed (secret_scan): No credentials — Token found on page 2')
                expect(panel).to_contain_text('Not verified (pr5_inclusa): PR #5 inclusa — Riferimento non disponibile')
                expect(panel.get_by_role('alert')).to_contain_text('no_secrets')
                expect(panel).to_contain_text('Policy Plan pinned on 2026-10-30 14:03 by the coordinator')
                panel.get_by_role('button',name='Turn pauses off').click()
                expect(panel.get_by_test_id('checkpoint-settings')).to_contain_text('Pause after each phase is off')
                expect(page.get_by_test_id('checkpoint-pending')).to_have_count(0)
                assert [b for m,pth,b in calls if pth.endswith('/harness-checkpoints')]==[{'enabled':False}]
                assert not errors,errors
            finally:browser.close()
    print('Policy Book UI OK: guided six-step setup with explanations, generated codes and readable summary; publish, retire, reactivate, restore and new version; read-only team view; tool choices; live chat governance with checkpoints.')


if __name__=='__main__':main()
