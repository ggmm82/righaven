"""Generic project skills, original brief provenance and actual worker context."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import projects
from righaven.project_skills import load_compiled, read_document, validate_roles
from righaven.run_agent import verify_project_context


def role(**changes):
    return dict(id='design', title='Responsabile della soluzione', mission='Risolvere il problema conservando i vincoli',
                expertise=['Analizzare vincoli e dipendenze specifici'], procedure=['Leggere gli input', 'Confrontare alternative sugli stessi vincoli'],
                checks=['Confrontare la proposta con ogni vincolo citando evidenze'], deliverables=['Prodotto e sorgenti modificabili'],
                inputs=[], risks=['Separare ipotesi da fatti'], tools=[], **changes)


class ProjectSkillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        projects.create_plan(self.root, 'Risultato richiesto', [])

    def compile(self, text, specs=None, memory=None):
        projects.sync_acceptance(self.root, [text])
        projects.sync_project_context(self.root, specs, memory)
        return projects.read_project(self.root)

    def test_same_compiler_supports_distinct_and_unanticipated_domains(self):
        # These are test inputs, never a production dispatch/profession catalog.
        cases = [('libro', 'Coerenza dei personaggi', []), ('palazzo', 'Vincoli di accessibilità', ['cadcraft']),
                 ('film', 'Continuità tra inquadrature', ['filmcraft', 'soundcraft']),
                 ('software', 'Manuale installabile insieme al prodotto', ['calibre']), ('evento', 'Distribuzione del programma ai partecipanti', ['calibre', 'wordcraft']),
                 ('ecosistema orbitale immaginario', 'Esplicitare assunzioni fisiche', [])]
        for index, (domain, expertise, tools) in enumerate(cases):
            with self.subTest(domain=domain):
                spec = role(); spec.update(id='role' + str(index), expertise=[expertise], tools=tools)
                p = self.compile('Progetta ' + domain, [spec], {'decisione': domain})
                compiled = p['roles'][0]
                text = load_compiled(self.root, compiled)
                for expected in (expertise, *spec['procedure'], *spec['checks'], *spec['deliverables']):
                    self.assertIn(expected, text)
                from righaven.environments import required_tools
                self.assertEqual(compiled['tools'],required_tools(tools))
                verify_project_context({'acceptance': p['acceptance'], 'role': compiled}, self.root)

    def test_compiler_rejects_title_only_and_uninstalled_tools(self):
        apps = projects.applications()
        for key in ('expertise', 'procedure', 'checks', 'deliverables'):
            spec = role(); spec[key] = []
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_roles([spec], apps)
        spec = role(); spec['tools'] = ['invented-cli']
        with self.assertRaises(ValueError):
            validate_roles([spec], apps)

    def test_versions_follow_request_memory_method_and_tool_release(self):
        p = self.compile('Vincolo iniziale', [role()]); first = p['roles'][0]
        projects.sync_project_context(self.root)
        self.assertEqual(projects.read_project(self.root)['roles'][0]['version'], first['version'])
        p = self.compile('Vincolo aggiornato in fondo', memory={'decision': 'Controllare il vincolo'})
        self.assertNotEqual(first['version'], p['roles'][0]['version'])
        self.assertIn('Vincolo iniziale', read_document(self.root, p['acceptance']['request_documents'][0]))
        self.assertIn('Missione', load_compiled(self.root, first))  # Earlier version is retained.
        version = p['roles'][0]['version']
        projects.sync_project_context(self.root, memory={'extra': 'Nuovo dato'})
        self.assertNotEqual(version, projects.read_project(self.root)['roles'][0]['version'])
        spec = role(); spec['tools'] = ['cadcraft']
        p = self.compile('Vincolo', [spec]); previous = p['roles'][0]['version']
        apps = copy.deepcopy(projects.applications())
        next(a for a in apps if a['id'] == 'cadcraft')['version'] = 'new-version'
        with patch.object(projects, 'applications', return_value=apps):
            projects.sync_project_context(self.root)
        self.assertNotEqual(previous, projects.read_project(self.root)['roles'][0]['version'])

    def test_long_original_and_all_clarifications_survive_compact_previews(self):
        original = 'INIZIO ' + 'vincoli centrali ' * 1000 + ' FINE: prima solo la bozza'
        p = self.compile(original, [role()])
        a = p['acceptance']
        self.assertLess(len(a['user_requests'][0]), 2100)
        self.assertEqual(read_document(self.root, a['request_documents'][0]), original)
        for i in range(14):
            projects.sync_acceptance(self.root, ['Chiarimento ' + str(i)])
        p = projects.read_project(self.root); a = p['acceptance']
        documents = json.loads(read_document(self.root, a['request_manifest']))
        self.assertEqual(len(documents), 15)
        self.assertEqual(len(a['user_requests']), 9)
        self.assertEqual(read_document(self.root, documents[3]), 'Chiarimento 2')
        projects.sync_project_context(self.root)
        verify_project_context({'acceptance': a, 'role': projects.read_project(self.root)['roles'][0]}, self.root)
        # Even an archived clarification omitted from previews is still checked.
        path = self.root / Path(documents[3]['path']).relative_to('/mnt/user-data')
        path.write_text('ALTERATO')
        with self.assertRaisesRegex(ValueError, 'modificato'):
            verify_project_context({'acceptance': a}, self.root)

    def test_legacy_prefix_is_recovered_only_from_real_complete_history(self):
        original = 'Brief ' + 'contenuto ' * 800 + ' coda vincolante'
        with projects.locked(self.root) as folder:
            value = projects.load(folder, self.root)
            value['acceptance'] = {'user_requests': [original[:4000]]}
            projects.atomic_json(folder / 'project.json', value)
        projects.sync_acceptance(self.root, [original])
        a = projects.read_project(self.root)['acceptance']
        self.assertEqual(a['request_count'], 1)
        self.assertEqual(read_document(self.root, a['request_documents'][0]), original)

    def test_memory_preserves_arbitrary_structure_and_redacts_recognized_secrets(self):
        p = self.compile('Brief', [role()], {'nested': {'items': [1, True, 'testo password: nascosta'],
                                                     'token': 'private'}, 'custom': {'domain': 'arbitrario'}})
        memory = json.loads(read_document(self.root, p['memory']))
        self.assertEqual(memory['nested']['items'], [1, True, 'testo [omesso]'])
        self.assertEqual(memory['nested']['token'], '[omesso]')
        self.assertEqual(memory['custom'], {'domain': 'arbitrario'})

    def test_lessons_survive_role_changes_and_keep_prior_evidence(self):
        lesson = {'problem': 'Dependency omitted', 'result': 'observed_on_one_case',
                  'check': 'Reopen a copied package', 'evidence': '/mnt/user-data/outputs/review.json'}
        p = self.compile('Brief', [role()], {'lesson_dependencies': lesson})
        first_memory, first_role = p['memory'], p['roles'][0]
        revised = role(); revised['checks'].append(lesson['check'])
        projects.sync_project_context(self.root, [revised], {'lesson_comparison': {'result': 'not_verified'}})
        current = projects.read_project(self.root)
        memory = json.loads(read_document(self.root, current['memory']))
        self.assertEqual(memory['lesson_dependencies'], lesson)
        self.assertEqual(memory['lesson_comparison']['result'], 'not_verified')
        self.assertIn(lesson['check'], load_compiled(self.root, current['roles'][0]))
        self.assertNotIn(lesson['check'], load_compiled(self.root, first_role))
        self.assertEqual(json.loads(read_document(self.root, first_memory))['lesson_dependencies'], lesson)
        verify_project_context({'role': current['roles'][0]}, self.root)

    def test_skill_and_memory_integrity_and_scoped_paths(self):
        p = self.compile('Brief', [role()], {'decisione': 'Reale'})
        compiled = p['roles'][0]
        path = self.root / Path(compiled['skill']['path']).relative_to('/mnt/user-data')
        path.write_text('Skill alterata')
        with self.assertRaisesRegex(ValueError, 'versione'):
            load_compiled(self.root, compiled)
        evil = copy.deepcopy(compiled); evil['skill']['path'] = '/mnt/user-data/../../etc/passwd'
        with self.assertRaises(ValueError):
            load_compiled(self.root, evil)
        memory = self.root / Path(p['memory']['path']).relative_to('/mnt/user-data')
        memory.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'modificato'):
            verify_project_context({'role': compiled}, self.root)

    def test_workspace_activity_exposes_role_and_bound_original_to_executor(self):
        p = self.compile('Prima il piano, non il prodotto completo', [role()])
        projects.create_plan(self.root, '', [{'id': 'prepare', 'agent': 'workspace', 'role_id': 'design', 'goal': 'Piano verificabile'}])
        seen = []
        def invoke(task, started):
            seen.append(task)
            return json.dumps({'ok': True, 'handoff': {'output_files': [], 'checks': []}})
        projects.execute_step(self.root, 'workspace', 'Prepara il piano', 'prepare', invoke, role=p['roles'][0])
        current = projects.read_project(self.root)
        self.assertEqual(current['steps'][0]['role_title'], p['roles'][0]['title'])
        self.assertIn(p['acceptance']['request_manifest']['path'], seen[0])
        self.assertEqual(current['steps'][0]['status'], 'completed')
