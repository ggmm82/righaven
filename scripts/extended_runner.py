"""Preserve complete native stdout/stderr and an explicit working directory."""
import json,os,subprocess,sys
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_text())
with Path(spec['stdout']).open('wb') as out,Path(spec['stderr']).open('wb') as err:
    result=subprocess.run(spec['argv'],cwd=spec['cwd'],stdout=out,stderr=err,
        env={**os.environ,**spec.get('env',{})})
sys.exit(result.returncode)
