#!/usr/bin/env python3
"""Run the genuine pinned CLI without an account, network or generation."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

with tempfile.TemporaryDirectory() as directory:
    env={**os.environ,'HOME':directory,'AGY_CLI_DISABLE_AUTO_UPDATE':'true'}
    result=subprocess.run(['agy','--input-format','stream-json','--output-format','stream-json'],
        input=json.dumps({'event':'user','message':{'content':'Reply with OK'}})+'\n',
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode!=0,'Fresh home must require a real account'
    events=[json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert events[-1]['event']=='result' and events[-1]['result']['status']=='ERROR'
    assert 'authentication' in result.stderr.lower()
    print('Official agy: stdin stream protocol and explicit missing-account failure verified.')
