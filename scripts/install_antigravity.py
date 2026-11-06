#!/usr/bin/env python3
"""Install the pinned official native agy release, verifying the pinned SHA-512 and publisher SHA-256."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import urllib.request


def install(arch, destination='/usr/local/bin/agy'):
    lock = json.loads((Path(__file__).with_name('antigravity.lock.json')).read_text())
    release = lock['platforms'][arch]
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / 'agy.tar.gz'
        with urllib.request.urlopen(release['url'], timeout=120) as response, archive.open('wb') as output:
            import shutil
            shutil.copyfileobj(response, output)
        if hashlib.sha512(archive.read_bytes()).hexdigest() != release['sha512']:
            raise ValueError('Checksum Antigravity non valido')
        if hashlib.sha256(archive.read_bytes()).hexdigest() != release['sha256']:
            raise ValueError('Checksum SHA-256 Antigravity non valido')
        with tarfile.open(archive) as payload:
            stream = payload.extractfile('antigravity')
            target = Path(destination)
            target.write_bytes(stream.read())
            target.chmod(0o755)
    print('Official Antigravity CLI installed:', lock['version'], arch)


if __name__ == '__main__':
    install(sys.argv[1])
