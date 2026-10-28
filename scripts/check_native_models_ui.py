#!/usr/bin/env python3
"""Fast browser regression of the actual native models page, without paid requests."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from playwright.sync_api import sync_playwright, expect


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-modules', required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    modules = Path(args.node_modules).resolve()
    with tempfile.TemporaryDirectory(prefix='righaven-native-models-') as folder:
        root = Path(folder)
        (root/'fetcher.ts').write_text('export const fetch = globalThis.fetch.bind(globalThis);')
        (root/'hooks.ts').write_text('export function useI18n(){return {locale:new URLSearchParams(window.location.search).has("italian")?"it-IT":"en-US"};}')
        (root/'navigation.ts').write_text('const router={replace:(url:string)=>{window.location.href=url}}; export function useRouter(){return router;}')
        (root/'link.tsx').write_text('export default function Link(props:any){return <a {...props}/>;}')
        (root/'entry.tsx').write_text('import React from "react";import {createRoot} from "react-dom/client";import Models from '+json.dumps(str(repo/'frontend/harness-page.tsx'))+';createRoot(document.getElementById("root")!).render(<Models/>);')
        aliases = {'next/link':str(root/'link.tsx'),'next/navigation':str(root/'navigation.ts'),
                   '@/core/api/fetcher':str(root/'fetcher.ts'),'@/core/i18n/hooks':str(root/'hooks.ts')}
        build = {'entryPoints':[str(root/'entry.tsx')],'bundle':True,'jsx':'automatic',
                 'nodePaths':[str(modules)],'outfile':str(root/'bundle.js'),'alias':aliases}
        subprocess.run(['node','-e','require('+json.dumps(str(modules/'esbuild'))+').buildSync('+json.dumps(build)+')'],check=True)
        html = '<!doctype html><html><body><div id="root"></div><script src="/bundle.js"></script></body></html>'
        fixture = {'profiles':{'coordinator':{'engine':'codex','model':'gpt-6.1-sol','ready':True},
                              'squad':{'engine':'deepseek','model':'deepseek-chat','ready':True}},
                   'connections':{engine:{'credentials_present':engine!='openai'} for engine in ('codex','gemini','deepseek','openai')}}
        requests, errors = [], []
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True,args=['--no-sandbox'])
            page = browser.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            def route(request):
                path=request.request.url.split('console.test',1)[1]
                if path=='/bundle.js':
                    request.fulfill(content_type='text/javascript',body=(root/'bundle.js').read_text());return
                if path=='/api/v1/cloud/edition':value={'edition':'community'}
                elif path=='/harness/api/catalog':value=fixture
                elif path.startswith('/harness/api/team/models'):value={'models':['fixture-model']}
                elif path=='/harness/api/team':
                    body=request.request.post_data_json;requests.append(body)
                    fixture['profiles']['squad']={'engine':body['engine'],'model':body['model'],'ready':True};value={'ok':True}
                elif path=='/harness/api/login/codex':value={'id':'fixture-session','engine':'codex','finished':False,'text':''}
                elif path=='/harness/api/login-session/fixture-session':
                    requests.append({'session_method':request.request.method})
                    value={'id':'fixture-session','engine':'codex','finished':False,'text':'Device code: ABCD-EFGH','authorization_url':'https://auth.openai.com/codex/device'}
                else:
                    request.fulfill(content_type='text/html',body=html);return
                request.fulfill(json=value)
            page.route('http://console.test/**',route)
            try:
                page.goto('http://console.test/')
                page.get_by_label('Assign to',exact=True).select_option('squad')
                page.get_by_label('Provider',exact=True).select_option('openai')
                page.get_by_label('Endpoint URL',exact=True).fill('https://provider.example/v1')
                page.get_by_label('API key',exact=True).fill('fixture-not-a-real-key')
                page.get_by_role('button',name='Load available models',exact=True).click()
                expect(page.get_by_role('status')).to_contain_text('Model list refreshed.')
                page.get_by_label('Available models',exact=True).select_option('fixture-model')
                expect(page.get_by_label('Model ID',exact=True)).to_have_value('fixture-model')
                page.get_by_role('button',name='Check & save',exact=True).click()
                expect(page.get_by_role('status')).to_contain_text('Connection checked and model assignments saved.')
                expect(page.get_by_label('API key',exact=True)).to_have_value('')
                assert requests[-1]['scope']=='squad'
                assert requests[-1]['base_url']=='https://provider.example/v1'
                expect(page.get_by_text('gpt-6.1-sol',exact=True)).to_be_visible()
                page.get_by_label('Provider',exact=True).select_option('gemini')
                page.get_by_role('button',name='Load available models',exact=True).click()
                page.get_by_label('Available models',exact=True).select_option('fixture-model')
                expect(page.get_by_label('Model ID',exact=True)).to_have_value('fixture-model')
                page.get_by_label('Provider',exact=True).select_option('codex')
                page.get_by_role('button',name='Connect account',exact=True).click()
                expect(page.get_by_role('link',name='Open official sign-in',exact=True)).to_be_visible()
                with page.expect_response(lambda response:response.url.endswith('/login-session/fixture-session') and response.request.method=='DELETE'):
                    page.get_by_role('button',name='Cancel sign-in',exact=True).click()
                assert {'session_method':'DELETE'} in requests
                page.goto('http://console.test/?italian')
                expect(page.get_by_role('heading',name='Modelli e risorse',exact=True)).to_be_visible()
                page.get_by_label('Assegna a',exact=True).select_option('coordinator')
                assert not errors,errors
            except Exception:
                print('Rendered model console:',page.locator('main').inner_text())
                print('Browser errors:',errors)
                raise
            finally:
                browser.close()
    print('Native models UI OK: English/Italian labels, scoped model assignment, endpoint, key clearing, official login and cancellation.')


if __name__=='__main__':
    main()
