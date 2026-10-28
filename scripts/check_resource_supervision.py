#!/usr/bin/env python3
"""Real cgroup OOM proof in a dedicated 256 MiB container; no model or account."""
import json
import sys
import tempfile

sys.path.insert(0, '/opt/righaven-worker')
from operations import supervise
from resource_usage import snapshot

before = snapshot()
assert before['memory_limit_bytes'] and before['memory_limit_bytes'] <= 268435456, 'Run only inside the dedicated 256 MiB test container'
with tempfile.TemporaryDirectory() as root:
    result, status = supervise([sys.executable, '-c', 'x=bytearray(768*1024*1024);print(len(x))'], root, 'oom-test', timeout=30)
    assert result.returncode != 0, result.returncode
    assert status['state'] == 'out_of_memory' and status['oom_kills'] > 0, status
    print(json.dumps({'verified': True, 'state': status['state'], 'oom_kills': status['oom_kills']}))
