"""Organization Policy Book: declarative sheets that govern every project.

A sheet states rules for the specialists, checks they must declare in their
handoff and criteria for the final validation of the finished product. The
runtime enforces them; the coordinator only selects optional sheets.
"""
from contextlib import contextmanager
import fcntl
import json
import re

from . import state
from .acceptance import METHODS, fingerprint
from .progress import clean_summary, utcnow

SHEET_ID = re.compile(r'[a-z][a-z0-9_]{0,39}\Z')
CHECK_ID = re.compile(r'[a-z][a-z0-9_]{0,59}\Z')
PURPOSES = ('work', 'preview', 'integration', 'delivery')
DEFAULT_SHEET = 'quality_standard'
MAX_SHEETS = 32


def builtin_sheets():
    value = json.loads((state.ROOT / 'policy-book.json').read_text())
    return [validate_sheet(sheet) for sheet in value['sheets']]


def folder():
    return state.STATE / 'policy-book'


def validate_sheet(sheet):
    """Normalize one sheet; unknown fields are rejected, not silently kept."""
    allowed = {'id', 'title', 'version', 'summary', 'mandatory', 'rules', 'handoff_checks', 'final_checks', 'depends_on', 'applies_to'}
    if not isinstance(sheet, dict) or set(sheet) - allowed:
        raise ValueError('Policy sheet: campi ammessi ' + ', '.join(sorted(allowed)))
    if not isinstance(sheet.get('id'), str) or not SHEET_ID.fullmatch(sheet['id']):
        raise ValueError('Policy sheet: id minuscolo con lettere, cifre e underscore')
    if not isinstance(sheet.get('title'), str) or not sheet['title'].strip() or len(sheet['title']) > 140:
        raise ValueError('Policy sheet: titolo entro 140 caratteri')
    if type(sheet.get('version', 1)) is not int or sheet.get('version', 1) < 1:
        raise ValueError('Policy sheet: version intera positiva')
    if not isinstance(sheet.get('summary', ''), str) or len(sheet.get('summary', '')) > 600:
        raise ValueError('Policy sheet: summary entro 600 caratteri')
    if type(sheet.get('mandatory', False)) is not bool:
        raise ValueError('Policy sheet: mandatory booleano')
    rules = sheet.get('rules', [])
    if (not isinstance(rules, list) or len(rules) > 12
            or any(not isinstance(r, str) or not r.strip() or len(r) > 500 for r in rules)):
        raise ValueError('Policy sheet: al massimo 12 regole testuali entro 500 caratteri')
    handoff = _checks(sheet.get('handoff_checks', []), 8, final=False)
    final = sheet.get('final_checks', [])
    if final != 'acceptance':
        final = _checks(final, 20, final=True)
    if not rules and not handoff and not final:
        raise ValueError('Policy sheet: indica almeno una regola o un controllo')
    depends = sheet.get('depends_on', [])
    if (not isinstance(depends, list) or len(depends) > 8 or sheet['id'] in depends
            or any(not isinstance(d, str) or not SHEET_ID.fullmatch(d) for d in depends)):
        raise ValueError('Policy sheet: depends_on elenca altre sheet esistenti')
    purposes = sheet.get('applies_to', list(PURPOSES))
    if not isinstance(purposes, list) or not purposes or any(p not in PURPOSES for p in purposes):
        raise ValueError('Policy sheet: applies_to tra ' + ', '.join(PURPOSES))
    return {'id': sheet['id'], 'title': clean_summary(sheet['title'], 140), 'version': sheet.get('version', 1),
            'summary': clean_summary(sheet.get('summary', ''), 600), 'mandatory': sheet.get('mandatory', False),
            'rules': [clean_summary(r, 500) for r in rules], 'handoff_checks': handoff, 'final_checks': final,
            'depends_on': list(dict.fromkeys(depends)), 'applies_to': list(dict.fromkeys(purposes))}


def _checks(items, limit, *, final):
    if not isinstance(items, list) or len(items) > limit:
        raise ValueError(f'Policy sheet: al massimo {limit} controlli')
    result, seen = [], set()
    for item in items:
        keys = {'id', 'requirement', 'critical'} | ({'method', 'probe'} if final else set())
        if (not isinstance(item, dict) or set(item) - keys or not isinstance(item.get('id'), str)
                or not CHECK_ID.fullmatch(item['id']) or item['id'] in seen
                or not isinstance(item.get('requirement'), str) or not item['requirement'].strip()
                or len(item['requirement']) > 600 or type(item.get('critical', True)) is not bool):
            raise ValueError('Policy sheet: ogni controllo richiede id unico, requirement e critical facoltativo')
        if final and item.get('method') not in METHODS:
            raise ValueError('Policy sheet: method del controllo finale tra ' + ', '.join(sorted(METHODS)))
        if final and 'probe' in item:
            from .policy_probes import PROBES
            if item['probe'] not in PROBES:
                raise ValueError('Policy sheet: probe tra ' + ', '.join(sorted(PROBES)))
        seen.add(item['id'])
        result.append({k: clean_summary(item[k], 600) if k == 'requirement' else item[k] for k in keys if k in item}
                      | {'critical': item.get('critical', True)})
    return result


