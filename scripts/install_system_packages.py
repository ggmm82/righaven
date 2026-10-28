"""Install only the curated Debian dependencies of the selected locked tools."""
import json,re,subprocess
from pathlib import Path


def packages(root,tools):
    mapping=json.loads((Path(root)/'toolkit-lock/system-packages.json').read_text())
    unknown=set(tools)-set(mapping)
    if unknown:raise ValueError('System dependencies not declared: '+', '.join(sorted(unknown)))
    selected=sorted({p for t in tools for p in mapping[t]})
    if any(not isinstance(p,str) or not re.fullmatch(r'[a-z0-9][a-z0-9+.-]*',p) for p in selected):
        raise ValueError('Invalid curated system package')
    return selected


def install(root,tools):
    selected=packages(root,tools)
    if not selected:return
    rows=subprocess.check_output(['dpkg-query','-W','-f=${binary:Package} ${db:Status-Status}\n'],text=True).splitlines()
    installed={line.split()[0].split(':')[0]+' installed' for line in rows if line.endswith(' installed')}
    missing=[p for p in selected if p+' installed' not in installed]
    if not missing:return
    print('System dependencies for '+', '.join(sorted(tools))+': '+', '.join(missing),flush=True)
    subprocess.run(['apt-get','update'],check=True)
    subprocess.run(['apt-get','install','-y','--no-install-recommends',*missing],check=True,
        env={**__import__('os').environ,'DEBIAN_FRONTEND':'noninteractive'})
