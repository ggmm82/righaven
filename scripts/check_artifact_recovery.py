"""Offline runtime proof: saved native source survives AI failure without credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    root = Path('/mnt/user-data/outputs/workspace/rh-job-123456abcdef')
    root.mkdir(parents=True)
    os.environ['RIGHAVEN_OUTPUT_DIR'] = str(root)
    source = root/'model.d2'; source.write_text('idea: Idea\nresult: Result\nidea -> result: resolves\n')
    job = {'agent':'workspace','run_id':root.name,'engine':'codex','purpose':'delivery',
           'role':{'tools':['d2']},'capability_policy':{'allowed':['d2'],'blocked':[]}}
    Path('/job.json').write_text(json.dumps(job))
    rendered = root/'rendered'
    subprocess.run(['d2-cli','call','render',json.dumps({'input':str(source),'output':str(rendered)})],check=True,capture_output=True,text=True)
    export = rendered/'diagram.svg'
    def item(path, role):
        return {'path':str(path),'role':role,'format':path.suffix[1:].upper(),'open_with':'D2 or SVG viewer',
            'editability':'D2 source and derived SVG','reopen':{'status':'passed','evidence':'Rendered with native D2'},'limitations':[]}
    manifest = {'task':'Saved diagram','source_files':[],'output_files':[str(source),str(export)],'previews':[],
        'checks':[{'name':'Native rendering','status':'passed','evidence':'D2 produced a visible SVG'}],'warnings':[],
        'delivery':{'source_status':'included','source_note':'Native editable source included','files':[item(source,'editable_source'),item(export,'export')],
            'components':[{'name':'Diagram','tool':'d2','artifacts':[{'path':str(export)}],'sources':[{'path':str(source)}]}]}}
    (root/'handoff.json').write_text(json.dumps(manifest))
    hashes = {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,export)}
    command = [sys.executable,'/opt/righaven-worker/run_agent.py','--finalize','/job.json']
    result = subprocess.run(command,capture_output=True,text=True,timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
    value = json.loads(result.stdout)
    assert value['ok'] and value['delivery_record']['technical_status']=='passed',value
    assert value['quality_review'] is None  # Native reopening cannot invent approval.
    assert next(f for f in value['delivery_record']['files'] if f['role']=='editable_source')['verification']['status']=='passed'
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
    source.unlink()
    failed = subprocess.run(command,capture_output=True,text=True,timeout=30)
    assert failed.returncode != 0 and json.loads(failed.stdout)['ok'] is False
    print('Artifact recovery OK: native D2 reopened offline, no credentials, identical saved files, no invented review; missing source rejected')


if __name__ == '__main__':
    main()
