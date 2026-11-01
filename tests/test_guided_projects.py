"""Persistent owner-guided projects, evidence invalidation and recipe-specific policies."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import journeys, projects, policy_book, state


class GuidedProjects(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / 'alice'; self.work.mkdir()
        patcher = patch.object(state, 'STATE', self.root / 'state'); patcher.start(); self.addCleanup(patcher.stop)
        self.value = journeys.start(self.work, 'data-pipeline', {'goal':'Create a documented data laboratory and business reports'})
        projects.create_plan(self.work, 'Data laboratory', [{'id':'catalog','agent':'workspace','goal':'Read documentation','depends_on':[]}])

    def submit(self, identifier, filename='catalog.md'):
        path=self.work/filename; path.write_text('Verified model and provenance')
        value=journeys.view(self.work)
        return journeys.record(self.work,identifier,[str(path)],['catalog'],'The catalog is ready for owner review',value['revision'])

    def test_start_and_read_survive_reload_without_connections_or_native_plan(self):
        other=self.root/'other';other.mkdir()
        value=journeys.start(other,'data-pipeline',{'goal':'Read attached documentation'})
        self.assertEqual(journeys.view(other)['revision'],value['revision'])
        self.assertTrue(value['connections_optional']); self.assertFalse(value['complete'])
        self.assertEqual(value['current'],'understand')
        self.assertIsNone(journeys.view(self.root/'bob'))

    def test_only_owner_decision_advances_and_is_revision_checked(self):
        submitted=self.submit('understand')
        self.assertEqual(submitted['stages'][0]['status'],'review')
        with self.assertRaises(ValueError): journeys.decide(self.work,'understand',True,submitted['revision']-1)
        approved=journeys.decide(self.work,'understand',True,submitted['revision'])
        self.assertEqual(approved['current'],'design')
        with self.assertRaises(ValueError): self.submit('package')

    def test_start_work_links_native_steps_and_rejects_missing_artifacts(self):
        working=journeys.record(self.work,'understand',[],['catalog'],'Reading the saved documentation',self.value['revision'])
        self.assertEqual(working['stages'][0]['status'],'working')
        with self.assertRaises(ValueError):journeys.decide(self.work,'understand',True,working['revision'])
        with self.assertRaises(ValueError):journeys.record(self.work,'understand',['/etc/passwd'],['catalog'],'No external evidence',working['revision'])
        with self.assertRaises(ValueError):journeys.record(self.work,'understand',[],['missing'],'Invalid native activity',working['revision'])

    def test_changed_evidence_invalidates_downstream_and_cannot_be_approved(self):
        v=self.submit('understand');journeys.decide(self.work,'understand',True,v['revision'])
        v=self.submit('design','design.md');journeys.decide(self.work,'design',True,v['revision'])
        (self.work/'catalog.md').write_text('The source schema changed')
        v=journeys.view(self.work)
        self.assertEqual([s['status'] for s in v['stages'][:2]],['stale','stale'])
        with self.assertRaises(ValueError):journeys.decide(self.work,'design',True,v['revision'])
        self.assertFalse(v['complete'])

    def test_recipe_policy_is_pinned_and_survives_coordinator_policy_changes(self):
        value=projects.read_project(self.work)
        self.assertIsNotNone(value['journey'])
        with projects.locked(self.work) as folder:
            raw=projects.load(folder,self.work)
        sheet=next(s for s in raw['policy_plan']['sheets'] if s['id']=='data_pipeline_delivery')
        self.assertTrue(any(c['id']=='bi_delivered' for c in sheet['final_checks']))
        self.assertNotIn('data_pipeline_delivery',[s['id'] for s in policy_book.book()])
        projects.set_policy_plan(self.work,[])
        with projects.locked(self.work) as folder:
            raw=projects.load(folder,self.work)
        self.assertIn('data_pipeline_delivery',[s['id'] for s in raw['policy_plan']['sheets']])
        with self.assertRaisesRegex(ValueError,'guided phases'):
            projects.create_plan(self.work,'',[],status='ready')

    def test_changed_answers_stale_existing_results_and_keep_sources(self):
        v=self.submit('understand');journeys.decide(self.work,'understand',True,v['revision'])
        current=journeys.view(self.work)
        changed=journeys.start(self.work,'data-pipeline',{'goal':'Change the business measures'},current['revision'])
        self.assertEqual(changed['stages'][0]['status'],'stale')
        self.assertTrue((self.work/'catalog.md').exists())
        with self.assertRaises(ValueError):journeys.start(self.work,'data-pipeline',{'goal':'Another edit'},current['revision'])

    def test_assignments_cannot_bypass_phase_gates(self):
        with self.assertRaisesRegex(ValueError,'current guided phase'):
            projects.execute_step(self.work,'workspace','Build later work','catalog',lambda *a: self.fail('worker must not start'))

    def test_definition_is_pinned_and_not_replaced_by_a_catalog_update(self):
        original=journeys.view(self.work)['definition']
        with patch.object(journeys,'definition',side_effect=AssertionError('Must use pinned workflow')):
            self.assertEqual(journeys.view(self.work)['definition'],original)


if __name__=='__main__':unittest.main()
