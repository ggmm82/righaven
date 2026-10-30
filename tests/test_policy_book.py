"""Policy Book model and the runtime-enforced project lifecycle."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import policy_book, policy_workflow, projects, state


def security(**changes):
    return {'id': 'security', 'title': 'Sicurezza', 'summary': 'Nessun segreto nei prodotti',
            'rules': ['Non inserire credenziali o token nei file consegnati.'],
            'handoff_checks': [{'id': 'no_secrets', 'requirement': 'Nessuna credenziale nei file prodotti'}],
            'final_checks': [{'id': 'secret_scan', 'requirement': 'Il prodotto non contiene credenziali', 'method': 'technical'}],
            **changes}


def publish(sheet):
    policy_book.save_draft(sheet['id'], sheet, 'admin@example.test')
    policy_book.publish(sheet['id'], 'admin@example.test')
    return policy_book.get(sheet['id'])


class PolicyBookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        fixture = patch.object(state, 'STATE', Path(temp.name)); fixture.start(); self.addCleanup(fixture.stop)

    def test_default_sheet_is_mandatory_and_reuses_the_acceptance_review(self):
        sheet = policy_book.get(policy_book.DEFAULT_SHEET)
        self.assertTrue(sheet['mandatory'])
        self.assertEqual(sheet['final_checks'], 'acceptance')
        plan = policy_book.build_plan([], [], selected_by='system')
        self.assertEqual([s['id'] for s in plan['sheets']], ['quality_standard'])
        self.assertTrue(policy_book.settled(plan))
        acceptance = {'criteria': [], 'hash': 'h'}
        self.assertIs(policy_book.contract(plan['sheets'][0], acceptance), acceptance)

    def test_organization_sheets_extend_the_book_but_cannot_replace_builtins(self):
        saved = publish(security())
        self.assertEqual((saved['source'], saved['version']), ('organization', 1))
        with self.assertRaisesRegex(ValueError, 'non si modificano'):
            policy_book.save_draft('quality_standard', security(), 'admin')
        with self.assertRaisesRegex(ValueError, 'campi ammessi'):
            policy_book.save_draft('security', security(owner='someone'), 'admin')
        with self.assertRaisesRegex(ValueError, 'method'):
            policy_book.save_draft('security', security(final_checks=[{'id': 'x', 'requirement': 'y', 'method': 'taste'}]), 'admin')
        with self.assertRaisesRegex(ValueError, 'organizzazione'):
            policy_book.retire('quality_standard', 'admin')

    def test_lifecycle_keeps_the_active_version_until_a_draft_is_published(self):
        policy_book.save_draft('security', security(), 'anna')
        self.assertEqual(policy_book.overview()[-1]['status'], 'draft')
        with self.assertRaisesRegex(ValueError, 'non attiva'):
            policy_book.get('security')  # drafts are not offered to projects
        policy_book.publish('security', 'anna')
        policy_book.save_draft('security', security(rules=['Regola rivista']), 'bruno')
        self.assertEqual(policy_book.get('security')['rules'], security()['rules'])
        record = policy_book.publish('security', 'bruno')
        self.assertEqual((record['active_version'], policy_book.get('security')['version']), (2, 2))
        self.assertEqual([v['sheet']['rules'] for v in record['versions']], [security()['rules'], ['Regola rivista']])
        policy_book.retire('security', 'carla')
        self.assertNotIn('security', [s['id'] for s in policy_book.book()])
        policy_book.reactivate('security', 'carla')
        record = policy_book.restore('security', 1, 'dario')
        self.assertEqual(record['draft']['rules'], security()['rules'])
        self.assertEqual(policy_book.publish('security', 'dario')['active_version'], 3)
        history = [(h['actor'], h['action'], h.get('version')) for h in policy_book.detail('security')['history']]
        self.assertEqual(history, [('anna', 'draft_saved', None), ('anna', 'published', 1), ('bruno', 'draft_saved', None),
                                   ('bruno', 'published', 2), ('carla', 'retired', 2), ('carla', 'reactivated', 2),
                                   ('dario', 'restored_to_draft', 1), ('dario', 'published', 3)])
        # A never-published sheet can be discarded entirely; a published one keeps its history.
        policy_book.save_draft('scratch', security(id='scratch'), 'anna')
        self.assertIsNone(policy_book.discard_draft('scratch', 'anna'))
        self.assertNotIn('scratch', [s['id'] for s in policy_book.overview()])

    def test_sheets_saved_before_the_lifecycle_become_version_one(self):
        state.atomic_json(policy_book.folder() / 'security.json', {**security(), 'updated_at': '2026-10-30T10:00:00+00:00'})
        self.assertEqual(policy_book.get('security')['version'], 1)
        self.assertEqual(policy_book.detail('security')['history'][0]['action'], 'published')

    def test_dependencies_must_exist_and_cannot_form_a_cycle(self):
        publish(security())
        policy_book.save_draft('release', security(id='release', depends_on=['missing']), 'admin')
        with self.assertRaisesRegex(ValueError, 'sconosciute'):
            policy_book.publish('release', 'admin')
        publish(security(id='release', depends_on=['security']))
        policy_book.save_draft('security', security(depends_on=['release']), 'admin')
        with self.assertRaisesRegex(ValueError, 'ciclo'):
            policy_book.publish('security', 'admin')
        with self.assertRaisesRegex(ValueError, 'dipendono'):
            policy_book.retire('security', 'admin')

    def test_optional_sheets_require_a_coordinator_decision_with_reasons(self):
        publish(security())
        system = policy_book.build_plan([], [{'id': 'draft'}], selected_by='system')
        self.assertFalse(policy_book.settled(system))
        self.assertEqual(system['optional_available'], ['security'])
        with self.assertRaisesRegex(ValueError, 'reason'):
            policy_book.build_plan([{'id': 'security'}], [{'id': 'draft'}])
        with self.assertRaisesRegex(ValueError, 'attività esistenti'):
            policy_book.build_plan([{'id': 'security', 'reason': 'Codice pubblico', 'steps': ['other']}], [{'id': 'draft'}])
        plan = policy_book.build_plan([{'id': 'security', 'reason': 'Codice pubblico', 'steps': ['draft']}], [{'id': 'draft'}])
        self.assertTrue(policy_book.settled(plan))
        self.assertEqual([s['id'] for s in plan['sheets']], ['quality_standard', 'security'])
        criteria = policy_book.contract(plan['sheets'][1], None)['criteria']
        self.assertEqual(criteria[0]['id'], 'secret_scan')
        # A sheet changed after planning gets a new revision; the pinned plan keeps its copy.
        publish(security(rules=['Regola aggiornata']))
        self.assertNotEqual(policy_book.get('security')['revision'], plan['sheets'][1]['revision'])

    def test_independent_sheets_share_a_wave_and_dependants_wait(self):
        sheets = [{'id': 'a', 'depends_on': []}, {'id': 'b', 'depends_on': []}, {'id': 'c', 'depends_on': ['a']}]
        self.assertEqual([[s['id'] for s in wave] for wave in policy_workflow.waves(sheets)], [['a', 'b'], ['c']])


class PolicyWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'conversation'; self.root.mkdir()
        fixture = patch.object(state, 'STATE', Path(temp.name) / 'state'); fixture.start(); self.addCleanup(fixture.stop)

    def plan(self):
        return projects.create_plan(self.root, 'Documento tecnico', [{'id': 'draft', 'agent': 'workspace', 'goal': 'Bozza'}],
                                    outcome={'result': 'Documento', 'format': 'Markdown modificabile'})

    def execute(self, checks, purpose='work'):
        folder = self.root / 'outputs' / 'job'; folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'draft.md'; path.write_text('bozza')
        tasks = []

        def invoke(task, started):
            tasks.append(task)
            return json.dumps({'ok': True, 'output_dir': str(folder), 'handoff': {
                'source_files': [], 'output_files': [str(path)], 'previews': [], 'checks': checks}})
        return json.loads(projects.execute_step(self.root, 'workspace', 'Scrivi la bozza', 'draft', invoke, purpose=purpose)), tasks

    def test_new_projects_are_governed_and_legacy_projects_keep_their_behaviour(self):
        self.plan()
        value = projects.governance_state(self.root)
        self.assertTrue(policy_workflow.governed(value))
        self.assertEqual(projects.read_project(self.root)['governance']['phase'], 'execution')
        value.pop('governance')
        self.assertEqual(policy_workflow.phase(value), 'legacy')

    def test_production_waits_for_the_policy_plan_when_the_book_offers_a_choice(self):
        publish(security())
        self.plan()
        self.assertEqual(projects.read_project(self.root)['governance']['phase'], 'planning')
        with self.assertRaisesRegex(ValueError, 'Policy Plan'):
            self.execute([{'name': 'Bozza', 'status': 'passed', 'evidence': 'letta'}])
        projects.set_policy_plan(self.root, [])
        result, tasks = self.execute([{'name': 'Bozza', 'status': 'passed', 'evidence': 'letta'}])
        self.assertTrue(result['ok'])
        self.assertNotIn('security', tasks[0])

    def test_handoff_must_declare_the_critical_policy_checks(self):
        publish(security())
        self.plan()
        projects.set_policy_plan(self.root, [{'id': 'security', 'reason': 'Documento pubblico'}])
        result, tasks = self.execute([{'name': 'Bozza', 'status': 'passed', 'evidence': 'letta'}])
        self.assertIn('security.no_secrets', tasks[0])
        self.assertIn('Non inserire credenziali', tasks[0])
        self.assertEqual(result['policy_violations'], ['Policy security.no_secrets'])
        self.assertEqual(result['activity']['status'], 'needs_revision')
        result, _ = self.execute([{'name': 'Segreti', 'status': 'passed', 'evidence': 'grep senza risultati',
                               'policy_check': 'security.no_secrets'}])
        self.assertEqual(result['activity']['status'], 'completed')
        self.assertEqual(result['policy_compliance'][0]['status'], 'passed')
        from righaven.audit_log import page
        events = page(self.root)['events']
        self.assertTrue(any(e['operation'] == 'Handoff non conforme al Policy Plan' and e['status'] == 'failed' for e in events))


class PhaseCheckpointTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'conversation'; self.root.mkdir()
        fixture = patch.object(state, 'STATE', Path(temp.name) / 'state'); fixture.start(); self.addCleanup(fixture.stop)
        projects.create_plan(self.root, 'Documento', [{'id': 'draft', 'agent': 'workspace', 'goal': 'Bozza'},
                                                      {'id': 'final', 'agent': 'workspace', 'goal': 'Finale'}],
                             outcome={'result': 'Documento', 'format': 'Markdown'})

    def execute(self, step, turn, ok=True, purpose='work'):
        folder = self.root / 'outputs' / (step + turn); folder.mkdir(parents=True, exist_ok=True)
        (folder / 'out.md').write_text('testo')
        reply = {'ok': ok, 'error': '' if ok else 'Worker interrotto', 'output_dir': str(folder), 'handoff': {'source_files': [], 'output_files': [str(folder / 'out.md')],
                 'previews': [], 'checks': [{'name': 'Letto', 'status': 'passed', 'evidence': 'riaperto'}]}}
        return json.loads(projects.execute_step(self.root, 'workspace', 'Esegui', step, lambda task, started: json.dumps(reply),
                                                purpose=purpose, request_id=turn))

    def test_production_waits_for_the_user_after_each_phase(self):
        self.assertEqual(self.execute('draft', 'turn-1')['checkpoint']['steps'], ['draft'])
        with self.assertRaisesRegex(ValueError, 'ask_clarification'):
            self.execute('final', 'turn-1')
        self.assertTrue(self.execute('draft', 'turn-1', purpose='review')['ok'])  # checks are not production
        live = policy_workflow.live(self.root, projects.governance_state(self.root))
        self.assertEqual(live['checkpoints']['pending']['steps'], ['draft'])
        self.assertEqual(projects.read_project(self.root)['checkpoint']['status'], 'awaiting_user')
        from righaven.completion_policy import needs_continuation
        self.assertFalse(needs_continuation(projects.read_project(self.root)))
        self.assertTrue(self.execute('final', 'turn-2')['ok'])  # the user replied
        live = policy_workflow.live(self.root, projects.governance_state(self.root))
        self.assertEqual((live['checkpoints']['pending']['steps'], live['checkpoints']['discussed']), (['final'], 1))
        from righaven.audit_log import page
        self.assertIn('Fase discussa con l’utente', [e['operation'] for e in page(self.root)['events']])

    def test_failures_do_not_open_a_discussion_and_owners_can_turn_pauses_off(self):
        self.assertNotIn('checkpoint', self.execute('draft', 'turn-1', ok=False))
        self.assertTrue(self.execute('draft', 'turn-1')['ok'])
        projects.set_checkpoints(self.root, False)
        self.assertTrue(self.execute('final', 'turn-1')['ok'])
        self.assertNotIn('checkpoint', self.execute('final', 'turn-1'))
        self.assertEqual(projects.governance_state(self.root)['checkpoint']['status'], 'waived')
        with self.assertRaises(ValueError):
            projects.set_checkpoints(self.root, 'no')


try:
    from righaven.tools import harness_delegate, harness_plan, harness_validate
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    harness_delegate = None


@unittest.skipIf(harness_delegate is None, 'Requires the pinned Gateway tool runtime')
class PolicyLifecycleTests(unittest.TestCase):
    """End to end through the coordinator tools, with simulated workers.

    Reviews go through the real review engine (read_review/evaluate) on real
    files, so verdicts, hashes and contracts are the ones production uses.
    """

    def setUp(self):
        from types import SimpleNamespace
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'conversation'; self.root.mkdir()
        fixtures = [patch.object(state, 'STATE', Path(temp.name) / 'state'),
                    patch('righaven.tools.workspace_for', return_value=self.root),
                    patch('righaven.state.team', return_value={'engine': 'claude', 'model': 'fixture'}),
                    patch('righaven.tools.delegate', side_effect=self.worker)]
        # Native skill storage is covered elsewhere; isolate the tool/project boundary.
        from righaven.capability_policy import policy_from_names
        capabilities = policy_from_names({'skill-' + a['id'] for a in state.applications()}, source='fixture')
        fixtures += [patch('righaven.capability_policy.runtime_policy', return_value=capabilities),
                     patch('righaven.tools.experience_root', return_value=Path(temp.name) / 'library')]
        for fixture in fixtures:
            fixture.start(); self.addCleanup(fixture.stop)
        self.runtime = SimpleNamespace(state={'messages': [SimpleNamespace(type='human', id='request',
            content='Scrivi un documento tecnico pubblicabile sul progetto')]})
        self.calls, self.version, self.secret_free, self.declare = [], 0, False, True
        import threading
        self.lock = threading.Lock()
        # The three first-wave reviews only pass this barrier if they really run together.
        self.barrier = threading.Barrier(3, timeout=20)

    def reply(self, text):
        from types import SimpleNamespace
        messages = self.runtime.state['messages']
        messages.append(SimpleNamespace(type='human', id='reply-' + str(len(messages)), content=text))

    def worker(self, agent, instructions, workspace, **kwargs):
        from righaven.deliveries import read_review
        from righaven.source_packages import digest
        purpose = kwargs['purpose']
        sheet = (kwargs.get('policy_review') or {}).get('sheet')
        with self.lock:
            self.calls.append({'purpose': purpose, 'sheet': sheet, 'instructions': instructions})
            folder = self.root / 'outputs' / 'workspace' / ('rh-job-' + str(len(self.calls)).zfill(12))
        folder.mkdir(parents=True)
        if kwargs.get('on_started'):
            kwargs['on_started'](str(folder))
        delivery = {'source_status': 'included', 'source_note': 'fixture', 'files': []}
        if purpose == 'review':
            standard = 'Validazione finale della policy sheet «Revisione di qualità standard»' in instructions
            if self.version == 1 and (standard or sheet in ('security', 'accessibility')):
                self.barrier.wait()
            contract = (kwargs.get('policy_review') or {}).get('contract') or kwargs['acceptance']
            product = projects.artifact_path(self.root, projects.governance_state(self.root)['product_path'])
            verdict = lambda c: 'failed' if c['id'] == 'secret_scan' and not self.secret_free else 'passed'
            report = folder / 'quality-review.json'
            report.write_text(json.dumps({'product_path': str(product), 'criteria': [
                {'requirement_id': c['id'], 'criterion': c['requirement'], 'method': c['method'],
                 'status': verdict(c), 'evidence': 'Osservato sul file ' + product.name} for c in contract['criteria']]}))
            handoff = {'task': 'review', 'source_files': [str(product)], 'output_files': [str(report)], 'previews': [],
                       'checks': [{'name': 'Revisione', 'status': 'passed', 'evidence': 'rapporto scritto'}], 'warnings': [], 'delivery': delivery}
            review = read_review(handoff, folder, self.root, 'claude', contract)
            return json.dumps({'ok': True, 'output_dir': str(folder), 'handoff': handoff, 'quality_review': review,
                               'available_files': [str(report)]})
        if purpose == 'delivery':
            self.version += 1
            path = folder / 'documento.md'; path.write_text('Documento versione ' + str(self.version))
        else:
            path = folder / 'bozza.md'; path.write_text('Bozza')
        checks = [{'name': 'Rilettura', 'status': 'passed', 'evidence': 'riaperto'}]
        if 'security.no_secrets' in instructions and self.declare:
            checks.append({'name': 'Segreti', 'status': 'passed', 'evidence': 'grep senza risultati', 'policy_check': 'security.no_secrets'})
        handoff = {'task': 'work', 'source_files': [], 'output_files': [str(path)], 'previews': [], 'checks': checks,
                   'warnings': [], 'delivery': delivery}
        record = {'id': folder.name, 'technical_status': 'passed', 'requirements': {}, 'verified_products': [str(path)],
                  'files': [{'path': str(path), 'sha256': digest(path), 'role': 'export', 'primary': True}]}
        return json.dumps({'ok': True, 'output_dir': str(folder), 'handoff': handoff, 'delivery_record': record,
                           'available_files': [str(path)], 'quality_review': None})

    def test_brief_to_delivery_is_enforced_by_the_runtime(self):
        from test_project_skills import role
        from righaven.audit_log import page
        publish(security())
        publish(security(id='accessibility', title='Accessibilità', rules=['Titoli e testo alternativo'], handoff_checks=[],
                                  final_checks=[{'id': 'headings', 'requirement': 'Gerarchia dei titoli corretta', 'method': 'structural'}]))
        publish(security(id='publication', title='Pubblicazione', rules=['Approvazione dopo la sicurezza'], handoff_checks=[],
                                  final_checks=[{'id': 'license', 'requirement': 'Licenza dichiarata', 'method': 'content'}],
                                  depends_on=['security']))
        plan = lambda **kwargs: json.loads(harness_plan.func(runtime=self.runtime, **kwargs))
        delegate = lambda step, purpose='work': json.loads(harness_delegate.func(
            agent='workspace', task='Esegui ' + step, step_id=step, purpose=purpose, role_id='writer', runtime=self.runtime))

        # Phase 1-2: brief, then Execution Plan; production waits for the Policy Plan.
        reply = plan(brief='Documento tecnico', outcome_json=json.dumps({'result': 'Documento tecnico', 'format': 'Markdown modificabile'}),
                     roles_json=json.dumps([{**role(), 'id': 'writer', 'title': 'Autore'}, {**role(), 'id': 'reviewer', 'title': 'Revisore indipendente'}]),
                     steps_json=json.dumps([{'id': 'draft', 'agent': 'workspace', 'role_id': 'writer', 'goal': 'Bozza'},
                                            {'id': 'final', 'agent': 'workspace', 'role_id': 'writer', 'goal': 'Documento finale'}]))
        self.assertEqual(reply['project']['governance']['phase'], 'planning')
        self.assertEqual({s['id'] for s in reply['policy_book']}, {'quality_standard', 'security', 'accessibility', 'publication'})
        with self.assertRaisesRegex(ValueError, 'Policy Plan'):
            delegate('draft')
        self.assertEqual(self.calls, [])
        plan(policies_json=json.dumps([{'id': 'security', 'reason': 'Documento pubblico', 'steps': ['draft']},
                                       {'id': 'accessibility', 'reason': 'Lettura sul web'},
                                       {'id': 'publication', 'reason': 'Rilascio pubblico'}]))

        # Phase 3: tasks receive their policies; an undeclared critical check is a violation.
        self.declare = False
        first = delegate('draft')
        self.declare = True
        self.assertIn('security.no_secrets', self.calls[0]['instructions'])
        self.assertIn('Non inserire credenziali', self.calls[0]['instructions'])
        self.assertEqual(first['policy_violations'], ['Policy security.no_secrets'])
        self.assertEqual(first['activity']['status'], 'needs_revision')
        # Every completed phase waits for the user before further production.
        self.assertEqual(first['checkpoint']['steps'], ['draft'])
        launched = len(self.calls)
        with self.assertRaisesRegex(ValueError, 'Fase conclusa'):
            delegate('draft')
        self.assertEqual(len(self.calls), launched)
        self.reply('Correggi la bozza dichiarando il controllo sui segreti')
        self.assertEqual(delegate('draft')['activity']['status'], 'completed')
        self.reply('Bene, prepara il documento finale')
        final = delegate('final', 'delivery')
        self.assertTrue(final['ok'])
        self.assertNotIn('security.no_secrets', self.calls[-1]['instructions'])  # scoped to draft only
        product = '/mnt/user-data/' + Path(final['output_dir']).relative_to(self.root).as_posix() + '/documento.md'
        plan(product_path=product, status='review')

        # Phase 4: delivery is refused until the final multi-policy validation passes.
        with self.assertRaisesRegex(ValueError, 'Policy Plan|revisione separata'):
            plan(status='ready')
        with self.assertRaisesRegex(ValueError, 'revisore indipendente'):
            harness_validate.func(runtime=self.runtime, role_id='writer')
        report = json.loads(harness_validate.func(runtime=self.runtime, role_id='reviewer'))
        self.assertEqual(report['status'], 'failed')
        verdicts = {s['id']: s['status'] for s in report['sheets']}
        # The chat panel recomputes the same verdicts live, with the evidence of each failure.
        live = policy_workflow.live(self.root, projects.governance_state(self.root))
        sheets = {s['id']: s for s in live['sheets']}
        self.assertEqual({k: s['status'] for k, s in sheets.items()}, verdicts)
        self.assertEqual(sheets['security']['findings'][0]['requirement_id'], 'secret_scan')
        self.assertIn('Osservato sul file', sheets['security']['findings'][0]['evidence'])
        self.assertTrue(sheets['quality_standard']['reviewed_at'])
        self.assertEqual(sheets['security']['handoff'], {'required': 1, 'declared': 1, 'violations': []})
        self.assertEqual((live['phase'], live['last_validation']['status']), ('validation', 'failed'))
        self.assertEqual(verdicts, {'quality_standard': 'passed', 'security': 'failed', 'accessibility': 'passed', 'publication': 'pending'})
        self.assertIn('In attesa', next(r['error'] for r in report['reviews'] if r['sheet'] == 'publication'))
        self.assertEqual(sorted(c['sheet'] or 'quality_standard' for c in self.calls if c['purpose'] == 'review'),
                         ['accessibility', 'quality_standard', 'security'])
        with self.assertRaisesRegex(ValueError, 'Policy Plan'):
            plan(status='ready')

        # Correct the violation: a new version is validated again; nothing is launched twice.
        self.secret_free = True
        self.reply('Rimuovi il token e consegna di nuovo')
        corrected = delegate('final', 'delivery')
        plan(product_path='/mnt/user-data/' + Path(corrected['output_dir']).relative_to(self.root).as_posix() + '/documento.md', status='review')
        before = len(self.calls)
        report = json.loads(harness_validate.func(runtime=self.runtime, role_id='reviewer'))
        self.assertEqual(report['status'], 'passed', report)
        reviews = [c for c in self.calls[before:] if c['purpose'] == 'review']
        self.assertEqual(sorted(c['sheet'] or 'quality_standard' for c in reviews), ['accessibility', 'publication', 'quality_standard', 'security'])
        self.assertEqual(reviews[-1]['sheet'], 'publication')  # dependent sheet ran after its prerequisite
        again = json.loads(harness_validate.func(runtime=self.runtime, role_id='reviewer'))
        self.assertEqual(again['status'], 'passed')
        live = policy_workflow.live(self.root, projects.governance_state(self.root))
        self.assertEqual({s['status'] for s in live['sheets']}, {'passed'})
        self.assertEqual(live['product']['integrity'], 'passed')
        self.assertEqual(len(self.calls), before + 4)  # passed sheets are reused, not re-run
        done = plan(status='ready')
        self.assertEqual(done['project']['status'], 'ready')
        self.assertEqual(done['project']['governance']['phase'], 'delivered')
        operations = [(e['operation'], e['status']) for e in page(self.root)['events'] if e['actor'] == 'Policy Book']
        self.assertIn(('Policy Plan definito dal coordinatore', 'completed'), operations)
        self.assertIn(('Validazione finale multi-policy', 'failed'), operations)
        self.assertIn(('Validazione finale multi-policy', 'completed'), operations)


@unittest.skipIf(harness_delegate is None, 'Requires the pinned Gateway tool runtime')
class PolicyRouteTests(unittest.TestCase):
    def test_team_reads_the_book_and_only_administrators_change_it(self):
        from types import SimpleNamespace
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.gateway.authz import AuthContext
        from righaven.policy_routes import router
        app = FastAPI(); app.include_router(router)

        @app.middleware('http')
        async def fixture_auth(request, call_next):
            role = request.headers.get('X-Test-Role')
            user = SimpleNamespace(id=role, system_role=role)
            request.state.auth = AuthContext(user, ['agents:read', 'agents:write'])
            request.state.user = user
            return await call_next(request)
        with tempfile.TemporaryDirectory() as directory, patch.object(state, 'STATE', Path(directory)), TestClient(app) as client:
            user, admin = {'X-Test-Role': 'user'}, {'X-Test-Role': 'admin'}
            listed = client.get('/api/harness/policy-book', headers=user)
            self.assertEqual(listed.status_code, 200, listed.text)
            self.assertEqual(([s['id'] for s in listed.json()['sheets']], listed.json()['can_manage']), (['quality_standard'], False))
            self.assertTrue(client.get('/api/harness/policy-book', headers=admin).json()['can_manage'])
            base = '/api/harness/policy-book/sheets/security'
            self.assertEqual(client.put(base + '/draft', json=security(), headers=user).status_code, 403)
            self.assertEqual(client.post(base + '/publish', headers=user).status_code, 403)
            saved = client.put(base + '/draft', json=security(), headers=admin)
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertEqual(saved.json()['status'], 'draft')
            self.assertEqual(client.put(base + '/draft', json=security(final_checks=[{'id': 'x'}]), headers=admin).status_code, 400)
            published = client.post(base + '/publish', headers=admin).json()
            self.assertEqual((published['status'], published['active_version']), ('active', 1))
            self.assertEqual(published['history'][-1]['actor'], 'admin')
            self.assertEqual(client.get(base, headers=user).json()['versions'][0]['sheet']['rules'], security()['rules'])
            self.assertEqual(client.post(base + '/retire', headers=admin).json()['status'], 'retired')
            self.assertEqual(client.post(base + '/reactivate', headers=admin).json()['status'], 'active')
            self.assertEqual(client.post(base + '/restore', json={'version': 1}, headers=admin).json()['draft']['rules'], security()['rules'])
            self.assertEqual(client.post(base + '/restore', json={}, headers=admin).status_code, 400)
            self.assertEqual(client.delete(base + '/draft', headers=admin).json()['sheet']['draft'], None)
            self.assertEqual(client.post('/api/harness/policy-book/sheets/quality_standard/retire', headers=admin).status_code, 400)
            self.assertEqual(client.post(base + '/unknown', headers=admin).status_code, 404)
            self.assertEqual(client.put(base + '/draft', json=security(), headers={**admin, 'Origin': 'https://evil.test'}).status_code, 403)
