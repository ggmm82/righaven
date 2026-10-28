"""Result discovery and orientation across domains, without a profession catalog."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from righaven import projects
from righaven.project_brief import briefing_issue, validate_outcome
from righaven.project_skills import read_document
from test_project_skills import role


class ProjectBriefTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_complete_results_in_different_domains_need_no_extra_approval(self):
        for domain, form in [('libro', 'Documento impaginato e manoscritto modificabile'),
                             ('palazzo', 'RigHaven preliminare con tavole modificabili, non progetto esecutivo'),
                             ('film', 'Montaggio video con timeline e media'),
                             ('software', 'Sorgenti eseguibili e istruzioni di avvio'),
                             ('evento', 'Piano operativo con calendario e budget'),
                             ('ecosistema orbitale', 'Proposta illustrata con ipotesi esplicite')]:
            with self.subTest(domain=domain):
                outcome = validate_outcome({'title': domain, 'result': 'Proposta di ' + domain, 'format': form})
                self.assertIsNone(briefing_issue(outcome))
                p = projects.create_plan(self.root, 'Richiesta completa', [], outcome=outcome)
                self.assertFalse(p['orientation']['needs_briefing'])
                self.assertEqual(p['outcome']['format'], form)

    def test_unresolved_choices_block_work_and_ready_without_losing_files(self):
        old = self.root / 'outputs/existing.txt'; old.parent.mkdir(); old.write_text('Preservare')
        p = projects.create_plan(self.root, 'Progetto da definire', [], outcome={'result': 'Prodotto richiesto',
                                'questions': ['Quale forma deve avere la consegna?']})
        self.assertEqual(p['status'], 'clarifying')
        invoke = Mock()
        with self.assertRaisesRegex(ValueError, 'scelte sul risultato'):
            projects.execute_step(self.root, 'wordcraft', 'Produrre', '', invoke)
        self.assertFalse(invoke.called)
        with self.assertRaisesRegex(ValueError, 'domande sul risultato'):
            projects.create_plan(self.root, '', [], status='ready')
        with self.assertRaisesRegex(ValueError, 'domande sul risultato'):
            projects.accept_delivery(self.root, 'any')
        self.assertEqual(old.read_text(), 'Preservare')
        p = projects.create_plan(self.root, '', [], outcome={'result': 'Prodotto richiesto', 'format': 'Consegna scelta dall’utente'})
        self.assertEqual(p['status'], 'working')
        captured = []
        def worker(task, started):
            captured.append(task)
            return json.dumps({'ok': True, 'handoff': {'checks': []}})
        projects.execute_step(self.root, 'wordcraft', 'Preparare', '', worker)
        self.assertIn('Consegna scelta dall’utente', captured[0])

    def test_current_task_counts_and_summary_remain_distinct(self):
        steps = [{'id': 'make', 'agent': 'workspace', 'goal': 'Completare il prodotto', 'role_id': 'design'},
                 {'id': 'review', 'agent': 'workspace', 'goal': 'Verificare la versione', 'depends_on': ['make']},
                 {'id': 'optional', 'agent': 'workspace', 'goal': 'Attività facoltativa', 'status': 'skipped'}]
        projects.create_plan(self.root, 'Obiettivo generale', steps, summary='Rifinisco il campione prima di estendere il lavoro.',
                             outcome={'result': 'Prodotto completo', 'format': 'Pacchetto modificabile'})
        seen = []
        def worker(task, started):
            p = projects.read_project(self.root)
            seen.append(p)
            self.assertEqual(p['orientation']['counts']['running'], 1)
            self.assertEqual(p['orientation']['counts']['completed'], 0)
            self.assertEqual(p['orientation']['total'], 2)
            self.assertEqual(p['orientation']['current'][0]['task'], 'Rifinire soltanto il campione')
            self.assertEqual(p['summary'], 'Rifinisco il campione prima di estendere il lavoro.')
            self.assertEqual(p['brief'], 'Obiettivo generale')
            return json.dumps({'ok': True, 'handoff': {'checks': []}})
        projects.execute_step(self.root, 'workspace', 'Rifinire soltanto il campione', 'make', worker)
        p = projects.read_project(self.root)
        self.assertEqual(p['orientation']['counts']['completed'], 1)
        self.assertEqual(p['orientation']['current'], [])
        self.assertEqual(p['orientation']['remaining'][0]['goal'], 'Verificare la versione')

    def test_reassigning_an_activity_does_not_claim_the_new_role_has_already_worked(self):
        projects.create_plan(self.root, 'Obiettivo', [{'id': 'task', 'agent': 'workspace', 'goal': 'Produrre', 'role_id': 'design'}])
        projects.execute_step(self.root, 'workspace', 'Produci', 'task',
            lambda task, started: json.dumps({'ok': True}), role=role())
        projects.create_plan(self.root, '', [{'id': 'task', 'agent': 'workspace', 'goal': 'Verificare', 'role_id': 'verify', 'status': 'pending'}])
        p = projects.read_project(self.root)
        self.assertEqual(p['orientation']['roles']['design']['attempts'], 1)
        self.assertNotIn('verify', p['orientation']['roles'])
        self.assertEqual(p['steps'][0]['role_id'], 'verify')

    def test_result_definition_reaches_versioned_memory_and_recompiles_roles(self):
        projects.create_plan(self.root, 'Richiesta', [], outcome={'result': 'Contenuto', 'format': 'Testo modificabile'})
        projects.sync_acceptance(self.root, ['Richiesta effettiva'])
        projects.sync_project_context(self.root, [role()])
        first = projects.read_project(self.root)
        projects.create_plan(self.root, '', [], outcome={'result': 'Contenuto', 'format': 'Prodotto impaginato e sorgente'})
        projects.sync_project_context(self.root)
        second = projects.read_project(self.root)
        self.assertNotEqual(first['roles'][0]['version'], second['roles'][0]['version'])
        memory = json.loads(read_document(self.root, second['memory']))
        self.assertEqual(memory['project_outcome']['format'], 'Prodotto impaginato e sorgente')
        self.assertEqual(second['acceptance']['hash'], first['acceptance']['hash'])  # A coordinator reformulation is not a user instruction.

    def test_owner_method_choice_reaches_workers_and_invalidates_old_approvals(self):
        projects.create_plan(self.root, 'Illustrazione', [], outcome={'result': 'Scena', 'format': 'Sorgente modificabile'})
        projects.sync_acceptance(self.root, ['Illustrazione richiesta'])
        projects.sync_project_context(self.root, [role()])
        before = projects.read_project(self.root)
        choice = projects.set_user_direction(self.root, 'vector', 'Tutti gli elementi disegnati modificabili')
        self.assertEqual(choice['user_direction']['revision'], 1)
        self.assertNotEqual(before['acceptance']['hash'], projects.read_project(self.root)['acceptance']['hash'])
        projects.sync_acceptance(self.root, ['Illustrazione richiesta'])
        projects.sync_project_context(self.root)
        after = projects.read_project(self.root)
        self.assertNotEqual(before['roles'][0]['version'], after['roles'][0]['version'])
        memo = json.loads(read_document(self.root, after['memory']))
        self.assertEqual(memo['user_direction']['visual_approach'], 'vector')
        tasks = []
        projects.execute_step(self.root, 'workspace', 'Produci', '',
            lambda task, started: tasks.append(task) or json.dumps({'ok': True}))
        self.assertIn('Tutti gli elementi disegnati modificabili', tasks[0])
        projects.create_plan(self.root, 'Piano nuovo del coordinatore', [])
        self.assertEqual(projects.read_project(self.root)['user_direction'], choice['user_direction'])
        self.assertEqual(projects.set_user_direction(self.root, 'vector', 'Tutti gli elementi disegnati modificabili')['user_direction']['revision'], 1)
        self.assertEqual(projects.set_user_direction(self.root, 'mixed', 'Testi separati')['user_direction']['revision'], 2)
        for invalid in ('invented', ''):
            with self.assertRaises(ValueError): projects.set_user_direction(self.root, invalid, '')

    def test_no_silent_truncation_or_fictional_domain_fields(self):
        for data in ({'result': 'Solo argomento'}, {'result': 'Prodotto', 'format': 'x' * 501},
                     {'questions': ['q'] * 4}, {'profession': 'Invented fixed catalog'}):
            with self.subTest(data=str(data)[:80]), self.assertRaises(ValueError):
                validate_outcome(data)
        self.assertTrue(briefing_issue(None))

    def test_questions_cannot_be_cleared_in_the_same_real_user_turn(self):
        projects.create_plan(self.root,'Richiesta',[],outcome={'result':'Prodotto', 'questions':['Quale forma?']}, source_turn='human-one')
        for turn in ('', 'human-one'):
            with self.assertRaisesRegex(ValueError,'nuova risposta reale'):
                projects.create_plan(self.root,'',[],outcome={'result':'Prodotto','format':'Pacchetto modificabile'},source_turn=turn)
        projects.create_plan(self.root,'',[],outcome={'result':'Prodotto','format':'Pacchetto modificabile'},source_turn='human-two')
        self.assertFalse(projects.read_project(self.root)['orientation']['needs_briefing'])

    def test_owner_pause_survives_replanning_and_blocks_workers_until_explicit_resume(self):
        projects.create_plan(self.root,'Richiesta completa',[],outcome={'result':'Prodotto','format':'Pacchetto modificabile'})
        projects.set_user_control(self.root,True)
        projects.create_plan(self.root,'Nuovo piano del coordinatore',[])
        invoke=Mock()
        with self.assertRaisesRegex(ValueError,'pausa'):
            projects.execute_step(self.root,'workspace','Esegui','',invoke)
        self.assertFalse(invoke.called)
        self.assertTrue(projects.read_project(self.root)['user_control']['paused'])
        projects.set_user_control(self.root,False)
        projects.execute_step(self.root,'workspace','Esegui','',lambda task,started: json.dumps({'ok':True}))
