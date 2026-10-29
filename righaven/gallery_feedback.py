"""Versioned community reviews and discussion, isolated from favorites and project data."""
import contextlib
import sqlite3
import os
import time
import uuid
from . import state, gallery


@contextlib.contextmanager
def database():
    state.STATE.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(state.STATE / 'gallery-feedback.sqlite3', timeout=15)
    os.chmod(state.STATE / "gallery-feedback.sqlite3", 0o600)
    connection.row_factory = sqlite3.Row
    try:
        # Keep SQLite's default journal: concurrent first-use connections must not
        # race to change journal mode before their busy timeout can serialize writes.
        connection.executescript('''
        CREATE TABLE IF NOT EXISTS handles (owner TEXT PRIMARY KEY, handle TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS feedback (
          id TEXT PRIMARY KEY, pack TEXT NOT NULL, version TEXT NOT NULL, owner TEXT NOT NULL,
          parent TEXT, score INTEGER, body TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
          hidden INTEGER NOT NULL DEFAULT 0, moderation TEXT NOT NULL DEFAULT '');
        CREATE UNIQUE INDEX IF NOT EXISTS rating_per_version ON feedback(pack,version,owner) WHERE score IS NOT NULL;
        CREATE INDEX IF NOT EXISTS discussion ON feedback(pack,version,created);
        CREATE TABLE IF NOT EXISTS reports (
          feedback TEXT NOT NULL, owner TEXT NOT NULL, reason TEXT NOT NULL, created REAL NOT NULL,
          PRIMARY KEY(feedback,owner));
        ''')
        with connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
    finally:
        connection.close()


def version_exists(pack, version):
    current = gallery.get_pack(pack)
    if current['version'] == version:
        return current
    import re
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.+-]{0,63}', version):
        raise ValueError('Invalid version')
    path = state.STATE / 'gallery-versions' / pack / (version + '.json')
    if not path.is_file():
        raise ValueError('This pack version is not published')
    import json
    return json.loads(path.read_text())


def _public(db, row, viewer, publisher):
    handle = db.execute('SELECT handle FROM handles WHERE owner=?', (row['owner'],)).fetchone()
    parent = db.execute('SELECT body,hidden FROM feedback WHERE id=?', (row['parent'],)).fetchone() if row['parent'] else None
    return {key: row[key] for key in ('id', 'version', 'parent', 'score', 'body', 'created', 'updated')} | {
        'display_name': handle['handle'] if handle else 'Community member',
        'mine': row['owner'] == viewer, 'author_reply': row['owner'] == publisher,
        'self_reported': True, 'parent_excerpt': parent['body'][:240] if parent and not parent['hidden'] else None}


def list_feedback(pack, viewer, version=None, offset=0, limit=20):
    current = gallery.get_pack(pack)
    if version:
        version_exists(pack, version)
    where, args = 'pack=? AND hidden=0', [pack]
    if version:
        where += ' AND version=?'; args.append(version)
    with database() as db:
        total = db.execute('SELECT COUNT(*) FROM feedback WHERE ' + where, args).fetchone()[0]
        rows = db.execute('SELECT * FROM feedback WHERE ' + where + ' ORDER BY created DESC,id LIMIT ? OFFSET ?', (*args, limit, offset)).fetchall()
        ratings = db.execute('SELECT version,COUNT(*) AS count,AVG(score) AS average FROM feedback WHERE pack=? AND hidden=0 AND score IS NOT NULL GROUP BY version', (pack,)).fetchall()
        return {'items': [_public(db, row, viewer, current['author']) for row in rows],
                'total': total, 'offset': offset, 'limit': limit, 'current_version': current['version'],
                'ratings': [dict(row) for row in ratings]}


def write(pack, version, owner, body, score=None, parent=None):
    published = version_exists(pack, version)
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= 4000:
        raise ValueError('Write a comment of 1–4000 characters')
    if score is not None and (type(score) is not int or not 1 <= score <= 5):
        raise ValueError('Rating must be between 1 and 5')
    if score is not None and (parent or owner == published['author']):
        raise ValueError('Replies and publishers cannot rate their own pack')
    with database() as db:
        if parent:
            target = db.execute('SELECT * FROM feedback WHERE id=? AND pack=? AND version=? AND hidden=0', (parent, pack, version)).fetchone()
            if not target or target['parent']:
                raise ValueError('Reply to a visible review or top-level comment of this version')
        now = time.time()
        db.execute('INSERT OR IGNORE INTO handles VALUES (?,?)', (owner, 'Member ' + uuid.uuid4().hex[:8]))
        previous = db.execute('SELECT * FROM feedback WHERE pack=? AND version=? AND owner=? AND score IS NOT NULL', (pack, version, owner)).fetchone() if score else None
        if previous:
            if previous['hidden']:
                raise ValueError('This review is moderated; contact the administrator')
            key = previous['id']
            db.execute('UPDATE feedback SET score=?,body=?,updated=? WHERE id=?', (score, body.strip(), now, key))
        else:
            key = uuid.uuid4().hex
            db.execute('INSERT INTO feedback(id,pack,version,owner,parent,score,body,created,updated) VALUES(?,?,?,?,?,?,?,?,?)', (key, pack, version, owner, parent, score, body.strip(), now, now))
        return _public(db, db.execute('SELECT * FROM feedback WHERE id=?', (key,)).fetchone(), owner, published['author'])


def remove(key, owner):
    with database() as db:
        # Preserve discussion links, but remove content and rating from public results.
        db.execute("UPDATE feedback SET hidden=1,body='',score=NULL,moderation='Deleted by owner' WHERE id=? AND owner=?", (key, owner))


def report(key, owner, reason):
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
        raise ValueError('Give a reason of 3–1000 characters')
    with database() as db:
        if not db.execute('SELECT id FROM feedback WHERE id=? AND hidden=0', (key,)).fetchone():
            raise ValueError('Feedback not found')
        db.execute('INSERT OR REPLACE INTO reports VALUES(?,?,?,?)', (key, owner, reason.strip(), time.time()))


def reports():
    with database() as db:
        return [dict(row) for row in db.execute('SELECT f.id,f.pack,f.version,f.body,COUNT(r.owner) AS reports,GROUP_CONCAT(r.reason, char(10)) AS reasons FROM feedback f JOIN reports r ON r.feedback=f.id WHERE f.hidden=0 GROUP BY f.id ORDER BY reports DESC')]


def moderate(key, reason):
    if not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
        raise ValueError('Give a moderation reason')
    with database() as db:
        db.execute('UPDATE feedback SET hidden=1,moderation=? WHERE id=?', (reason.strip(), key))


def rating_summaries():
    if not (state.STATE / 'gallery-feedback.sqlite3').exists():
        return {}
    with database() as db:
        return {(row['pack'], row['version']): {'rating_count': row['count'], 'rating_average': row['average']}
                for row in db.execute('SELECT pack,version,COUNT(*) AS count,AVG(score) AS average FROM feedback WHERE hidden=0 AND score IS NOT NULL GROUP BY pack,version')}
