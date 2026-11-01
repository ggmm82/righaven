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

    def test_owner_skips_unneeded_phases_and_can_reopen_them(self):
        v=self.submit('understand');v=journeys.decide(self.work,'understand',None,v['revision'],action='approve')
        proposal=journeys.record(self.work,'design',[],[],'A demo with sample data needs no separate design phase',v['revision'],propose_skip=True)
        self.assertEqual(proposal['awaiting_owner'],['design'])
        self.assertEqual(proposal['stages'][1]['status'],'pending','a coordinator proposal never settles the phase')
        kept=journeys.decide(self.work,'design',None,proposal['revision'],'Serve comunque',action='keep')
        self.assertEqual((kept['awaiting_owner'],kept['stages'][1]['status']),([],'pending'))
        with self.assertRaises(ValueError):journeys.decide(self.work,'design',None,kept['revision'],action='keep')
        proposal=journeys.record(self.work,'design',[],[],'A demo with sample data needs no separate design phase',kept['revision'],propose_skip=True)
        skipped=journeys.decide(self.work,'design',None,proposal['revision'],'Not needed for the demo',action='skip')
        self.assertEqual(skipped['stages'][1]['status'],'skipped')
        self.assertNotIn('proposal',skipped['stages'][1])
        downstream=[s for s in skipped['stages'] if s['depends_on']==['design']]
        self.assertTrue(downstream and all(s['available'] for s in downstream),'a skipped phase satisfies its dependants')
        with self.assertRaises(ValueError):journeys.decide(self.work,'design',None,skipped['revision'],action='skip')
        again=self.submit('understand')
        self.assertEqual(again['stages'][1]['status'],'skipped','new upstream evidence keeps the owner skip')
        reopened=journeys.decide(self.work,'design',None,journeys.decide(self.work,'understand',True,again['revision'])['revision'],action='reopen')
        self.assertEqual(reopened['current'],'design')
        with self.assertRaises(ValueError):journeys.decide(self.work,'design',None,reopened['revision'],action='reopen')
        with self.assertRaises(ValueError):journeys.decide(self.work,'design',None,reopened['revision'],action='delete')

    def test_phase_without_gate_completes_with_evidence_and_compact_view_is_small(self):
        with projects.locked(self.work) as folder:
            raw=json.loads((folder/'journey.json').read_text())
            raw['definition']['stages'][0]['gate']=False
            state.atomic_json(folder/'journey.json',raw)
        done=self.submit('understand')
        self.assertEqual(done['stages'][0]['status'],'approved')
        self.assertEqual(done['current'],'design')
        small=journeys.compact(done)
        self.assertNotIn('definition',small)
        self.assertLess(len(json.dumps(small)),len(json.dumps(done))/2)
        self.assertEqual(small['stages'][0]['evidence'],['/mnt/user-data/catalog.md'])
        self.assertIn('Salta fase',journeys.instructions(self.work))

    def test_team_proposes_every_unneeded_phase_at_once_and_owner_skips_them_together(self):
        start=journeys.view(self.work)
        for stage in ('lab','pipeline','package'):
            start=journeys.record(self.work,stage,[],[],'Una demo con dati di esempio non ne ha bisogno',start['revision'],propose_skip=True)
        self.assertEqual(start['awaiting_owner'],['lab','pipeline','package'],'future phases can be proposed before they are reached')
        with self.assertRaises(ValueError):journeys.decide(self.work,'pipeline',True,start['revision'])
        done=journeys.decide_many(self.work,['lab','pipeline','package'],'skip',start['revision'],'Solo una demo')
        self.assertEqual([s['status'] for s in done['stages']],['pending','pending','skipped','pending','skipped','pending','skipped'])
        self.assertEqual(done['awaiting_owner'],[])
        with self.assertRaises(ValueError):journeys.decide_many(self.work,['design'],'approve',done['revision'])

    def test_goal_from_the_intake_is_the_project_result_without_asking_again(self):
        value=projects.read_project(self.work)
        self.assertEqual(value['outcome']['result'],'Create a documented data laboratory and business reports')
        self.assertEqual(value['outcome']['title'],'Pipeline dati end-to-end')
        self.assertTrue(value['outcome']['format'])
        self.assertIsNone(projects.briefing_issue(value['outcome']))
        # A coordinator that only records open questions keeps the owner's goal as the result.
        projects.create_plan(self.work,'',[],outcome={'questions':['Foglio di calcolo o pagina web?']})
        self.assertEqual(projects.read_project(self.work)['outcome']['result'],'Create a documented data laboratory and business reports')

    def test_guided_phase_gates_replace_chat_checkpoints_while_free_projects_keep_them(self):
        def run(work, step, turn):
            folder=work/'outputs'/(step+turn);folder.mkdir(parents=True,exist_ok=True);(folder/'out.md').write_text('testo')
            reply={'ok':True,'error':'','output_dir':str(folder),'handoff':{'source_files':[],'output_files':[str(folder/'out.md')],'previews':[],
                   'checks':[{'name':'Letto','status':'passed','evidence':'riaperto'}]}}
            return json.loads(projects.execute_step(work,'workspace','Esegui',step,lambda task,started:json.dumps(reply),purpose='work',request_id=turn))
        projects.set_policy_plan(self.work,[])
        working=journeys.record(self.work,'understand',[],['catalog'],'Leggo la documentazione',journeys.view(self.work)['revision'])
        self.assertEqual(working['stages'][0]['status'],'working')
        result=run(self.work,'catalog','turn-1')
        self.assertTrue(result['ok']);self.assertNotIn('checkpoint',result,'no chat confirmation on top of the phase approval')
        free=self.root/'free';free.mkdir()
        projects.create_plan(free,'Documento',[{'id':'draft','agent':'workspace','goal':'Bozza','depends_on':[]}],outcome={'result':'Documento','format':'Markdown'})
        projects.set_policy_plan(free,[])
        self.assertIsNone(journeys.view(free))
        self.assertEqual(run(free,'draft','turn-1')['checkpoint']['steps'],['draft'],'free projects keep their checkpoints')
        self.assertNotIn('journey',{k for k,v in projects.read_project(free).items() if v})

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
        sheet=next(s for s in raw['policy_plan']['sheets'] if s['id']=='recipe_data_pipeline')
        self.assertTrue(any(c['id']=='bi_delivered' for c in sheet['final_checks']))
        self.assertNotIn('recipe_data_pipeline',[s['id'] for s in policy_book.book()])
        projects.set_policy_plan(self.work,[])
        with projects.locked(self.work) as folder:
            raw=projects.load(folder,self.work)
        self.assertIn('recipe_data_pipeline',[s['id'] for s in raw['policy_plan']['sheets']])
        with self.assertRaisesRegex(ValueError,'guided phases'):
            projects.create_plan(self.work,'',[],status='ready')

    def test_changed_answers_stale_existing_results_and_keep_sources(self):
        v=self.submit('understand');journeys.decide(self.work,'understand',True,v['revision'])
        current=journeys.view(self.work)
        changed=journeys.start(self.work,'data-pipeline',{'goal':'Change the business measures'},current['revision'])
        self.assertEqual(changed['stages'][0]['status'],'stale')
        self.assertTrue((self.work/'catalog.md').exists())
        with self.assertRaises(ValueError):journeys.start(self.work,'data-pipeline',{'goal':'Another edit'},current['revision'])

    def test_recipe_never_replaces_a_mandatory_organization_policy(self):
        from copy import deepcopy
        organization=deepcopy(journeys.definition('data-pipeline')['workflow']['policy'])
        organization.update(mandatory=True,title='Organization requirement')
        organization['revision']=policy_book.revision(organization)
        quality=policy_book.book()
        with patch.object(policy_book,'book',return_value=[*quality,organization]):
            projects.create_plan(self.work,'',[])
            projects.set_policy_plan(self.work,[{'id':'recipe_data_pipeline_1','reason':'Already pinned automatically'}])
            with projects.locked(self.work) as folder:raw=projects.load(folder,self.work)
        sheets={s['id']:s for s in raw['policy_plan']['sheets']}
        self.assertTrue(sheets['recipe_data_pipeline']['mandatory'])
        self.assertEqual(sheets['recipe_data_pipeline']['title'],'Organization requirement')
        self.assertEqual(sheets['recipe_data_pipeline_1']['source_recipe'],'data-pipeline')

    def test_assignments_cannot_bypass_phase_gates(self):
        with self.assertRaisesRegex(ValueError,'current guided phase'):
            projects.execute_step(self.work,'workspace','Build later work','catalog',lambda *a: self.fail('worker must not start'))

    def test_definition_is_pinned_and_not_replaced_by_a_catalog_update(self):
        original=journeys.view(self.work)['definition']
        with patch.object(journeys,'definition',side_effect=AssertionError('Must use pinned workflow')):
            self.assertEqual(journeys.view(self.work)['definition'],original)


if __name__=='__main__':unittest.main()
