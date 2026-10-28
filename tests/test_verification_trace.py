"""Production regressions: comparable samples, immutable proofs and useful traces."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from righaven import source_packages, verification_cache, projects
from righaven.audit_log import page
from righaven.deliveries import build_delivery
from righaven.progress import Reporter, read_status, public_status
from righaven.sandbox_lessons import technical_validation
from righaven.completion_policy import needs_continuation


class VerificationTraceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_normalized_observations_accept_equivalent_encodings_and_reject_real_changes(self):
        video, image, other = [self.root / n for n in ('master.mp4','quarter.png','different.png')]
        def run(*args): subprocess.run(['ffmpeg','-v','error','-y',*map(str,args)],check=True,capture_output=True)
        run('-f','lavfi','-i','color=c=0x8dccff:s=1280x720:r=1','-frames:v',1,
            '-c:v','libx264','-colorspace','bt709','-color_trc','bt709','-color_primaries','bt709',video)
        run('-i',video,'-frames:v',1,'-vf','scale=320:180',image)
        run('-f','lavfi','-i','color=c=red:s=320x180','-frames:v',1,other)
        def error(a,b): return sum(abs(x-y) for x,y in zip(a,b))/len(a)
        master=source_packages.sample(video)
        self.assertEqual(len(master),432)
        self.assertLess(error(master,source_packages.sample(image)),3)
        self.assertGreater(error(master,source_packages.sample(other)),12)

    def test_gateway_proofs_are_thread_runtime_and_content_scoped(self):
        archive=self.root/'outputs/source.zip';archive.parent.mkdir()
        with zipfile.ZipFile(archive,'w') as z:z.writestr('source.txt','A real fixture')
        sha=source_packages.digest(archive)
        proof={'status':'passed','sha256':sha,'files':1,'checks':[]}
        result={'delivery_record':{'files':[{'path':str(archive),'role':'source_archive','verification':proof}]}}
        private=self.root/'gateway-private'
        verification_cache.save(private,self.root,'runtime-v1',result)
        proofs=verification_cache.load(private,self.root,'runtime-v1')
        self.assertIn(sha,proofs)
        self.assertEqual(verification_cache.load(private,self.root/'other-thread','runtime-v1'),{})
        self.assertEqual(verification_cache.load(private,self.root,'runtime-v2'),{})
        real_digest = source_packages.digest
        with patch('righaven.verification_cache.digest', side_effect=lambda p: 'new-tool-versions' if Path(p).name == 'versions.lock.json' else real_digest(p)):
            self.assertEqual(verification_cache.load(private,self.root,'runtime-v1'),{})
        handoff={'task':'Fixture','checks':[],'delivery':{'source_status':'included','source_note':'Fixture source',
            'files':[{'path':str(archive),'role':'source_archive','reopen':{'status':'passed'},'limitations':[]}]}}
        with patch('righaven.deliveries.verify_archive',return_value=proof) as native:
            record=build_delivery(handoff,archive.parent,verified_archives=proofs)
            native.assert_not_called()
            self.assertTrue(record['files'][0]['verification']['reused'])
            archive.write_bytes(b'changed')
            build_delivery(handoff,archive.parent,verified_archives=proofs)
            native.assert_called_once()

    def test_review_follows_identical_product_and_sources_but_never_changed_sources(self):
        folder=self.root/'outputs';folder.mkdir()
        original,copy,source,sourcecopy=[folder/n for n in ('old.txt','new.txt','source.txt','copied-source.txt')]
        original.write_text('Product');copy.write_bytes(original.read_bytes())
        source.write_text('Source');sourcecopy.write_bytes(source.read_bytes())
        sha=source_packages.digest(source)
        value={'acceptance':{'hash':'contract'},'steps':[{'attempts':[{'output_files':[str(copy)],
            'delivery_record':{'files':[{'path':str(sourcecopy),'role':'editable_source','sha256':sha}]}}]}]}
        review={'product_path':str(original),'sha256':source_packages.digest(original),'contract_hash':'contract',
            'input_hashes':{str(original):source_packages.digest(original),str(source):sha}}
        self.assertTrue(projects.review_matches(value,review,str(copy),self.root))
        sourcecopy.write_text('Different source')
        self.assertFalse(projects.review_matches(value,review,str(copy),self.root))
        sourcecopy.write_bytes(source.read_bytes());value['acceptance']['hash']='changed-contract'
        self.assertFalse(projects.review_matches(value,review,str(copy),self.root))

    def test_command_details_survive_journal_and_prove_tests_without_exposing_payloads(self):
        job={'agent':'workspace','engine':'codex','model':'fixture','run_id':'rh-job-123456abcdef'}
        out=self.root/'outputs/workspace'/job['run_id'];out.mkdir(parents=True)
        reporter=Reporter(out,job)
        reporter.cli_event('codex',{'type':'item.started','item':{'id':'one','type':'command_execution',
            'command':'python3 /opt/righaven-worker/source_packages.py verify /mnt/user-data/outputs/sources.zip --api-key sk-private-key-value'}})
        (out/'result.txt').write_text('Observed output')
        reporter.cli_event('codex',{'type':'item.completed','item':{'id':'one','type':'command_execution',
            'exit_code':1,'duration_ms':1200,'output':'FileNotFoundError: sk-private-key-value PRIVATE PROMPT'}})
        event=public_status(read_status(reporter.path))['events'][-1]
        self.assertEqual(event['context']['duration_seconds'],1.2)
        self.assertEqual(event['context']['exit_code'],1)
        self.assertEqual(event['context']['changed_files'],['result.txt'])
        self.assertIn('non trovato',event['context']['diagnostic'])
        rows=page(self.root)['events']
        self.assertEqual(rows[-1]['status'],'failed')
        self.assertEqual(rows[-1]['context']['tool'],'python3')
        self.assertNotIn('PRIVATE',json.dumps(rows))
        self.assertNotIn('sk-private',json.dumps(rows))
        reporter.cli_event('codex',{'type':'item.started','item':{'id':'two','type':'command_execution','command':'python3 work/check.py'}})
        reporter.cli_event('codex',{'type':'item.completed','item':{'id':'two','type':'command_execution','exit_code':0}})
        identifier=read_status(reporter.path)['events'][-1]['context']['id']
        operation=out/'work/commands'/identifier/'status.json';result=out/'work/check.json';result.write_text('{"reopened":true}')
        validation=technical_validation(self.root,out,{'validation':{'operation_path':str(operation),'result_path':str(result),
            'assertions':[{'pointer':'/reopened','equals':True}]}},lambda root,path:Path(path) if Path(path).is_file() else None)
        self.assertEqual(validation['status'],'passed')

    def test_copy_keeps_independent_review_and_does_not_restart_for_unavailable_listening(self):
        projects.create_plan(self.root,'Deliver result',[])
        projects.sync_acceptance(self.root,['Deliver result'])
        contract=projects.read_project(self.root)['acceptance']['hash']
        folders=[self.root/'outputs'/name for name in ('old','new')]
        for folder in folders:
            folder.mkdir(parents=True)
            (folder/'product.txt').write_text('Identical product')
            (folder/'source.txt').write_text('Identical source')
        def produced(folder):
            return {'ok':True,'output_dir':str(folder),'handoff':{'output_files':[str(folder/'product.txt'),str(folder/'source.txt')],'checks':[]},
                'delivery_record':{'id':folder.name,'technical_status':'passed','files':[
                    {'path':str(folder/name),'role':role,'sha256':source_packages.digest(folder/name)}
                    for name,role in [('product.txt','export'),('source.txt','editable_source')]]}}
        projects.execute_step(self.root,'workspace','Produce','old',lambda *a:json.dumps(produced(folders[0])),purpose='delivery')
        review={'product_path':str(folders[0]/'product.txt'),'sha256':source_packages.digest(folders[0]/'product.txt'),
            'contract_hash':contract,'status':'needs_review','unavailable_methods':['listening'],
            'criteria':[{'requirement_id':'request_fidelity','status':'passed','method':'content'},
                        {'requirement_id':'sound','status':'not_run','method':'listening'}],
            'input_hashes':{str(p):source_packages.digest(p) for p in folders[0].iterdir()}}
        projects.execute_step(self.root,'workspace','Review','review',lambda *a:json.dumps({
            'ok':True,'quality_review':review,'handoff':{'output_files':[],'checks':[]}}),purpose='review')
        projects.execute_step(self.root,'workspace','Copy metadata','new',lambda *a:json.dumps(produced(folders[1])),purpose='delivery')
        state=projects.read_project(self.root)
        self.assertEqual(state['quality_status'],'needs_review')
        self.assertFalse(needs_continuation(state))
        (folders[1]/'source.txt').write_text('Changed source')
        self.assertTrue(needs_continuation(projects.read_project(self.root)))
