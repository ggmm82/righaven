#!/usr/bin/env python3
"""Install and natively verify an official release with packaged shell completions."""
import argparse,json,sys,tempfile,time,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import state,tool_versions as versions,environment_runtime as factory,docker_runtime as runtime


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tool',default='photocraft');parser.add_argument('--version',default='v0.16.0');args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='native-version-installation-') as temporary:
        root=Path(temporary);(root/'installation-id').write_text(uuid.uuid4().hex)
        with patch.object(state,'STATE',root),patch.object(runtime,'host_path',side_effect=str),patch.object(factory,'pinned',return_value=set()):
            try:
                job=versions.start(args.tool,args.version);file=versions.directory()/'jobs'/job['id']/'status.json'
                until=time.monotonic()+600
                while True:
                    value=json.loads(file.read_text())
                    if value['state'] in ('ready','failed'):break
                    if time.monotonic()>until:raise TimeoutError('Native version acceptance timed out')
                    time.sleep(.2)
                if value['state']!='ready':
                    if value.get('environment_id'):print(factory.preparation_text(value['environment_id']),file=sys.stderr)
                    raise AssertionError(value)
                revision=versions.read(value['revision']);record=factory.read(revision['environment_id'])
                proof=json.loads(runtime.docker('run','--rm','--network=none',record['image_id'],'cat','/opt/righaven/environment.json'))
                assert proof['verified'] and args.tool in proof['checks']['native_workflows'],proof
                target=runtime.docker('run','--rm','--network=none',record['image_id'],'readlink','/usr/local/bin/'+args.tool+'-cli')
                assert '/bin/'+args.tool+'-cli' in target and '/completions/' not in target,target
                print('Official release native OK:',args.tool,args.version,'; executable selected from bin, shell completion ignored, CLI registry and native source/export workflow passed.')
            finally:
                for file in factory.folder().glob('*.json'):
                    try:
                        record=factory.read(file.stem)
                        if record and record.get('status')=='ready':factory.evict(record['id'])
                    except (ValueError,__import__('subprocess').SubprocessError):pass


if __name__=='__main__':main()
