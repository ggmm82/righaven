"""Fail early on broken local frontend imports after pruning optional surfaces."""
from pathlib import Path
import re
import shlex

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'core/frontend/src'


def check():
    files = {str(path.relative_to(SOURCE)): path for path in SOURCE.rglob('*') if path.is_file()}
    # UI integrations are copied into the same source tree before Next.js builds.
    for line in (ROOT/'docker/Dockerfile.frontend').read_text().splitlines():
        if not line.startswith('COPY frontend/'):
            continue
        parts = shlex.split(line)
        destination = parts[-1]
        if not destination.startswith('./frontend/src/'):
            continue
        target = destination.removeprefix('./frontend/src/')
        for source in parts[1:-1]:
            path = ROOT/source
            if path.is_dir():
                for child in path.rglob('*'):
                    if child.is_file(): files[target+'/'+str(child.relative_to(path))] = child
            else:
                files[target+path.name if target.endswith('/') else target] = path
    missing = []
    pattern = re.compile(r'''(?:from\s*|import\s*\(\s*|import\s*)["'](@/[^"']+)["']''')
    for name, path in files.items():
        if path.suffix not in ('.ts','.tsx','.js','.jsx'):
            continue
        for match in pattern.finditer(path.read_text()):
            module = match[1][2:]
            candidates = [module]+[module+ext for ext in ('.ts','.tsx','.js','.jsx','.json')]+[module+'/index'+ext for ext in ('.ts','.tsx','.js')]
            if not any(candidate in files for candidate in candidates):
                missing.append(f'{name}: {match[1]}')
    if missing:
        raise SystemExit('Unresolved frontend imports:\n'+'\n'.join(sorted(set(missing))))
    print(f'Frontend source imports resolve across {len(files)} files, including build integrations')


if __name__ == '__main__':
    check()
