"""Official Claude Code CLI only; no OAuth-token replay against a model API."""
import json
import os
from pathlib import Path
import subprocess
import sys


def environment():
    return {**os.environ,'CLAUDE_CONFIG_DIR':str(Path('/root/.claude')),'DISABLE_AUTOUPDATER':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}


def command(model,schema=None,worker=False):
    args=['claude','--print','--verbose','--output-format','stream-json','--no-session-persistence',
          '--setting-sources','','--strict-mcp-config','--mcp-config','{"mcpServers":{}}']
    if model:args+=['--model',model]
    if worker:
        args+=['--permission-mode','acceptEdits','--tools','Bash,Read,Write,Edit,Glob,Grep','--allowedTools','Bash,Read,Write,Edit,Glob,Grep','--add-dir','/mnt/user-data']
    else:args+=['--tools','','--max-turns','8']
    if schema:args+=['--json-schema',json.dumps(schema)]
    return args


def envelope(output):
    events=[]
    for line in output.splitlines():
        try:event=json.loads(line)
        except ValueError:continue
        if isinstance(event,dict) and event.get('type')=='result':events.append(event)
    if not events:raise RuntimeError('Claude Code returned no final result; inspect CLI progress')
    result=events[-1]
    if result.get('is_error') or result.get('subtype') not in (None,'success'):
        raise RuntimeError('Claude Code did not complete the request; check account, selected model, quota and CLI progress')
    return {'status':'SUCCESS','structured_output':result.get('structured_output') or {},
            'result':result.get('result',''),'usage':result.get('usage',{})}


def generate(payload):
    result=subprocess.run(command(payload.get('model'),payload['schema']),input=payload['prompt'],
        capture_output=True,text=True,env=environment(),cwd='/tmp',timeout=1530)
    if result.returncode:raise RuntimeError('Claude Code request failed; check official login, model and quota')
    final=envelope(result.stdout)
    value=final['structured_output']
    if not value:
        try:value=json.loads(final['result'])
        except ValueError:raise RuntimeError('Claude Code returned invalid structured output') from None
    return {**value,'usage':final['usage']}


def main():
    from run_agent import copy_credentials
    root=Path('/root/.claude');copy_credentials(Path('/credentials'),root,'claude')
    try:
        if sys.argv[1]=='--status':
            status=subprocess.run(['claude','auth','status'],capture_output=True,text=True,env=environment(),timeout=45)
            if status.returncode:raise RuntimeError('Claude Code account is not connected')
            print(json.dumps({'ok':True,'authenticated':True}))
        else:print(json.dumps({'ok':True,'response':generate(json.loads(Path(sys.argv[1]).read_text()))}))
    finally:copy_credentials(root,Path('/credentials'),'claude')


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'ok':False,'error':str(error) if isinstance(error,RuntimeError) else 'Claude Code unavailable; inspect account and CLI configuration'}));sys.exit(1)
