#!/usr/bin/env python3
"""Opt-in live model control smoke, using an isolated synthetic task, never production data.

Runs the actual OpenAI-compatible provider (for example DeepSeek), native agent graph, call guard and journey engine.
The small producer/reviewer fixtures test coordination, not creative model quality
or Docker/CLI installation (covered separately by native CI).
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--key-env',default='RIGHAVEN_TEST_API_KEY')
    parser.add_argument('--model',default='deepseek-chat')
    parser.add_argument('--base-url',default='https://api.deepseek.com')
    args=parser.parse_args()
    key=os.environ.get(args.key_env)
    if not key:raise SystemExit('Set the dedicated test API key environment variable')
    from langchain.agents import create_agent
    from langchain_core.tools import tool
    from langchain_core.messages import HumanMessage,SystemMessage
    from righaven import journeys,projects,state
    from righaven.audit_middleware import ConversationAuditMiddleware
    from righaven.openai_provider import HarnessCompatibleChatModel
    from righaven.progress import utcnow
    from righaven.published_files import read
    with tempfile.TemporaryDirectory(prefix='rh-live-coordination-') as directory:
        root=Path(directory);work=root/'task';work.mkdir()
        outputs=work/'outputs';outputs.mkdir()
        credentials=root/'credentials';credentials.mkdir(mode=0o700)
        secret=credentials/'api.json';secret.write_text(json.dumps({'api_key':key,'base_url':args.base_url}));secret.chmod(0o600)
        with patch('righaven.openai_provider.custom_connection_path',return_value=secret),patch.dict(os.environ,{'RIGHAVEN_EDITION':'community'}):
            model=HarnessCompatibleChatModel(model=args.model,max_tokens=1000,timeout=60,max_retries=0)
        secret.unlink()
        with patch.object(state,'STATE',root/'state'):
            journeys.start(work,'data-pipeline',{'goal':'A small sales dashboard with synthetic data, total revenue and editable sources'},mode='first_result')
            projects.create_plan(work,'Sales dashboard',[
                {'id':'build','agent':'workspace','goal':'Build usable dashboard','depends_on':[]},
                {'id':'review','agent':'workspace','goal':'Independent verification','depends_on':['build']},
                {'id':'deliver','agent':'workspace','goal':'Deliver editable sources','depends_on':[]}])
            executed=[]
            @tool
            def harness_journey()->str:
                """Read the persisted phase and next action. Never approve or rewrite phase states."""
                return json.dumps(journeys.compact(journeys.view(work)))
            @tool
            def harness_delegate(agent:str,task:str,step_id:str='',purpose:str='work',role_id:str='',phase_id:str='')->str:
                """Run an existing activity in the current phase; the runtime records evidence and submits reviewed phases.

                Activities: build (author, preview), review (checker, review), deliver (author, delivery).
                The owner alone approves a phase. Completed activities must not be repeated.
                """
                if agent!='workspace' or (step_id,role_id,purpose) not in (
                    ('build','author','preview'),('review','checker','review'),('deliver','author','delivery')):
                    raise ValueError('Use the declared activity, independent role and purpose')
                if step_id in executed:raise ValueError('Activity already completed; read the current phase')
                journeys.begin_activity(work,phase_id,step_id)
                started=utcnow()
                if step_id=='build':
                    with sqlite3.connect(outputs/'sales.sqlite') as db:
                        db.execute('CREATE TABLE sales(amount REAL)')
                        db.executemany('INSERT INTO sales VALUES (?)',[(10,),(20,),(30,)])
                        total=db.execute('SELECT sum(amount) FROM sales').fetchone()[0]
                    artifact=outputs/'dashboard.html';artifact.write_text(f'<!doctype html><title>Sales</title><h1>Sales dashboard</h1><output id="revenue">{total}</output>')
                elif step_id=='review':
                    with sqlite3.connect(outputs/'sales.sqlite') as db:total=db.execute('SELECT sum(amount) FROM sales').fetchone()[0]
                    assert total==60 and '60.0' in (outputs/'dashboard.html').read_text()
                    artifact=outputs/'review.md';artifact.write_text('Independent reconciliation passed: 3 sales, total 60.0. HTML matches actual data.')
                else:
                    artifact=outputs/'source.sql';artifact.write_text('CREATE TABLE sales(amount REAL);\nINSERT INTO sales VALUES (10),(20),(30);\nSELECT sum(amount) FROM sales;\n')
                path=work/'.righaven-project/project.json';project=json.loads(path.read_text())
                step=next(s for s in project['steps'] if s['id']==step_id)
                step.update(status='completed',purpose=purpose,role_id=role_id,attempts=[{
                    'started_at':started,'finished_at':utcnow(),'status':'completed','validated':True,
                    'output_files':[str(artifact)],'quality_review':{'status':'passed'}}])
                state.atomic_json(path,project);executed.append(step_id)
                return json.dumps({'ok':True,'artifact':'/mnt/user-data/outputs/'+artifact.name,
                                   'journey':journeys.compact(journeys.reconcile(work))})
            @tool
            def read_file(path:str)->str:
                """Read a published text artifact."""
                return json.dumps(read(work,path))
            @tool
            def ask_clarification(question:str)->str:
                """Ask a genuinely missing business choice, never a repeated phase approval."""
                raise ValueError('The fixture goal is complete; no further business question is needed')
            system=SystemMessage(content='You coordinate an isolated test task. Use harness_journey first. '
                'Execute the existing activities using the exact IDs and role/purpose described by harness_delegate. '
                'Produce a usable result before documenting further work. A completed independent review submits the phase automatically. '
                'When awaiting_owner is nonempty, present links and stop: the owner decides in the task card, never ask_clarification. '
                'After the owner approves, continue the delivery phase. When complete, present the source and stop. '
                'Do not set statuses or invent parameters. This smoke ends before final production policy validation.')
            with patch('righaven.audit_middleware.scope',return_value=(work,'Coordinator')),patch('righaven.audit_middleware.workspace_for',return_value=work):
                graph=create_agent(model,tools=[harness_journey,harness_delegate,read_file,ask_clarification],middleware=[ConversationAuditMiddleware()])
                first=graph.invoke({'messages':[system,HumanMessage('Create the synthetic sales dashboard now.')]},config={'recursion_limit':16})
                waiting=journeys.view(work)
                assert waiting['awaiting_owner']==['preview'] and executed==['build','review'],executed
                approved=journeys.decide(work,'preview',True,waiting['revision'])
                second=graph.invoke({'messages':[system,*first['messages'][1:],HumanMessage('The owner decision is saved. Read the current state and continue.')]},config={'recursion_limit':12})
                assert journeys.view(work)['complete'] and executed==['build','review','deliver'],executed
                assert (outputs/'source.sql').is_file() and approved['current']=='delivery'
                failures=[m for m in [*first['messages'],*second['messages']] if getattr(m,'type','')=='tool' and getattr(m,'status','')=='error']
                assert not failures,'Live coordinator used invalid control operations'
                print('Live coordinator control smoke OK: real provider, build/review, one owner decision, delivery, no repeated approvals or invalid calls')


if __name__=='__main__':main()
