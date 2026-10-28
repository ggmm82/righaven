"""Read actual cgroup limits/usage; absent counters remain unknown."""
from pathlib import Path


def snapshot(root='/sys/fs/cgroup'):
    root = Path(root)
    def number(name):
        try:
            text = (root / name).read_text().strip()
            return int(text) if text != 'max' else None
        except (OSError, ValueError):
            return None
    value = {'memory_bytes': number('memory.current'), 'memory_peak_bytes': number('memory.peak'),
             'memory_limit_bytes': number('memory.max'), 'oom_kills': None, 'cpu_seconds': None}
    for filename, key, field, scale in [('memory.events', 'oom_kill', 'oom_kills', 1), ('cpu.stat', 'usage_usec', 'cpu_seconds', 1000000)]:
        try:
            data = dict(line.split() for line in (root / filename).read_text().splitlines())
            value[field] = int(data[key]) / scale
        except (OSError, ValueError, KeyError):
            pass
    return value