def revision(sheet):
    return fingerprint({k: v for k, v in sheet.items() if k not in ('revision', 'source', 'updated_at', 'published_at')})


STATUSES = ('draft', 'active', 'retired')
MAX_VERSIONS = 100
MAX_HISTORY = 200


def _record_path(identifier):
    if not isinstance(identifier, str) or not SHEET_ID.fullmatch(identifier):
        raise ValueError('Policy sheet sconosciuta')
    if folder().is_symlink():
        raise ValueError('Directory del Policy Book non valida')
    return folder() / (identifier + '.json')


def _read(identifier):
    """Organization record: draft, immutable published versions, status and history."""
    path = _record_path(identifier)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        return None
    value = json.loads(path.read_text())
    if 'versions' not in value:
        # Sheets saved before the lifecycle become their first published version.
        sheet = validate_sheet({k: v for k, v in value.items() if k != 'updated_at'})
        at = value.get('updated_at', '')
        value = {'id': sheet['id'], 'status': 'active', 'active_version': 1, 'draft': None,
                 'versions': [{'version': 1, 'sheet': {**sheet, 'version': 1}, 'revision': revision({**sheet, 'version': 1}),
                               'published_at': at, 'published_by': 'migrazione'}],
                 'history': [{'at': at, 'actor': 'migrazione', 'action': 'published', 'version': 1}], 'created_at': at}
    if value.get('id') != identifier or value.get('status') not in STATUSES:
        raise ValueError('Record della policy sheet non valido')
    return value


def _write(value):
    value['history'] = value['history'][-MAX_HISTORY:]
    value['updated_at'] = utcnow()
    state.atomic_json(_record_path(value['id']), value)


@contextmanager
def _locked():
    folder().mkdir(parents=True, exist_ok=True)
    with open(folder() / '.lock', 'a') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _records():
    if not folder().is_dir() or folder().is_symlink():
        return []
    result = []
    for path in sorted(folder().glob('*.json')):
        try:
            record = _read(path.stem) if SHEET_ID.fullmatch(path.stem) else None
        except (OSError, ValueError):
            continue
        if record:
            result.append(record)
    return result


def _active(record):
    entry = next(v for v in record['versions'] if v['version'] == record['active_version'])
    return {**entry['sheet'], 'source': 'organization', 'published_at': entry['published_at']}


def book():
    """Sheets usable by new projects: built-in sheets and active organization sheets."""
    sheets = [{**s, 'source': 'builtin'} for s in builtin_sheets()]
    builtin = {s['id'] for s in sheets}
    sheets += [_active(r) for r in _records() if r['status'] == 'active' and r['id'] not in builtin][:MAX_SHEETS]
    known = {s['id'] for s in sheets}
    sheets = [s for s in sheets if set(s['depends_on']) <= known]
    return [{**s, 'revision': revision(s)} for s in sheets]


def get(identifier):
    sheet = next((s for s in book() if s['id'] == identifier), None)
    if not sheet:
        raise ValueError('Policy sheet sconosciuta o non attiva: ' + str(identifier)[:60])
    return sheet


def overview():
    """Management view: every sheet, whatever its state."""
    rows = [{'id': s['id'], 'title': s['title'], 'summary': s['summary'], 'source': 'builtin', 'status': 'active',
             'mandatory': s['mandatory'], 'active_version': s['version'], 'has_draft': False, 'depends_on': s['depends_on']}
            for s in builtin_sheets()]
    for record in _records():
        current = _active(record) if record['active_version'] else (record['draft'] or {})
        rows.append({'id': record['id'], 'title': current.get('title', record['id']), 'summary': current.get('summary', ''),
                     'source': 'organization', 'status': record['status'], 'mandatory': bool(current.get('mandatory')),
                     'active_version': record['active_version'], 'has_draft': record['draft'] is not None,
                     'depends_on': current.get('depends_on', []), 'updated_at': record.get('updated_at', '')})
    return rows


def detail(identifier):
    builtin = next((s for s in builtin_sheets() if s['id'] == identifier), None)
    if builtin:
        sheet = {**builtin, 'revision': revision(builtin)}
        return {'id': identifier, 'source': 'builtin', 'status': 'active', 'active_version': builtin['version'],
                'draft': None, 'versions': [{'version': builtin['version'], 'sheet': sheet, 'revision': sheet['revision'],
                                             'published_at': '', 'published_by': 'RigHaven'}], 'history': []}
    record = _read(identifier)
    if not record:
        raise ValueError('Policy sheet sconosciuta')
    return {**record, 'source': 'organization'}


