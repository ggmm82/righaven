"""Launch Lab with a durable, writable project kernel, separate from server deps."""
import json
import os
from pathlib import Path
import sys
import sysconfig
import venv


def launch(arguments):
    home=Path(os.environ['HOME']);home.mkdir(parents=True,exist_ok=True)
    kernel=Path(os.environ.get('RIGHAVEN_EDITOR_KERNEL_ROOT','/workspace/python'))
    if not (kernel/'bin/python').is_file():
        venv.EnvBuilder(with_pip=True,system_site_packages=True).create(kernel)
    # Same interpreter ABI as the interface. The kernel sees ipykernel and
    # widgets from the immutable server without copying or modifying them.
    site=kernel/'lib'/('python'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))/'site-packages'
    site.mkdir(parents=True,exist_ok=True)
    (site/'righaven-interface.pth').write_text(sysconfig.get_path('purelib')+'\n')
    specs=home/'.local/share/jupyter/kernels/python3';specs.mkdir(parents=True,exist_ok=True)
    (specs/'kernel.json').write_text(json.dumps({'argv':[str(kernel/'bin/python'),'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Project Python','language':'python'}))
    os.environ['JUPYTER_PREFER_ENV_PATH']='0'
    os.environ['PATH']=str(kernel/'bin')+':'+os.environ['PATH']
    os.execv(str(Path(sys.prefix)/'bin/jupyter'),['jupyter','lab',*arguments])


if __name__=='__main__':launch(sys.argv[1:])
