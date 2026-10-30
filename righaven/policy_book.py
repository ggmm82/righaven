"""Organization Policy Book: declarative sheets that govern every project.

A sheet states rules for the specialists, checks they must declare in their
handoff and criteria for the final validation of the finished product. The
runtime enforces them; the coordinator only selects optional sheets.
"""
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
        keys = {'id', 'requirement', 'critical'} | ({'method'} if final else set())
        if (not isinstance(item, dict) or set(item) - keys or not isinstance(item.get('id'), str)
                or not CHECK_ID.fullmatch(item['id']) or item['id'] in seen
                or not isinstance(item.get('requirement'), str) or not item['requirement'].strip()
                or len(item['requirement']) > 600 or type(item.get('critical', True)) is not bool):
            raise ValueError('Policy sheet: ogni controllo richiede id unico, requirement e critical facoltativo')
        if final and item.get('method') not in METHODS:
            raise ValueError('Policy sheet: method del controllo finale tra ' + ', '.join(sorted(METHODS)))
        seen.add(item['id'])
        result.append({k: clean_summary(item[k], 600) if k == 'requirement' else item[k] for k in keys if k in item}
                      | {'critical': item.get('critical', True)})
    return result


def revision(sheet):
    return fingerprint({k: v for k, v in sheet.items() if k not in ('revision', 'source', 'updated_at')})


def book():
    """Every sheet of the organization, built-in sheets first."""
    sheets = [{**s, 'source': 'builtin'} for s in builtin_sheets()]
    builtin = {s['id'] for s in sheets}
    if folder().is_dir() and not folder().is_symlink():
        for path in sorted(folder().glob('*.json'))[:MAX_SHEETS]:
            if path.is_symlink() or path.stat().st_size > 64000:
                continue
            try:
                saved = json.loads(path.read_text())
                sheet = validate_sheet({k: v for k, v in saved.items() if k != 'updated_at'})
            except (OSError, ValueError):
                continue
            if sheet['id'] in builtin or path.stem != sheet['id']:
                continue
            sheets.append({**sheet, 'source': 'organization', 'updated_at': saved.get('updated_at', '')})
    known = {s['id'] for s in sheets}
    sheets = [s for s in sheets if set(s['depends_on']) <= known]
    return [{**s, 'revision': revision(s)} for s in sheets]


def get(identifier):
    sheet = next((s for s in book() if s['id'] == identifier), None)
    if not sheet:
        raise ValueError('Policy sheet sconosciuta: ' + str(identifier)[:60])
    return sheet


def save(sheet):
    """Administrator-owned: add or replace an organization sheet."""
    value = validate_sheet(sheet)
    if value['id'] in {s['id'] for s in builtin_sheets()}:
        raise ValueError('Le sheet incluse in RigHaven non si sostituiscono: crea una sheet con un altro id')
    others = {s['id']: s for s in book() if s['id'] != value['id']}
    if len(others) >= MAX_SHEETS:
        raise ValueError(f'Il Policy Book contiene al massimo {MAX_SHEETS} sheet')
    missing = set(value['depends_on']) - set(others)
    if missing:
        raise ValueError('Dipendenze sconosciute: ' + ', '.join(sorted(missing)))
    graph = {**{k: s['depends_on'] for k, s in others.items()}, value['id']: value['depends_on']}
    _acyclic(graph)
    if folder().is_symlink():
        raise ValueError('Directory del Policy Book non valida')
    state.atomic_json(folder() / (value['id'] + '.json'), {**value, 'updated_at': utcnow()})
    return get(value['id'])


def delete(identifier):
    if not isinstance(identifier, str) or not SHEET_ID.fullmatch(identifier):
        raise ValueError('Policy sheet sconosciuta')
    if identifier in {s['id'] for s in builtin_sheets()}:
        raise ValueError('Le sheet incluse in RigHaven non si eliminano')
    dependants = [s['id'] for s in book() if identifier in s['depends_on']]
    if dependants:
        raise ValueError('Altre sheet dipendono da questa: ' + ', '.join(dependants))
    path = folder() / (identifier + '.json')
    if path.is_symlink() or not path.is_file():
        raise ValueError('Policy sheet sconosciuta')
    path.unlink()


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
                           'critical': c['critical'], 'reference_paths': []} for c in sheet['final_checks']]}
    return {**value, 'hash': fingerprint(value)}


def summary(plan):
    """Compact view for the coordinator, the board and audit events."""
    if not plan:
        return None
    return {'hash': plan['hash'], 'selected_by': plan['selected_by'], 'settled': settled(plan),
            'optional_available': plan.get('optional_available', []),
            'sheets': [{k: s[k] for k in ('id', 'title', 'version', 'mandatory', 'reason', 'steps', 'depends_on')}
                       | {'handoff_checks': [c['id'] for c in s['handoff_checks']],
                          'final_checks': 'acceptance' if s['final_checks'] == 'acceptance' else [c['id'] for c in s['final_checks']]}
                       for s in plan['sheets']]}


def catalog():
    """What the coordinator may choose from, without full rule text."""
    return [{k: s[k] for k in ('id', 'title', 'summary', 'mandatory', 'depends_on', 'applies_to')} for s in book()]
