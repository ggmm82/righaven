"""Run a supervised renderer from the captured source project directory."""
import json
from pathlib import Path
import subprocess
import sys

data=json.loads(Path(sys.argv[1]).read_text())
subprocess.run(data['argv'],cwd=data['cwd'],check=True)
