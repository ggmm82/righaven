"""OAuth workers receive private copies; stale refreshes cannot overwrite newer auth."""
import base64
import hashlib
import json
from pathlib import Path
import shutil
import time


def signature(path):
    if path.is_symlink():raise ValueError('Credenziali collegate non consentite')
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def expiring_codex(source):
    try:
        value=json.loads((source/'auth.json').read_text())
        token=value.get('tokens',{}).get('access_token','')
        encoded=token.split('.')[1]
        expiry=json.loads(base64.urlsafe_b64decode(encoded+'='*((-len(encoded))%4))).get('exp',0)
        return expiry<time.time()+1800
    except (OSError,ValueError,IndexError,TypeError):return False


class ApiCredentialSession:
    """Decrypt an API key only into a private, disposable worker mount."""
    def __init__(self, engine, destination, connection_id=None):
        from .state import credential_dir, custom_connection_path, atomic_json
        from .tenant_profiles import read_secret
        self.directory = Path(destination)
        self.directory.mkdir(parents=True, mode=0o700)
        self.directory.chmod(0o700)
        source = custom_connection_path(connection_id) if engine == 'openai' else credential_dir(engine)/'api.json'
        atomic_json(self.directory/'api.json', read_secret(source))

    def close(self):
        shutil.rmtree(self.directory, ignore_errors=True)


class CredentialSession:
    def __init__(self,engine,destination):
        from .docker_runtime import EXECUTION_LOCK,codex_account
        from .state import credential_dir
        from .run_agent import copy_credentials
        self.engine=engine;self.source=credential_dir(engine);self.directory=Path(destination)
        self.directory.mkdir(parents=True,mode=0o700)
        with EXECUTION_LOCK:
            if engine=='codex' and expiring_codex(self.source):codex_account(locked=True)
            copy_credentials(self.source,self.directory,engine)
            self.original={str(p.relative_to(self.directory)):signature(self.source/p.relative_to(self.directory))
                for p in self.directory.rglob('*') if p.is_file()}

    def close(self):
        from .docker_runtime import EXECUTION_LOCK
        from .state import atomic_json
        with EXECUTION_LOCK:
            # Compare the whole account snapshot, not individual rotating fields.
            if all(signature(self.source/name)==value for name,value in self.original.items()):
                for name in self.original:
                    path=self.directory/name
                    if not path.is_file() or path.is_symlink():continue
                    target=self.source/name
                    temporary=target.with_name(target.name+'.refresh')
                    shutil.copyfile(path,temporary);temporary.chmod(0o600);temporary.replace(target)
        shutil.rmtree(self.directory,ignore_errors=True)
