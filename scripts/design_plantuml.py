"""Controlled stdin bridge for the native PlantUML CLI."""
import json,os,subprocess,sys
from pathlib import Path
value=json.loads(Path(sys.argv[1]).read_text())
result=subprocess.run(['java','-Xmx384m','-Djava.awt.headless=true','-DPLANTUML_SECURITY_PROFILE=SECURE','-jar',value['jar'],'-tsvg','-pipe','-failfast2','-charset','UTF-8'],input=Path(value['source']).read_bytes(),capture_output=True,timeout=180)
if result.returncode:raise RuntimeError('PlantUML: '+result.stderr.decode(errors='replace')[-1800:])
Path(value['target']).write_bytes(result.stdout)
