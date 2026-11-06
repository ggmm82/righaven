"""Durable organization admission, using native user identities.

SQLite transactions make concurrent Gateway processes share one admission ledger.
This counts completed/failed jobs and active reservations, not estimates of tokens.
"""
from contextlib import contextmanager
import hashlib
import sqlite3
import time
import uuid
from . import state


@contextmanager
def database():
    state.STATE.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(state.STATE / 'organizations.sqlite', timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS organizations (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, max_parallel INTEGER NOT NULL DEFAULT 2,
          jobs_per_month INTEGER NOT NULL DEFAULT 1000);
        CREATE TABLE IF NOT EXISTS memberships (
          user_id TEXT PRIMARY KEY, organization_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS organization_jobs (
          id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, user_id TEXT NOT NULL,
          started REAL NOT NULL, finished REAL, outcome TEXT, elapsed_seconds REAL);
        ''')
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def organization(db, user_id):
    if not isinstance(user_id, str) or not user_id or len(user_id) > 128:
        raise ValueError('A native user identity is required')
    member = db.execute('SELECT organization_id FROM memberships WHERE user_id=?', (user_id,)).fetchone()
    if member:
        return member[0]
    identifier = 'org-' + hashlib.sha256(user_id.encode()).hexdigest()[:32]
    db.execute('INSERT OR IGNORE INTO organizations(id,owner) VALUES (?,?)', (identifier,user_id))
    db.execute('INSERT INTO memberships VALUES (?,?)', (user_id,identifier))
    return identifier


def snapshot(user_id):
    with database() as db:
        identifier = organization(db, user_id)
        result = dict(db.execute('SELECT * FROM organizations WHERE id=?',(identifier,)).fetchone())
        month = time.strftime('%Y-%m-01', time.gmtime())
        result['used_jobs'] = db.execute("SELECT count(*) FROM organization_jobs WHERE organization_id=? AND started>=strftime('%s',?)",(identifier,month)).fetchone()[0]
        result['active_jobs'] = db.execute('SELECT count(*) FROM organization_jobs WHERE organization_id=? AND finished IS NULL',(identifier,)).fetchone()[0]
        result['measured_job_seconds'] = db.execute('SELECT coalesce(sum(elapsed_seconds),0) FROM organization_jobs WHERE organization_id=?',(identifier,)).fetchone()[0]
        return result


def configure(user_id, max_parallel, jobs_per_month):
    if type(max_parallel) is not int or not 1 <= max_parallel <= 64:
        raise ValueError('max_parallel must be between 1 and 64')
    if type(jobs_per_month) is not int or not 0 <= jobs_per_month <= 1000000:
        raise ValueError('Invalid monthly job allowance')
    with database() as db:
        identifier = organization(db,user_id)
        db.execute('UPDATE organizations SET max_parallel=?,jobs_per_month=? WHERE id=?', (max_parallel,jobs_per_month,identifier))
    return snapshot(user_id)


def recover_after_cleanup():
    """Called only after the single Gateway has reclaimed its old workers."""
    if not (state.STATE / 'organizations.sqlite').exists():
        return
    with database() as db:
        now = time.time()
        db.execute("UPDATE organization_jobs SET finished=?,elapsed_seconds=?-started,outcome='interrupted' WHERE finished IS NULL", (now,now))


@contextmanager
def admission(user_id):
    identifier = uuid.uuid4().hex
    with database() as db:
        org = organization(db,user_id)
        limits = db.execute('SELECT * FROM organizations WHERE id=?',(org,)).fetchone()
        active = db.execute('SELECT count(*) FROM organization_jobs WHERE organization_id=? AND finished IS NULL',(org,)).fetchone()[0]
        month = time.strftime('%Y-%m-01',time.gmtime())
        used = db.execute("SELECT count(*) FROM organization_jobs WHERE organization_id=? AND started>=strftime('%s',?)",(org,month)).fetchone()[0]
        if active >= limits['max_parallel']:
            raise ValueError('Organization concurrency limit reached; wait for an active job to finish')
        if used >= limits['jobs_per_month']:
            raise ValueError('Organization monthly job allowance exhausted')
        db.execute('INSERT INTO organization_jobs(id,organization_id,user_id,started) VALUES (?,?,?,?)', (identifier,org,user_id,time.time()))
    outcome = 'failed'
    try:
        yield identifier
        outcome = 'returned'
    finally:
        with database() as db:
            now = time.time()
            db.execute('UPDATE organization_jobs SET finished=?,elapsed_seconds=?-started,outcome=? WHERE id=? AND finished IS NULL', (now,now,outcome,identifier))


def organization_job(function):
    import functools
    @functools.wraps(function)
    def wrapped(*args, **kwargs):
        from .cloud_portal import current_edition
        if current_edition() != 'cloud':
            return function(*args, **kwargs)
        from righaven_core.runtime.user_context import require_current_user
        with admission(str(require_current_user().id)):
            return function(*args, **kwargs)
    return wrapped
