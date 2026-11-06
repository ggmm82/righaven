"""Regressions from successive deliveries; no fabricated application success."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from righaven import handoff, projects
from righaven.acceptance import evaluate
from righaven.deliveries import build_delivery
from righaven.source_packages import digest
from righaven.control_memory import delegate_view, project_view


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'outputs/run'; self.out.mkdir(parents=True)
        self.product = self.out / 'result.txt'; self.product.write_text('The same usable product')
        self.recipe = self.out / 'recipe.py'; self.recipe.write_text('# source, never executed by preflight')
        def metadata(path, role):
            return {'path':str(path),'role':role,'format':path.suffix,'open_with':'Text editor',
                'editability':'Editable text','reopen':{'status':'passed','evidence':'Read back fixture'},'limitations':[]}
        self.value = {'task':'Generic delivery','source_files':[],'output_files':[str(self.product),str(self.recipe)],
            'previews':[],'checks':[{'name':'Current check','status':'passed','evidence':'Actual current observation'}],
            'warnings':[], 'delivery':{'source_status':'included','source_note':'Source supplied',
            'files':[metadata(self.product,'export'),metadata(self.recipe,'editable_source')],
            'components':[{'name':'Product','tool':'python3','artifacts':[{'path':str(self.product)}],
                           'sources':[{'path':str(self.recipe)}]}]}}

    def validate(self):
        (self.out/'handoff.json').write_text(json.dumps(self.value))
        return handoff.validate_handoff(self.out,self.root,require_delivery=True)

    def test_cli_catches_late_component_error_and_repairs_metadata_on_same_files(self):
        self.value['delivery']['components'][0]['tool']='Long explanation of authoring, checking, provenance and version '*2
        (self.out/'handoff.json').write_text(json.dumps(self.value))
        before = digest(self.product), digest(self.recipe)
        command=[sys.executable,handoff.__file__,'validate',str(self.out),'--workspace',str(self.root)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,1)
        self.assertIn('components[0].tool',json.loads(result.stdout)['error'])
        self.assertIn('48',json.loads(result.stdout)['error'])
        self.value['delivery']['components'][0]['tool']='python3'
        self.validate()
        result=subprocess.run(command,capture_output=True,text=True,check=True)
        self.assertTrue(json.loads(result.stdout)['ok'])
        self.assertFalse(json.loads(result.stdout)['product_approved'])
        self.assertEqual((digest(self.product),digest(self.recipe)),before)

    def test_empty_learning_manifest_does_not_claim_a_recorded_lesson(self):
        from righaven.run_agent import learning_status
        work=self.out/'work';work.mkdir()
        manifest=work/'tool-lessons.json'
        self.assertEqual(learning_status(self.out),'not_recorded')
        for value in ([],{'lessons':[]}):
            manifest.write_text(json.dumps(value))
            self.assertEqual(learning_status(self.out),'no_findings')
        manifest.write_text('{broken')
        self.assertEqual(learning_status(self.out),'invalid')
        manifest.write_text(json.dumps({'lessons':[{'lesson':{'title':'Reported, still to validate'}}]}))
        self.assertEqual(learning_status(self.out),'recorded')

    def test_zip_inventory_preflight_catches_missing_member_before_worker_closes(self):
        archive=self.recipe.with_suffix('.zip')
        with zipfile.ZipFile(archive,'w') as z:z.write(self.recipe,'recipe.py')
        self.value['output_files'][1]=str(archive)
        self.value['delivery']['files'][1].update(path=str(archive),role='source_archive')
        ref=self.value['delivery']['components'][0]['sources'][0]
        ref.update(path=str(archive),member='missing.py')
        with self.assertRaisesRegex(ValueError,'file non presente'):self.validate()
        ref['member']='recipe.py'
        self.assertEqual(self.validate()['output_files'][1],str(archive))
        with zipfile.ZipFile(archive,'a') as z:z.writestr('../escape','never extracted')
        with self.assertRaisesRegex(ValueError,'non sicuro'):self.validate()
        archive.write_bytes(b'not a ZIP container')
        with self.assertRaisesRegex(ValueError,'archivio.*non leggibile'):self.validate()

    def test_superseded_failure_keeps_evidence_without_blocking_current_product(self):
        previous={'name':'Historical checker','status':'failed','evidence':'Original crash exit 139',
                  'scope':'historical','superseded_by':'Current check'}
        self.value['checks'].insert(0,previous)
        validated=self.validate()
        self.assertEqual(validated['checks'][0]['status'],'failed')
        self.assertEqual(list(handoff.blocking_checks(validated['checks'])),[])
        delivery=build_delivery(validated,self.out,native=False)
        self.assertEqual(delivery['technical_status'],'passed')
        self.assertEqual(delivery['historical_checks'],[previous])
        control=delegate_view({'ok':True,'checks':validated['checks'],'delivery':delivery})
        self.assertNotEqual(control['decision'],'needs_revision')
        self.assertIsNone(control['continuation'])
        self.assertEqual(control['check_counts']['failed'],1)
        self.assertEqual(control['blocking_failed_checks'],0)
        # The coordinator's short reply may omit the successful successor.
        excerpt={'ok':True,'checks':[previous],'check_counts':{'failed':1,'passed':20},
                 'blocking_failed_checks':0,'delivery':delivery}
        self.assertNotEqual(delegate_view(excerpt)['decision'],'needs_revision')
        self.assertIsNone(delegate_view(excerpt)['continuation'])
        excerpt.pop('blocking_failed_checks')
        self.assertEqual(delegate_view(excerpt)['decision'],'needs_revision')
        self.assertIn('exit 139',projects.delivery_summary(delivery)['historical_checks'][0]['evidence'])
        self.value['checks'].append({'name':'Unresolved defect','status':'failed','evidence':'Observed current defect'})
        delivery=build_delivery(self.validate(),self.out,native=False)
        self.assertEqual(delivery['technical_status'],'needs_revision')
        self.assertIn('Unresolved defect',str(delivery['issues']))

    def test_historical_label_requires_one_passed_current_successor(self):
        self.value['checks'].insert(0,{'name':'Old','status':'failed','evidence':'Original result',
                                     'scope':'historical','superseded_by':'Current check'})
        for status in ('failed','not_run'):
            self.value['checks'][1]['status']=status
            with self.assertRaisesRegex(ValueError,'success|superseded_by'):self.validate()
        self.value['checks'][1]['status']='passed'
        self.value['checks'].append(copy.deepcopy(self.value['checks'][1]))
        with self.assertRaisesRegex(ValueError,'univoco'):self.validate()

    def test_native_failure_cannot_be_retired_by_model_historical_claim(self):
        self.value['checks'].insert(0,{'name':'Old','status':'failed','evidence':'Old crash',
                                     'scope':'historical','superseded_by':'Current check'})
        self.product=self.product.rename(self.out/'book.epub')
        self.value['output_files'][0]=str(self.product)
        self.value['delivery']['files'][0]['path']=str(self.product)
        self.value['delivery']['components'][0]['artifacts'][0]['path']=str(self.product)
        with patch('righaven.deliveries.inspect_ebook',side_effect=ValueError('Actual native defect')):
            delivery=build_delivery(self.validate(),self.out)
        self.assertEqual(delivery['technical_status'],'needs_revision')
        self.assertIn('Actual native defect',str(delivery['issues']))


class SupplementaryReviewTests(unittest.TestCase):
    def setUp(self):
        self.contract={'criteria':[{'id':'links','requirement':'Requested working links','method':'functional','critical':True,'reference_paths':[]}]}
        self.required={'requirement_id':'links','criterion':'Requested links','method':'functional',
                       'status':'passed','evidence':'Every destination was tested'}
        self.extra={'scope':'supplementary','criterion':'Unrequested physical device','method':'functional',
                    'status':'not_run','evidence':'Device unavailable; limitation retained'}

    def test_unavailable_extra_does_not_cancel_observed_required_behavior(self):
        for outcome in ('not_run','failed'):
            self.extra['status']=outcome
            criteria,status=evaluate([self.required,self.extra],self.contract,'codex')
            self.assertEqual(status,'passed')
            self.assertEqual(criteria[1]['status'],outcome)
            self.assertFalse(criteria[1]['critical'])

    def test_supplement_cannot_replace_missing_or_failed_required_test(self):
        self.assertEqual(evaluate([self.extra],self.contract,'codex')[1],'needs_review')
        required={**self.required,'status':'failed','critical':False}
        self.assertEqual(evaluate([required,self.extra],self.contract,'codex')[1],'needs_revision')
        for identifier in ('links','invented'):
            with self.assertRaisesRegex(ValueError,'requirement_id'):
                evaluate([self.required,{**self.extra,'requirement_id':identifier}],self.contract,'codex')
        with self.assertRaisesRegex(ValueError,'requirement_id'):
            evaluate([self.extra],None,'codex')

    def test_coordinator_presents_new_sample_not_previous_release_product(self):
        old={'path':'/mnt/user-data/outputs/old/book.pdf','delivery_id':'old','at':'2026-10-23T09:00:00Z'}
        sample={'path':'/mnt/user-data/outputs/new/sample.epub','delivery_id':'new','at':'2026-10-23T14:00:00Z'}
        source={'path':'/mnt/user-data/outputs/new/sources.zip','delivery_id':'new','role':'source_archive'}
        project={'id':'fixture','status':'review','product_path':old['path'],'latest_sample':sample,'results':[old,sample,source]}
        paths=project_view(project)['presentation']['paths']
        self.assertEqual(paths,[sample['path'],source['path']])
        self.assertNotIn(old['path'],paths)
        project['results'][0]['at']='2026-10-23T15:00:00Z'
        self.assertEqual(project_view(project)['presentation']['paths'],[old['path']])
