"""Verify a prepared browser helper under actual role capability masks."""
import json,subprocess,sys,tempfile
from pathlib import Path


def main():
    if len(sys.argv)>1 and sys.argv[1]=='--inside':
        sys.path.insert(0,'/opt/righaven')
        from acceptance import Case
        from acceptance_extended import CASES
        assert not Path('/opt/righaven/toolkit/node_modules/playwright').exists()
        known=json.loads(subprocess.check_output(['craft','list'],text=True))
        assert {r['id'] for r in known}=={'axe-core'},known
        denied=subprocess.run(['craft','commands','playwright'],capture_output=True)
        assert denied.returncode!=0
        case=Case(Path('/mnt/user-data/outputs'),'axe-core');CASES['axe-core'](case)
        print('Scoped axe-core native OK: real browser audit works with standalone Playwright capability disabled')
        return
    root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
    from righaven.capability_policy import policy_from_names,worker_arguments
    policy=policy_from_names({'skill-axe-core'})
    with tempfile.TemporaryDirectory(prefix='axe-scope-') as temp:
        folder=Path(temp);blocker=folder/'disabled';blocker.write_text('#!/bin/sh\necho "Disabled capability" >&2\nexit 126\n');blocker.chmod(0o755)
        job=folder/'job.json';job.write_text(json.dumps({'agent':'workspace','capability_policy':policy}));job.chmod(0o644)
        subprocess.run(['docker','run','--rm','--init','--network=none','--memory=1536m','--cpus=1.5','--pids-limit=256',
          '--cap-drop=ALL','--security-opt=no-new-privileges',*worker_arguments(policy,blocker),
          '--mount',f'type=bind,src={root},dst=/review,readonly','--mount',f'type=bind,src={job},dst=/job.json,readonly',
          '--entrypoint','python3',sys.argv[1],'/review/scripts/check_extended_worker_scope.py','--inside'],check=True)


if __name__=='__main__':main()
