"""Published files remain visible without changing approval or acceptance."""
import copy,json,tempfile,unittest
from pathlib import Path
from righaven.presentation import presentation
from righaven import projects
from righaven.project_controls import RESUME_INSTRUCTIONS
from righaven.environment_changes import difference,reason


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        output=self.root/'outputs/job';output.mkdir(parents=True)
        self.product=output/'result.pdf';self.product.write_bytes(b'published document fixture')
        self.sources=output/'sources.zip';self.sources.write_bytes(b'published source package fixture')
        self.paths=['/mnt/user-data/outputs/job/result.pdf','/mnt/user-data/outputs/job/sources.zip']
        files=[{'path':p,'role':role,'sha256':projects.digest(actual)} for p,role,actual in zip(self.paths,['export','source_archive'],[self.product,self.sources])]
        self.project={'id':'fixture','status':'review','product_path':self.paths[0],
          'results':[{**f,'delivery_id':'job'} for f in files],'deliveries':[{'id':'job','files':files}]}

    def test_exact_published_product_and_its_sources_are_selected_once(self):
        before=copy.deepcopy(self.project);plan=presentation(self.root,self.project,{})
        self.assertEqual(plan['paths'],self.paths);self.assertEqual(self.project,before)
        self.assertIsNone(presentation(self.root,self.project,{'harness_presentation_signature':plan['signature']}))
        existing=presentation(self.root,self.project,{'artifacts':self.paths})
        self.assertEqual(existing['paths'],[])

    def test_missing_changed_and_external_files_are_never_presented_as_verified(self):
        self.product.write_bytes(b'changed after verification')
        self.assertNotIn(self.paths[0],presentation(self.root,self.project,{})['paths'])
        self.sources.unlink();self.assertIsNone(presentation(self.root,self.project,{}))
        self.project['product_path']='/etc/passwd';self.assertIsNone(presentation(self.root,self.project,{}))

    def test_resume_does_not_invalidate_review_but_real_revision_does(self):
        projects.create_plan(self.root,'A report',[])
        projects.sync_acceptance(self.root,['Create a report','Deliver PDF and editable sources'])
        initial=projects.read_project(self.root)['acceptance']['hash']
        resume=next(iter(RESUME_INSTRUCTIONS))
        projects.sync_acceptance(self.root,['Create a report','Deliver PDF and editable sources',resume])
        self.assertEqual(projects.read_project(self.root)['acceptance']['hash'],initial)
        projects.sync_acceptance(self.root,['Resume the report and add a new chapter'])
        self.assertNotEqual(projects.read_project(self.root)['acceptance']['hash'],initial)

    def test_operational_resume_repairs_old_polluted_manifest(self):
        from righaven.project_skills import save_requests,compact_acceptance
        from righaven.acceptance import contract,fingerprint
        from righaven.state import atomic_json
        projects.create_plan(self.root,'Report',[]);projects.sync_acceptance(self.root,['Report'])
        original=projects.read_project(self.root)['acceptance']['hash']
        file=self.root/'.righaven-project/project.json';value=json.loads(file.read_text())
        docs,manifest=save_requests(self.root,['Report',next(iter(RESUME_INSTRUCTIONS))])
        value['acceptance']={**compact_acceptance(contract(['Report',next(iter(RESUME_INSTRUCTIONS))])),
          'request_documents':docs,'request_manifest':manifest,'request_count':2}
        atomic_json(file,value)
        projects.sync_acceptance(self.root,[next(iter(RESUME_INSTRUCTIONS))])
        repaired=projects.read_project(self.root)['acceptance']
        self.assertEqual(repaired['hash'],original);self.assertEqual(repaired['request_count'],1)

    def test_completed_board_updates_are_idempotent_but_cannot_invent_execution(self):
        step={'id':'write','agent':'wordcraft','goal':'Write report'}
        projects.create_plan(self.root,'Report',[step])
        with self.assertRaises(ValueError):projects.create_plan(self.root,'',[{**step,'status':'completed'}])
        projects.execute_step(self.root,'wordcraft','Write report','write',lambda *a:json.dumps({'ok':True,'handoff':{'checks':[],'output_files':[]}}))
        projects.create_plan(self.root,'',[{**step,'status':'completed'}])
        self.assertEqual(len(json.loads((self.root/'.righaven-project/project.json').read_text())['steps'][0]['attempts']),1)
        with self.assertRaises(ValueError):projects.create_plan(self.root,'',[{**step,'goal':'Different unexecuted task','status':'completed'}])

    def test_preparation_reasons_distinguish_version_base_and_missing_image(self):
        prior={'core':'old','tools':['d2'],'versions':{}}
        self.assertEqual(difference(prior,{'core':'new','tools':['d2'],'versions':{}})['code'],'base_changed')
        spec={**prior,'versions':{'d2':'new'}}
        self.assertEqual(difference(prior,spec)['tools'],['d2'])
        self.assertEqual(difference(prior,{**prior,'versions':{'provider-agy':'new'}})['code'],'image_missing')
        self.assertEqual(difference(prior,prior)['code'],'image_missing')
        self.assertIn('provider-agy',reason('version_change','provider-agy')['message'])
