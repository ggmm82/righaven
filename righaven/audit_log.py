"""Conversation-owned operational journal; no prompts, outputs or private reasoning."""
from contextlib import contextmanager, closing
from datetime import datetime, timezone
import logging
import json
from pathlib import Path
import sqlite3
import uuid

logger = logging.getLogger(__name__)


@contextmanager
def database(workspace, create=True):
    root=Path(workspace).resolve(); folder=root/'.righaven-project/audit'; path=folder/'events.sqlite3'
    if folder.is_symlink() or path.is_symlink() or not path.resolve().is_relative_to(root):
        raise ValueError('Registro fuori dalla conversazione')
    if not create and not path.exists():
        yield None;return
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    with closing(sqlite3.connect(path,timeout=5)) as conn, conn:
        conn.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, id TEXT UNIQUE, at TEXT, actor TEXT, operation TEXT, status TEXT, detail TEXT, correlation TEXT)')
        columns = {r[1] for r in conn.execute('PRAGMA table_info(events)')}
        if 'context' not in columns:
            try:
                conn.execute("ALTER TABLE events ADD COLUMN context TEXT DEFAULT '{}'")
            except sqlite3.OperationalError:
                if 'context' not in {r[1] for r in conn.execute('PRAGMA table_info(events)')}:
                    raise
        path.chmod(0o600)
        yield conn


def append(workspace, actor, operation, status, detail='', correlation='', identifier=None, at=None, context=None):
    try:
        try:
            from .progress import clean_summary
        except ImportError:
            from progress import clean_summary
        fields=[clean_summary(v,n) for v,n in [(actor,140),(operation,160),(status,40),(detail,500),(correlation,160)]]
        try:
            from .command_details import public
        except ImportError:
            from command_details import public
        fields.append(json.dumps(public(context)))
        with database(workspace) as conn:
            conn.execute('INSERT OR IGNORE INTO events (id,at,actor,operation,status,detail,correlation,context) VALUES (?,?,?,?,?,?,?,?)',
                         [identifier or uuid.uuid4().hex,at or datetime.now(timezone.utc).isoformat(),*fields])
        return True
    except (OSError,ValueError,sqlite3.Error):
        logger.warning('Registro operativo non aggiornato')
        return False


def page(workspace, after=None, before=None, limit=100):
    if after is not None and before is not None or not 1<=limit<=200:
        raise ValueError('Paginazione registro non valida')
    with database(workspace,False) as conn:
        if conn is None:return {'events':[],'next_before':None,'latest_seq':0}
        conn.row_factory=sqlite3.Row
        where,params=('WHERE seq > ?', [after]) if after is not None else ('WHERE seq < ?', [before]) if before is not None else ('',[])
        order='ASC' if after is not None else 'DESC'
        rows=[dict(r) for r in conn.execute(f'SELECT * FROM events {where} ORDER BY seq {order} LIMIT ?', [*params,limit])]
        for row in rows:
            try: row['context'] = json.loads(row.get('context') or '{}')
            except ValueError: row['context'] = {}
        if order=='DESC':rows.reverse()
        oldest=rows[0]['seq'] if rows else 0
        more=bool(oldest and conn.execute('SELECT 1 FROM events WHERE seq < ? LIMIT 1',[oldest]).fetchone())
        return {'events':rows,'next_before':oldest if more else None,
                'latest_seq':conn.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]}


def export_rows(workspace):
    import csv,io
    stream=io.StringIO();writer=csv.writer(stream)
    writer.writerow(['timestamp_utc','attore','operazione','esito','dettaglio','correlazione','strumento','azione','durata_secondi','codice_uscita','diagnostica','file','comando_estratto','comando_sha256'])
    yield '\ufeff'+stream.getvalue();cursor=0
    while True:
        rows=page(workspace,after=cursor,limit=200)['events']
        if not rows:return
        for row in rows:
            stream.seek(0);stream.truncate(0)
            # Spreadsheet exports must not turn model error text into formulas.
            context=row.get('context') or {}
            values=[row[k] for k in ('at','actor','operation','status','detail','correlation')]
            values += [context.get(k,'') for k in ('tool','action','duration_seconds','exit_code','diagnostic')]
            values.append(' | '.join(context.get('files',[])))
            values += [context.get('command_preview',''), context.get('command_sha256','')]
            values=[str(v) if v is not None else '' for v in values]
            writer.writerow(["'"+v if v.lstrip().startswith(('=','+','-','@')) else v for v in values])
            yield stream.getvalue();cursor=row['seq']