def _draft_content(identifier, content):
    if not isinstance(content, dict):
        raise ValueError('Policy sheet: contenuto JSON non valido')
    value = validate_sheet({**{k: v for k, v in content.items() if k not in ('version', 'revision', 'source')}, 'id': identifier})
    value.pop('version')
    return value


def save_draft(identifier, content, actor):
    """Create a sheet or prepare its next version; the active version keeps applying."""
    if identifier in {s['id'] for s in builtin_sheets()}:
        raise ValueError('Le sheet incluse in RigHaven non si modificano: crea una sheet con un altro id')
    draft = _draft_content(identifier, content)
    with _locked():
        record = _read(identifier)
        if record is None:
            if len(_records()) >= MAX_SHEETS:
                raise ValueError(f'Il Policy Book contiene al massimo {MAX_SHEETS} sheet')
            record = {'id': identifier, 'status': 'draft', 'active_version': None, 'versions': [], 'history': [],
                      'created_at': utcnow()}
        record['draft'] = {**draft, 'saved_at': utcnow(), 'saved_by': actor}
        record['history'].append({'at': utcnow(), 'actor': actor, 'action': 'draft_saved'})
        _write(record)
    return detail(identifier)


def discard_draft(identifier, actor):
    """Drop the pending draft; a sheet that was never published disappears entirely."""
    with _locked():
        record = _read(identifier)
        if not record or record['draft'] is None:
            raise ValueError('Nessuna bozza da scartare')
        if not record['versions']:
            _record_path(identifier).unlink()
            return None
        record['draft'] = None
        record['history'].append({'at': utcnow(), 'actor': actor, 'action': 'draft_discarded'})
        _write(record)
    return detail(identifier)


def publish(identifier, actor):
    """Freeze the draft as the next immutable version and make it active for new plans."""
    with _locked():
        record = _read(identifier)
        if not record or record['draft'] is None:
            raise ValueError('Nessuna bozza da pubblicare')
        if len(record['versions']) >= MAX_VERSIONS:
            raise ValueError(f'Raggiunte {MAX_VERSIONS} versioni: crea una nuova sheet')
        number = max((v['version'] for v in record['versions']), default=0) + 1
        sheet = validate_sheet({**{k: v for k, v in record['draft'].items() if k not in ('saved_at', 'saved_by')}, 'version': number})
        _check_graph(identifier, sheet['depends_on'])
        record['versions'].append({'version': number, 'sheet': sheet, 'revision': revision(sheet),
                                   'published_at': utcnow(), 'published_by': actor})
        record.update(status='active', active_version=number, draft=None)
        record['history'].append({'at': utcnow(), 'actor': actor, 'action': 'published', 'version': number})
        _write(record)
    return detail(identifier)


def retire(identifier, actor):
    """Stop offering a sheet to new plans; projects keep the version they pinned."""
    with _locked():
        record = _read(identifier)
        if not record or record['status'] != 'active':
            raise ValueError('Si ritira soltanto una sheet attiva dell’organizzazione')
        dependants = [s['id'] for s in book() if identifier in s['depends_on']]
        if dependants:
            raise ValueError('Altre sheet attive dipendono da questa: ' + ', '.join(dependants))
        record['status'] = 'retired'
        record['history'].append({'at': utcnow(), 'actor': actor, 'action': 'retired', 'version': record['active_version']})
        _write(record)
    return detail(identifier)


def reactivate(identifier, actor):
    with _locked():
        record = _read(identifier)
        if not record or record['status'] != 'retired':
            raise ValueError('Si riattiva soltanto una sheet ritirata')
        _check_graph(identifier, _active(record)['depends_on'])
        record['status'] = 'active'
        record['history'].append({'at': utcnow(), 'actor': actor, 'action': 'reactivated', 'version': record['active_version']})
        _write(record)
    return detail(identifier)


def restore(identifier, version, actor):
    """Copy a published version into the draft; publishing it creates a new version."""
    with _locked():
        record = _read(identifier)
        entry = next((v for v in (record or {}).get('versions', []) if v['version'] == version), None)
        if not entry:
            raise ValueError('Versione sconosciuta')
        content = {k: v for k, v in entry['sheet'].items() if k != 'version'}
        record['draft'] = {**content, 'saved_at': utcnow(), 'saved_by': actor}
        record['history'].append({'at': utcnow(), 'actor': actor, 'action': 'restored_to_draft', 'version': version})
        _write(record)
    return detail(identifier)


def _check_graph(identifier, depends_on):
    active = {s['id']: s for s in book() if s['id'] != identifier}
    missing = set(depends_on) - set(active)
    if missing:
        raise ValueError('Dipendenze sconosciute o non attive: ' + ', '.join(sorted(missing)))
    _acyclic({**{k: s['depends_on'] for k, s in active.items()}, identifier: depends_on})


