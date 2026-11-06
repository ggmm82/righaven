"""Replay the failed task's state transitions without granting the model owner privileges."""
import json
from pathlib import Path
import tempfile
import unittest
from righaven import journeys, projects, state
from righaven.progress import utcnow
from righaven.published_files import read, inventory
from righaven.tool_contracts import argument_error, closed_schema


class OutcomeWorkflowTests(unittest.TestCase):
    def test_unknown_stage_rewrite_is_not_a_successful_read(self):
        schema={'type':'object','properties':{'stage_id':{'type':'string'},'expected_revision':{'type':'integer'}}}
        wrong={'current':'data','stages_json':'[{"id":"understand","status":"completed"}]'}
        error=argument_error(wrong,schema)
        self.assertEqual(error['code'],'invalid_tool_arguments')
        self.assertFalse(error['changed'])
        self.assertIsNone(argument_error({},schema))
        self.assertFalse(closed_schema(schema)['additionalProperties'])
        self.assertNotIn('additionalProperties',schema,'never mutate a cached provider schema')

    def test_published_files_are_owner_scoped_and_independent_of_sandbox(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);alice=root/'alice';bob=root/'bob'
            (alice/'outputs/job').mkdir(parents=True);(bob/'outputs/job').mkdir(parents=True)
            path=alice/'outputs/job/report.md';path.write_text('Actual published result\nSecond line')
            result=read(alice,'/mnt/user-data/outputs/job/report.md',start_line=2)
            self.assertEqual(result['content'],'Second line')
            self.assertEqual(inventory(alice,pattern='**/*.md')['files'],['/mnt/user-data/outputs/job/report.md'])
            for rejected in (str(path),'/mnt/user-data/outputs/../../alice/outputs/job/report.md'):
                with self.assertRaises(ValueError):read(bob,rejected)
            (alice/'outputs/leak').symlink_to(root/'bob')
            (bob/'secret.txt').write_text('must not be visible')
            with self.assertRaises(ValueError):read(alice,'/mnt/user-data/outputs/leak/secret.txt')

    def test_first_result_has_no_unrequested_pipeline_and_keeps_legacy_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            fast=journeys.start(root/'fast','data-pipeline',{'goal':'A simple dashboard with example data'},mode='first_result')
            self.assertEqual([s['id'] for s in fast['stages']],['preview'])
            self.assertEqual(fast['answers']['goal'],'A simple dashboard with example data')
            self.assertNotIn('policy',fast['definition'],'the full method cannot reintroduce excluded deliverables')
            legacy=journeys.start(root/'legacy','data-pipeline',{'goal':'A complete scheduled pipeline'})
            self.assertEqual(len(legacy['stages']),7)
            with self.assertRaises(ValueError):journeys.start(root/'legacy','data-pipeline',{'goal':'Changed'},legacy['revision'],mode='first_result')

    def test_recorded_review_submits_once_then_only_owner_advances(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);output=work/'outputs';output.mkdir()
            html=output/'dashboard.html';html.write_text('<h1>Verified sales dashboard</h1>')
            report=output/'review.md';report.write_text('Values reconcile; browser filters work')
            source=output/'source.js';source.write_text('editable source')
            journeys.start(work,'data-pipeline',{'goal':'A simple dashboard with example data'},mode='first_result')
            projects.create_plan(work,'Dashboard',[
                {'id':'draft','agent':'workspace','goal':'Build usable dashboard','depends_on':[]},
                {'id':'check','agent':'workspace','goal':'Independent verification','depends_on':['draft']},
                {'id':'release','agent':'workspace','goal':'Deliver sources','depends_on':[]}])
            def finish(identifier,filename,purpose,role):
                path=work/'.righaven-project/project.json';p=json.loads(path.read_text())
                step=next(s for s in p['steps'] if s['id']==identifier)
                step.update(status='completed',purpose=purpose,role_id=role,attempts=[{
                    'started_at':utcnow(),'finished_at':utcnow(),'status':'completed','validated':True,
                    'output_files':[str(filename)],'quality_review':{'status':'passed'}}])
                state.atomic_json(path,p)
            journeys.begin_activity(work,'preview','draft');finish('draft',html,'preview','author')
            self.assertEqual(journeys.reconcile(work)['stages'][0]['status'],'working','no self-approval without a review')
            journeys.begin_activity(work,'preview','check');finish('check',report,'review','checker')
            reviewed=journeys.reconcile(work)
            self.assertEqual(reviewed['awaiting_owner'],['preview'])
            self.assertEqual(journeys.reconcile(work)['revision'],reviewed['revision'],'no duplicate submissions from polling/retries')
            self.assertEqual(journeys.compact(reviewed)['next_action']['action'],'await_owner')
            with self.assertRaises(ValueError):journeys.begin_activity(work,'delivery','release')
            approved=journeys.decide(work,'preview',True,reviewed['revision'])
            self.assertIsNone(approved['current'])
            done=journeys.reconcile(work)
            self.assertEqual(done['stages'][0]['evidence'],reviewed['stages'][0]['evidence'],'approval reuses existing verified files without another assignment')
            self.assertTrue(done['complete'])
            self.assertTrue(html.exists())
            self.assertEqual(journeys.compact(done)['next_action']['action'],'validate_delivery','normal final quality validation still applies')

    def test_owner_simplifies_existing_path_without_losing_files_or_organization_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            work=Path(directory);(work/'outputs').mkdir()
            artifact=work/'outputs/catalog.md';artifact.write_text('Retained source catalog')
            old=journeys.start(work,'data-pipeline',{'goal':'A simple dashboard'})
            projects.create_plan(work,'Dashboard',[{'id':'catalog','agent':'workspace','goal':'Catalog','depends_on':[]}])
            project=work/'.righaven-project/project.json';before=json.loads(project.read_text())
            organization=[s['id'] for s in before['policy_plan']['sheets'] if not s.get('source_recipe')]
            new=journeys.simplify(work,old['revision'])
            self.assertEqual(new['mode'],'first_result')
            self.assertEqual(new['answers'],old['answers'])
            self.assertEqual(len(new['stages']),1)
            archived=json.loads((work/'.righaven-project/journey-history'/f"{old['revision']}.json").read_text())
            self.assertEqual(archived['definition'],old['definition'])
            self.assertEqual(artifact.read_text(),'Retained source catalog')
            after=json.loads(project.read_text())
            self.assertEqual([s['id'] for s in after['policy_plan']['sheets']],organization)
            with self.assertRaises(ValueError):journeys.simplify(work,old['revision'])

    def test_review_belongs_to_the_phase_and_another_author(self):
        project={'steps':[
            {'id':'work','status':'completed','purpose':'work','role_id':'author','attempts':[{'finished_at':'2026-11-02T08:10:00Z'}]},
            {'id':'review','status':'completed','purpose':'review','phase_id':'preview','role_id':'checker',
             'attempts':[{'finished_at':'2026-11-02T08:11:00Z','quality_review':{'status':'passed'}}]},
            {'id':'future_review','status':'pending','purpose':'review','phase_id':'delivery','attempts':[]}]}
        journeys._require_review(project,['work'],'preview')
        project['steps'][1]['role_id']='author'
        with self.assertRaises(ValueError):journeys._require_review(project,['work'],'preview')


if __name__=='__main__':unittest.main()
