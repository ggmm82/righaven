import json
from pathlib import Path
import tempfile
import unittest

from righaven import experience, lessons, projects
from righaven.production_observations import observations, recent_context
from test_project_skills import role


class ProductionObservationsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.root = Path(directory.name); self.workspace = self.root / 'thread'
        self.library = self.root / 'library'
        projects.create_plan(self.workspace, 'Complete product', [])
        projects.sync_acceptance(self.workspace, ['Deliver an editable product'])
        self.output = self.workspace / 'outputs/workspace/rh-job-123456abcdef'
        self.output.mkdir(parents=True)
        self.product = self.output / 'sample.svg'; self.product.write_text('<svg/>')
        self.report = self.output / 'handoff.json'
        self.report.write_text(json.dumps({'output_files': [str(self.product)],
            'checks': [{'name':'Geometry readability','status':'failed','evidence':'Components overlap at the contact frame.'},
                       {'name':'Export','status':'passed','evidence':'Export succeeded'},
                       {'name':'Audio','status':'not_run','evidence':'Not observed'}]}))
        self.attempt = {'status':'paused','validated':False,'output_dir':str(self.output),
                        'finished_at':'2026-10-21T12:00:00Z','output_files':[str(self.product)]}
        self.state = self.workspace / '.righaven-project/project.json'
        value = json.loads(self.state.read_text())
        value['steps'] = [{'id':'sample','agent':'workspace','goal':'Sample','depends_on':[],
                           'status':'paused','attempts':[self.attempt]}]
        self.state.write_text(json.dumps(value))

    def test_interrupted_handoff_is_retained_without_formal_review_or_lesson_file(self):
        self.assertEqual(experience.collect(self.workspace, self.library, 'thread-a'), 1)
        self.assertEqual(experience.collect(self.workspace, self.library, 'thread-a'), 0)
        source = experience.entries(self.library)[0]
        self.assertEqual(source['observation']['status'], 'reported_failure')
        self.assertEqual(len(lessons.pending(self.library)), 1)
        self.assertEqual(lessons.propose_findings(self.library, 'thread-a'), [])
        self.assertEqual(lessons.accepted(self.library), set())
        self.assertEqual(experience.select(self.library, [role()], projects.applications()), [])
        lesson = {'category':'production_method','title':'Isolate overlapping components',
                  'applies_when':'A composition has overlapping components',
                  'procedure':['Inspect one component at a time before replacing the renderer'],
                  'verification':['Compare the same frame before and after the change'],
                  'limits':'A reported failure suggests a diagnostic step, not a proven improvement','tools':[]}
        identifier = lessons.learn(self.library, [source['id']], lesson)
        self.assertNotIn(identifier, lessons.accepted(self.library))
        lessons.accept(self.library, identifier)
        self.assertIn(identifier, lessons.accepted(self.library))

    def test_next_role_gets_failure_evidence_without_relying_on_coordinator_summary(self):
        original = self.product.read_bytes(); seen = []
        def invoke(task, started):
            seen.append(task)
            return json.dumps({'ok':False,'error':'Fixture provider unavailable'})
        projects.execute_step(self.workspace, 'workspace', 'Diagnose the same product', '', invoke)
        self.assertIn('Components overlap at the contact frame.', seen[0])
        self.assertIn('handoff.json', seen[0])
        self.assertIn('reported_failure', seen[0])
        self.assertEqual(self.product.read_bytes(), original)

    def test_unfinished_or_missing_evidence_never_invents_learning(self):
        self.assertEqual(observations(self.workspace, {**self.attempt, 'status':'running'}, {}, None), [])
        self.product.unlink()
        self.assertEqual(experience.collect(self.workspace, self.library), 0)
        self.report.write_text('null')
        self.assertEqual(experience.collect(self.workspace, self.library), 0)

    def test_other_job_files_and_symlinked_reports_are_not_evidence(self):
        elsewhere = self.workspace / 'other.svg'; elsewhere.write_text('<svg/>')
        self.report.write_text(json.dumps({'output_files':[str(elsewhere)],
            'checks':[{'name':'Wrong','status':'failed','evidence':'Unrelated artifact'}]}))
        self.assertEqual(experience.collect(self.workspace, self.library), 0)
        self.report.unlink(); self.report.symlink_to(elsewhere)
        self.assertEqual(experience.collect(self.workspace, self.library), 0)

    def test_observation_context_is_bounded_and_does_not_approve_results(self):
        value = json.loads(self.state.read_text())
        value['steps'][0]['attempts'] *= 10
        result = recent_context(self.workspace, value)
        self.assertLessEqual(len(result), 3)
        self.assertEqual(len(result), 1)
        self.assertTrue(all(r['status'] == 'reported_failure' for r in result))

    def test_virtual_paths_and_large_exports_keep_evidence_bounded(self):
        large = self.output / 'render.mp4'
        with large.open('wb') as stream:
            stream.truncate(32 * 1024 * 1024)
        virtual = '/mnt/user-data/' + self.output.relative_to(self.workspace).as_posix()
        value = json.loads(self.report.read_text())
        value.update(output_files=[virtual + '/render.mp4'], previews=[virtual + '/sample.svg'] * 5)
        self.report.write_text(json.dumps(value))
        records = observations(self.workspace, {**self.attempt, 'output_dir':virtual}, {}, 'thread-a')
        self.assertEqual(len(records), 1)
        self.assertEqual([f['path'] for f in records[0]['observation']['evidence_files']], [virtual + '/sample.svg'])
