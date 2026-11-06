"""A revision must apply the supplied activity plan instead of acknowledging and dropping it."""
import json
from pathlib import Path
import tempfile
import unittest
from righaven import projects
from righaven.project_store import locked
from righaven.state import atomic_json


class PlanRevisions(unittest.TestCase):
    def test_reopen_and_replan_preserve_results_and_prior_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'outputs/baseline.sql';source.parent.mkdir();source.write_text('original source')
            initial=[{'id':'build','agent':'workspace','goal':'Build a local SQL pipeline'},{'id':'verify','agent':'workspace','goal':'Verify the local pipeline'}]
            projects.create_plan(root,'Initial pipeline',initial,outcome={'result':'Local pipeline','format':'SQL sources'})
            with locked(root) as folder:
                value=json.loads((folder/'project.json').read_text());attempt={'status':'completed','task':'Build a local SQL pipeline','output_files':[str(source)]}
                value['steps'][0].update(status='completed',attempts=[attempt]);atomic_json(folder/'project.json',value)
            updated=projects.create_plan(root,'Adapt the existing pipeline',[
                {'id':'build','agent':'workspace','goal':'Build cloud notebooks and a semantic model'},
                {'id':'verify','agent':'workspace','goal':'Verify deployment and business measures'}],
                revise_step_id='build',revision_reason='Adapt the approved result',status='working',
                outcome={'result':'Cloud notebook pipeline','format':'Notebook and model sources'})
            self.assertEqual(updated['steps'][0]['goal'],'Build cloud notebooks and a semantic model')
            self.assertEqual(updated['steps'][1]['goal'],'Verify deployment and business measures')
            self.assertEqual(updated['outcome']['result'],'Cloud notebook pipeline')
            with locked(root) as folder:
                persisted=json.loads((folder/'project.json').read_text());before=(folder/'project.json').read_bytes()
                self.assertEqual(persisted['steps'][0]['attempts'],[attempt]);self.assertTrue(persisted['steps'][0]['revision_id'])
            with self.assertRaises(ValueError):projects.create_plan(root,'Invalid update',[{'id':'bad','agent':'absent','goal':'Bad'}],revise_step_id='build',revision_reason='Attempted revision')
            self.assertEqual((root/'.righaven-project/project.json').read_bytes(),before)
            with self.assertRaises(ValueError):projects.create_plan(root,'Reject forged completion',[{'id':'verify','agent':'workspace','goal':'Verify deployment and business measures','status':'completed'}],revise_step_id='build',revision_reason='Do not commit a partial reopening')
            self.assertEqual((root/'.righaven-project/project.json').read_bytes(),before)
            self.assertEqual(source.read_text(),'original source')
