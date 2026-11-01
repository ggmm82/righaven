"""Exercise the real app-owned package verification tool in the isolated CI Compose only."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,'/app/backend')
from righaven import state,environment_runtime,docker_runtime,package_checks


def main():
    if os.environ.get('RIGHAVEN_CI_PACKAGE_CHECK')!='1':raise RuntimeError('CI package check is disabled')
    with tempfile.TemporaryDirectory(dir=state.STATE,prefix='ci-package-') as directory:
        root=Path(directory);outputs=root/'outputs';outputs.mkdir();outputs.chmod(0o777)
        limits={'cpus':2,'memory_mib':4096,'max_workers':1,'timeout':900,'tmp_mib':512}
        with patch('righaven.runtime_settings.effective',return_value=limits):
            ready=environment_runtime.ensure(['sqlglot'])
            code="""import sys
from pathlib import Path
sys.path[:0]=['/opt/righaven']
from acceptance_pipeline import MODEL
import pipeline_scaffold
pipeline_scaffold.scaffold(MODEL,Path('/out'),target='postgres',source_dialect='postgres',name='verified',schedule={'ingest':'@hourly','stubs':'@hourly','transform':'@hourly','transform_model_cron':'@hourly'})
"""
            subprocess.run(['docker','run','--rm','--network=none','--mount',docker_runtime.mount(outputs,'/out',False),
                            *docker_runtime.runtime_arguments(),ready['image_id'],'/opt/righaven/apps/sqlglot/venv/bin/python','-c',code],check=True)
            result=package_checks.check(root,str(outputs/'package'))
            if result['status']!='passed':
                for log in outputs.rglob('*.log'):print(log.read_text()[-12000:])
                raise AssertionError(result)
            print('Gateway package verifier OK: real BuildKit limits, synthetic cycles, retained report, no production access')


if __name__=='__main__':main()
