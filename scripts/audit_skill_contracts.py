"""Audit every shipped skill and executable adapter, including deferred imports."""
import ast
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def audit():
    errors=[];skills=list((ROOT/'skills/custom').glob('*/SKILL.md'))
    from yaml import safe_load
    known={app['id'] for app in json.loads((ROOT/'versions.lock.json').read_text())['applications']}
    for file in skills:
        text=file.read_text();front=re.match(r'^---\s*\n(.*?)\n---',text,re.S)
        if not front:errors.append(f'{file.relative_to(ROOT)}: missing metadata');continue
        metadata=safe_load(front[1])
        if metadata.get('name')!=file.parent.name:errors.append(f'{file.relative_to(ROOT)}: name differs from directory')
        for target in re.findall(r'\]\(([^)]+)\)',text):
            if ':' in target or target.startswith('#'):continue
            target=target.split('#')[0]
            if target and not (file.parent/target).is_file():errors.append(f'{file.relative_to(ROOT)}: missing reference {target}')
    # Import roots are determined by the current source tree, not a compatibility alias.
    public_roots={path.stem for path in ROOT.iterdir() if path.is_dir()}
    for file in (ROOT/'righaven').glob('*.py'):
        tree=ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='__import__' and node.args and isinstance(node.args[0],ast.Constant):
                name=node.args[0].value
                if isinstance(name,str) and '.' in name:
                    import importlib.util
                    try:found=importlib.util.find_spec(name.split('.')[0])
                    except (ImportError,ValueError):found=None
                    if name.split('.')[0] not in public_roots and found is None:errors.append(f'{file.relative_to(ROOT)}:{node.lineno}: unavailable dynamic module {name}')
    expected={'skill-'+tool for tool in known}|{'skill-workspace','skill-harness','skill-quality-review','skill-problem-solving'}
    errors.extend('Missing skill: '+name for name in sorted(expected-{p.parent.name for p in skills}))
    if errors:raise SystemExit('\n'.join(errors))
    print(f'Skill contracts verified: {len(skills)} skills, local references and deferred adapter imports')

if __name__=='__main__':audit()
