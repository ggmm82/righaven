#!/usr/bin/env python3
"""A cold builder must use the published stage without rerunning installers."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.software_image import fingerprint


def main():
    repo=Path(__file__).resolve().parents[1]
    selection=json.loads((repo/'reports/software-image.json').read_text())
    if not selection['reuse']:
        print('New software recipe: cold-builder reuse will apply once this verified version is published.')
        return
    before=fingerprint(repo)
    with tempfile.TemporaryDirectory(prefix='software-reuse-') as directory:
        root=Path(directory)
        # Copy only recipe inputs; an unrelated worker/frontend change cannot
        # become part of the software fingerprint by accident.
        from scripts.software_image import inputs
        for name in [*inputs(repo)['files'],'docker/Dockerfile.sandbox']:
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(repo/name,target)
        (root/'righaven').mkdir();(root/'righaven/run_agent.py').write_text('# changed worker release\n')
        (root/'frontend').mkdir();(root/'frontend/new.tsx').write_text('// changed UI\n')
        assert fingerprint(root)==before
        dockerfile=root/'Dockerfile.probe'
        dockerfile.write_text('FROM scratch AS software\nRUN exit 99\nFROM software AS core\nRUN python3 -c "print(123)"\n')
        tag='skill-software-reuse-check:local'
        try:
            # --no-cache plus a deliberately failing local software stage prove
            # that reuse comes from a pinned published image, not GHA cache.
            subprocess.run(['docker','buildx','build','--no-cache','--load','--target','core',
                '--build-context',selection['context'],'--file',str(dockerfile),'--tag',tag,str(root)],check=True,timeout=180)
            subprocess.run(['docker','run','--rm','--network=none',tag,'python3','-c','from pathlib import Path;assert not Path("/opt/righaven-worker/run_agent.py").exists()'],check=True)
        finally:subprocess.run(['docker','image','rm','--no-prune',tag],check=False,stdout=subprocess.DEVNULL)
    print('Published software reuse OK: changed worker and UI keep the same inputs; a cold builder never runs the local installer stage.')


if __name__=='__main__':main()
