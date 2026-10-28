"""Offline worker-image check: native method packages need no app installation."""
import json,shutil,sys,tempfile
from pathlib import Path
sys.path.insert(0,'/opt/righaven-worker')
from skill_composition import package_revision
from run_agent import verify_project_context


assert json.loads(Path('/opt/righaven/installed.json').read_text())==[]
name='skill-problem-solving';source=Path('/mnt/skills/custom')/name
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);projection=root/'skills';projection.mkdir()
    shutil.copytree(source,projection/name)
    protocol=Path('/mnt/skills/custom/skill-workspace')
    shutil.copytree(protocol,projection/protocol.name)
    role={'skill_bindings':[{'name':name,'revision':package_revision(source),'tools':[]}],
          'package_bindings':[{'name':protocol.name,'revision':package_revision(protocol)}]}
    job={'role':role,'environment':{'skill_revision':package_revision(projection,require_skill=False)}}
    verify_project_context(job,root,projection)
    (projection/'extra.txt').write_text('Unexpected projection content')
    try:verify_project_context(job,root,projection)
    except ValueError:pass
    else:raise AssertionError('Worker accepted an unexpected projected file')
    (projection/'extra.txt').unlink()
    (projection/name/'SKILL.md').write_text('Changed after compilation')
    try:verify_project_context(job,root,projection)
    except ValueError:pass
    else:raise AssertionError('Worker accepted a changed method package')
print('Worker composition OK: zero apps installed; actual native method verified; modified package rejected without credentials or generation.')
