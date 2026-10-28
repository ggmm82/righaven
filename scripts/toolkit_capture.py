"""Keep machine-readable native stdout complete, separate from bounded UI logs."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    output, encoded = sys.argv[1:]
    argv = json.loads(encoded)
    if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
        raise ValueError('Expected an explicit argument vector')
    with Path(output).open('xb') as stream:
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=stream, stderr=sys.stderr)
    return result.returncode


if __name__ == '__main__':sys.exit(main())
