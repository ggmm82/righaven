"""Move managed SQLite storage out of the disposable Gateway filesystem."""
import fcntl
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile

import yaml


def configure(config_path, state_dir, *, working_directory=None):
    """Cut over before application imports; never overwrite two different stores.

    SQLite's backup API includes committed WAL contents. Keep the original file
    intact so a failed cutover cannot destroy the only surviving copy.
    Explicit external databases and custom absolute paths remain user-owned.
    """
    config_path, state_dir = Path(config_path), Path(state_dir).resolve()
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir/'database-migration.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        content = yaml.safe_load(config_path.read_text()) or {}
        database = content.get('database') or {}
        if database.get('backend') != 'sqlite':
            return
        configured = database.get('sqlite_dir', '.righaven/data')
        if not isinstance(configured, str) or configured.startswith('$'):
            return
        source_dir = Path(configured)
        managed = configured in ('/app/backend/.righaven/data', '/righaven-state/database')
        if source_dir.is_absolute() and not managed:
            return
        if not source_dir.is_absolute():
            source_dir = Path(working_directory or Path.cwd())/source_dir
        source_dir = source_dir.resolve()
        target_dir = state_dir/'database'
        if target_dir.is_symlink():
            raise ValueError('Persistent database directory must not be a symbolic link')
        target_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        source, target = source_dir/'righaven_core.db', target_dir/'righaven_core.db'
        if source != target and source.exists():
            if source.is_symlink() or target.is_symlink():
                raise ValueError('SQLite cutover refuses symbolic database links')
            if target.exists() and target.stat().st_size:
                raise ValueError('Both previous and persistent SQLite databases exist. Preserve both and resolve the conflict before starting.')
            descriptor, temporary = tempfile.mkstemp(prefix='sqlite-cutover-', suffix='.db', dir=target_dir)
            os.close(descriptor)
            try:
                with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as original, closing(sqlite3.connect(temporary)) as backup:
                    original.backup(backup)
                    if backup.execute('PRAGMA quick_check').fetchone() != ('ok',):
                        raise ValueError('SQLite backup integrity check failed')
                os.chmod(temporary, 0o600)
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)
        # The persistent config is updated only after a successful backup.
        if configured != str(target_dir):
            content['database'] = {**database, 'sqlite_dir':str(target_dir)}
            # Use atomic replacement and preserve YAML rather than changing its format.
            descriptor, temporary = tempfile.mkstemp(prefix='config-cutover-', suffix='.yaml', dir=config_path.parent)
            try:
                with os.fdopen(descriptor, 'w') as output:
                    yaml.safe_dump(content, output, allow_unicode=True, sort_keys=False)
                    output.flush(); os.fsync(output.fileno())
                os.replace(temporary, config_path)
            finally:
                Path(temporary).unlink(missing_ok=True)
