"""Who used which machine, how and how much: one row per finished assignment."""
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3

from . import state

logger = logging.getLogger(__name__)
COLUMNS = ('job_id', 'user_id', 'thread_id', 'started_at', 'finished_at', 'duration_seconds', 'role', 'agent', 'engine', 'model',
           'profile', 'mode', 'environment_id', 'tools', 'cpu_seconds', 'memory_peak_bytes', 'outcome')


def database():
    path = state.STATE / 'usage-ledger.sqlite3'
    if path.is_symlink():
        raise ValueError('Registro d’uso non valido')
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5)
    conn.execute('CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, user_id TEXT, thread_id TEXT, started_at TEXT, finished_at TEXT, '
                 'duration_seconds REAL, role TEXT, agent TEXT, engine TEXT, model TEXT, profile TEXT, mode TEXT, environment_id TEXT, '
                 'tools TEXT, cpu_seconds REAL, memory_peak_bytes INTEGER, outcome TEXT)')
    conn.execute('CREATE INDEX IF NOT EXISTS jobs_finished ON jobs(finished_at)')
    return conn


def owner(workspace):
    """users/<user>/threads/<thread>/user-data -> (user, thread); legacy layouts stay anonymous."""
    path = Path(workspace)
    if path.name == 'user-data' and path.parent.parent.name == 'threads' and path.parents[3].name == 'users':
        return path.parents[2].name, path.parent.name
    return '', path.parent.name if path.name == 'user-data' else ''


def _seconds(start, end):
    try:
        return max(0.0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    except (TypeError, ValueError):
        return None


def record(workspace, status):
    """Store a finished assignment once; failures never affect the assignment itself."""
    try:
        user, thread = owner(workspace)
        environment = status.get('environment') or {}
        profile = environment.get('profile') or {}
        resources = status.get('resources') or {}
        started = status.get('started_at') or status.get('created_at', '')
        row = {'job_id': status.get('job_id', ''), 'user_id': user, 'thread_id': thread, 'started_at': started,
               'finished_at': status.get('finished_at', ''), 'duration_seconds': _seconds(started, status.get('finished_at')),
               'role': status.get('role_title') or status.get('agent', ''), 'agent': status.get('agent', ''),
               'engine': status.get('engine', ''), 'model': status.get('model', ''), 'profile': profile.get('profile', ''),
               'mode': profile.get('mode') or ('core' if not environment.get('tools') else 'dedicated'),
               'environment_id': environment.get('id', ''), 'tools': json.dumps(environment.get('tools', [])),
               'cpu_seconds': resources.get('cpu_seconds'), 'memory_peak_bytes': resources.get('memory_peak_bytes'),
               'outcome': status.get('phase', '')}
        if not row['job_id']:
            return False
        with closing(database()) as conn, conn:
            conn.execute('INSERT OR REPLACE INTO jobs (' + ','.join(COLUMNS) + ') VALUES (' + ','.join('?' * len(COLUMNS)) + ')',
                         [row[c] for c in COLUMNS])
        return True
    except (OSError, ValueError, sqlite3.Error):
        logger.warning('Registro d’uso non aggiornato')
        return False


def report(user_id=None, days=30, limit=100):
    """Aggregates per machine and per user plus the latest assignments; user_id=None means every user."""
    if type(days) is not int or not 1 <= days <= 366:
        raise ValueError('Periodo tra 1 e 366 giorni')
    since = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - days * 86400, timezone.utc).isoformat()
    where, args = 'finished_at >= ?', [since]
    if user_id is not None:
        where += ' AND user_id = ?'
        args.append(user_id)
    with closing(database()) as conn:
        conn.row_factory = sqlite3.Row
        machine = "CASE WHEN profile != '' THEN profile WHEN mode = 'core' THEN '' ELSE 'dedicated' END"
        totals = dict(conn.execute('SELECT COUNT(*) AS jobs, COALESCE(SUM(duration_seconds),0) AS seconds, COALESCE(SUM(cpu_seconds),0) AS cpu_seconds, '
                                   'MAX(memory_peak_bytes) AS memory_peak_bytes FROM jobs WHERE ' + where, args).fetchone())
        def grouped(key):
            return [dict(r) for r in conn.execute(
                'SELECT ' + key + ' AS name, COUNT(*) AS jobs, COALESCE(SUM(duration_seconds),0) AS seconds, COALESCE(SUM(cpu_seconds),0) AS cpu_seconds, '
                'MAX(memory_peak_bytes) AS memory_peak_bytes, MAX(finished_at) AS last_at, COUNT(DISTINCT user_id) AS users, '
                "SUM(mode = 'reused') AS reused, SUM(mode = 'extended') AS extended, SUM(outcome = 'completed') AS completed "
                'FROM jobs WHERE ' + where + ' GROUP BY ' + key + ' ORDER BY seconds DESC', args)]
        jobs = [dict(r) for r in conn.execute('SELECT * FROM jobs WHERE ' + where + ' ORDER BY finished_at DESC LIMIT ?', [*args, limit])]
        result = {'days': days, 'totals': totals, 'machines': grouped(machine), 'users': grouped('user_id') if user_id is None else [],
                  'roles': grouped('role'), 'jobs': jobs}
    for job in jobs:
        job['tools'] = json.loads(job['tools'] or '[]')
    return result