def _acyclic(graph):
    visiting, done = set(), set()

    def visit(node):
        if node in done:
            return
        if node in visiting:
            raise ValueError('Le dipendenze tra policy sheet formano un ciclo')
        visiting.add(node)
        for child in graph.get(node, []):
            visit(child)
        visiting.discard(node)
        done.add(node)
    for node in graph:
        visit(node)


def build_plan(selections, steps, *, selected_by='coordinator'):
    """Pin the applicable sheets for one project; mandatory sheets are not optional.

    selections: optional sheets chosen by the coordinator, each with id, reason
    and optional steps (activity IDs; empty means all production activities).
    """
    if not isinstance(selections, list) or len(selections) > MAX_SHEETS:
        raise ValueError('policies_json: elenco di sheet con id e reason')
    sheets = {s['id']: s for s in book()}
    step_ids = {s['id'] for s in steps}
    chosen = {}
    for item in selections:
        if (not isinstance(item, dict) or set(item) - {'id', 'reason', 'steps'} or item.get('id') not in sheets
                or not isinstance(item.get('reason'), str) or not item['reason'].strip()):
            raise ValueError('policies_json: ogni sheet richiede id del Policy Book e reason che ne motivi l’applicazione al progetto')
        scope = item.get('steps', [])
        if not isinstance(scope, list) or any(s not in step_ids for s in scope):
            raise ValueError('policies_json: steps deve elencare attività esistenti dell’Execution Plan')
        if item['id'] in chosen:
            raise ValueError('policies_json: sheet ripetuta')
        chosen[item['id']] = {'reason': clean_summary(item['reason'], 400), 'steps': scope}
    for sheet in sheets.values():
        if sheet['mandatory'] and sheet['id'] not in chosen:
            chosen[sheet['id']] = {'reason': 'Obbligatoria nel Policy Book', 'steps': []}
    for identifier in list(chosen):
        missing = [d for d in sheets[identifier]['depends_on'] if d not in chosen]
        if missing:
            raise ValueError('La sheet ' + identifier + ' richiede anche: ' + ', '.join(missing))
    entries = [{**{k: sheets[i][k] for k in ('id', 'title', 'version', 'revision', 'mandatory', 'rules',
                                              'handoff_checks', 'final_checks', 'depends_on', 'applies_to')},
                **chosen[i]} for i in sorted(chosen, key=lambda i: (not sheets[i]['mandatory'], i))]
    plan = {'sheets': entries, 'selected_by': selected_by,
            'optional_available': sorted(i for i, s in sheets.items() if not s['mandatory']),
            'created_at': utcnow()}
    plan['hash'] = fingerprint({'sheets': entries})
    return plan


def missing_mandatory(plan):
    """Sheets made mandatory after this plan was pinned."""
    present = {s['id'] for s in plan['sheets']}
    return [s['id'] for s in book() if s['mandatory'] and s['id'] not in present]


def settled(plan):
    """A Policy Plan is settled once someone decided on the optional sheets."""
    return bool(plan) and (plan.get('selected_by') == 'coordinator' or not plan.get('optional_available'))


def contract(sheet, acceptance):
    """Final-validation contract for one sheet, in the acceptance shape the review engine evaluates."""
    if sheet['final_checks'] == 'acceptance':
        return acceptance
    value = {'policy_sheet': sheet['id'], 'policy_revision': sheet['revision'],
             'criteria': [{'id': c['id'], 'requirement': c['requirement'], 'method': c['method'],
                           'critical': c['critical'], 'reference_paths': []} for c in sheet['final_checks'] if not c.get('probe')]}
    return {**value, 'hash': fingerprint(value)}


def summary(plan):
    """Compact view for the coordinator, the board and audit events."""
    if not plan:
        return None
    return {'hash': plan['hash'], 'selected_by': plan['selected_by'], 'settled': settled(plan),
            'optional_available': plan.get('optional_available', []),
            'sheets': [{k: s[k] for k in ('id', 'title', 'version', 'mandatory', 'reason', 'steps', 'depends_on')}
                       | {'handoff_checks': [c['id'] for c in s['handoff_checks']],
                          'final_checks': 'acceptance' if s['final_checks'] == 'acceptance' else [c['id'] for c in s['final_checks']],
                          'probes': [c['probe'] for c in s['final_checks'] if c.get('probe')] if s['final_checks'] != 'acceptance' else []}
                       for s in plan['sheets']]}


def catalog():
    """What the coordinator may choose from, without full rule text."""
    return [{k: s[k] for k in ('id', 'title', 'summary', 'mandatory', 'depends_on', 'applies_to')} for s in book()]
