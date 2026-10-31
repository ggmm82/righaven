"""Who used which machine, how and how much: one row per finished assignment."""
from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import sqlite3

from . import model_prices, state

logger = logging.getLogger(__name__)
COLUMNS = ('job_id', 'user_id', 'thread_id', 'started_at', 'finished_at', 'duration_seconds', 'role', 'agent', 'engine', 'model',
           'profile', 'mode', 'environment_id', 'tools', 'cpu_seconds', 'memory_peak_bytes', 'outcome',
           'input_tokens', 'cached_tokens', 'output_tokens', 'reasoning_tokens', 'error_code')
ADDED = {'input_tokens': 'INTEGER', 'cached_tokens': 'INTEGER', 'output_tokens': 'INTEGER', 'reasoning_tokens': 'INTEGER', 'error_code': 'TEXT'}
QUOTA_HOURS = 24


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
    present = {row[1] for row in conn.execute('PRAGMA table_info(jobs)')}
    for column, kind in ADDED.items():
        if column not in present:
            conn.execute(f'ALTER TABLE jobs ADD COLUMN {column} {kind}')
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
               'outcome': status.get('phase', ''), 'error_code': status.get('error_code') or ''}
        tokens = status.get('tokens') if isinstance(status.get('tokens'), dict) else {}
        for column, key in (('input_tokens', 'input'), ('cached_tokens', 'cached_input'), ('output_tokens', 'output'), ('reasoning_tokens', 'reasoning')):
            row[column] = tokens.get(key) if type(tokens.get(key)) is int else None
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
    prices = model_prices.load()
    with closing(database()) as conn:
        conn.row_factory = sqlite3.Row
        machine = "CASE WHEN profile != '' THEN profile WHEN mode = 'core' THEN '' ELSE 'dedicated' END"
        tokens = ('COALESCE(SUM(input_tokens),0) AS input_tokens, COALESCE(SUM(cached_tokens),0) AS cached_tokens, '
                  'COALESCE(SUM(output_tokens),0) AS output_tokens, COALESCE(SUM(reasoning_tokens),0) AS reasoning_tokens')
        totals = dict(conn.execute('SELECT COUNT(*) AS jobs, COALESCE(SUM(duration_seconds),0) AS seconds, COALESCE(SUM(cpu_seconds),0) AS cpu_seconds, '
                                   'MAX(memory_peak_bytes) AS memory_peak_bytes, ' + tokens + ' FROM jobs WHERE ' + where, args).fetchone())
        def grouped(key):
            return [dict(r) for r in conn.execute(
                'SELECT ' + key + ' AS name, COUNT(*) AS jobs, COALESCE(SUM(duration_seconds),0) AS seconds, COALESCE(SUM(cpu_seconds),0) AS cpu_seconds, '
                'MAX(memory_peak_bytes) AS memory_peak_bytes, MAX(finished_at) AS last_at, COUNT(DISTINCT user_id) AS users, '
                "SUM(mode = 'reused') AS reused, SUM(mode = 'extended') AS extended, SUM(outcome = 'completed') AS completed, " + tokens + ' '
                'FROM jobs WHERE ' + where + ' GROUP BY ' + key + ' ORDER BY seconds DESC', args)]

        def costs(key):
            """Estimated cost per group, summed over the models used in it; None when no model has a price."""
            values = {}
            for row in conn.execute('SELECT ' + key + ' AS name, model, SUM(input_tokens) AS i, SUM(cached_tokens) AS c, SUM(output_tokens) AS o '
                                    'FROM jobs WHERE ' + where + ' GROUP BY ' + key + ', model', args):
                amount = model_prices.cost(prices, row['model'], row['i'], row['c'], row['o'])
                if amount is not None:
                    values[row['name']] = round(values.get(row['name'], 0) + amount, 6)
            return values

        def with_cost(rows, key):
            amounts = costs(key)
            return [{**row, 'cost': amounts.get(row['name'])} for row in rows]
        jobs = [dict(r) for r in conn.execute('SELECT * FROM jobs WHERE ' + where + ' ORDER BY finished_at DESC LIMIT ?', [*args, limit])]
        totals['cost'] = costs("''").get('')
        quota_since = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() - QUOTA_HOURS * 3600, timezone.utc).isoformat()
        quota = [dict(r) for r in conn.execute(
            "SELECT engine, model, COUNT(*) AS jobs, COUNT(DISTINCT user_id) AS users, MAX(finished_at) AS last_at FROM jobs "
            "WHERE error_code = 'provider_quota' AND finished_at >= ?" + (' AND user_id = ?' if user_id is not None else '') +
            ' GROUP BY engine, model ORDER BY last_at DESC', [quota_since, *([user_id] if user_id is not None else [])])]
        result = {'days': days, 'currency': prices['currency'], 'priced_models': sorted(prices['models']), 'totals': totals,
                  'machines': with_cost(grouped(machine), machine), 'users': with_cost(grouped('user_id'), 'user_id') if user_id is None else [],
                  'roles': with_cost(grouped('role'), 'role'), 'models': with_cost(grouped('model'), 'model'), 'jobs': jobs, 'quota_alerts': quota}
    for job in jobs:
        job['tools'] = json.loads(job['tools'] or '[]')
        job['cost'] = model_prices.cost(prices, job['model'], job['input_tokens'], job['cached_tokens'], job['output_tokens']) \
            if job.get('input_tokens') is not None or job.get('output_tokens') is not None else None
    return result
