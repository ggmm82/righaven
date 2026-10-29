"""Boundaries of optional native workflows and exact-output PDF inspection."""
import json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from scripts import toolkit_cli as cli
from scripts import extended_tools as native
from scripts.acceptance_extended import pdf


class ExtendedToolTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.scope=patch.object(cli,'ROOT',self.root);self.scope.start()
        self.env=patch.dict(os.environ,{'RIGHAVEN_OUTPUT_DIR':str(self.root)});self.env.start()
    def tearDown(self):self.env.stop();self.scope.stop();self.temp.cleanup()

    def test_target_authorization_and_output_bounds_before_any_execution(self):
        for tool,action,args in [('axe-core','audit',{'url':'https://example.test'}),('zap','baseline',{'url':'https://example.test'})]:
            output=self.root/tool
            with patch.object(cli,'run') as run:
                with self.assertRaises(ValueError):cli.invoke(tool,action,{**args,'output':str(output),'authorized':False})
                run.assert_not_called();self.assertFalse(output.exists())
        for target in ['file:///etc/passwd','https://user:secret@example.test','https://example.test/#secret']:
            with self.assertRaises(ValueError):native.url(target)
        with self.assertRaises(ValueError):cli.invoke('poppler','render',{'input':'/etc/passwd','output':str(self.root/'Pages')})

    def test_resource_symlinks_and_overwriting_are_rejected(self):
        resources=self.root/'input';resources.mkdir();source=resources/'notebook.ipynb';source.write_text('{}')
        (resources/'outside').symlink_to('/etc/passwd');out=self.root/'out'
        with self.assertRaises(ValueError):cli.invoke('jupyter','execute',{'input':str(source),'output':str(out),'resource_dir':str(resources)})
        with patch.object(cli,'run') as run:
            with self.assertRaises(ValueError):cli.invoke('jupyter','execute',{'input':str(source),'output':str(out)})
            run.assert_not_called()

    def test_scanning_cannot_write_a_report_into_its_input(self):
        source=self.root/'repository';source.mkdir()
        with self.assertRaises(ValueError):cli.invoke('gitleaks','scan',{'input':str(source),'output':str(source/'report')})
        self.assertFalse((source/'report').exists())

    def test_passive_zap_plan_never_contains_an_active_scan_job(self):
        output=self.root/'passive'
        def execute(app,argv,root,**kwargs):
            spec=json.loads(Path(argv[-1]).read_text());Path(spec['stdout']).write_text('done');Path(spec['stderr']).write_text('')
            (output/'report.xml').write_text('<OWASPZAPReport/>')
            return subprocess.CompletedProcess(argv,0,'','')
        with patch.object(native,'binary',return_value='/native/zap.sh'),patch.object(cli,'run',side_effect=execute):
            cli.invoke('zap','baseline',{'url':'https://example.test/authorized','output':str(output),'authorized':True})
        plan=json.loads((output/'passive-plan.yaml').read_text())
        self.assertEqual([j['type'] for j in plan['jobs']],['spider','passiveScan-wait','report'])
        self.assertEqual(plan['env']['contexts'][0]['urls'],['https://example.test/authorized'])

    @unittest.skipUnless(shutil.which('pdftoppm') and shutil.which('pdftotext'),'Requires real Poppler')
    def test_exact_pdf_is_rendered_and_text_extracted_without_modifying_original(self):
        source=self.root/'document.pdf';pdf(source);before=source.read_bytes()
        pages=self.root/'pages';cli.invoke('poppler','render',{'input':str(source),'output':str(pages),'dpi':72})
        self.assertEqual(len(list(pages.glob('page-*.png'))),1)
        from PIL import Image
        with Image.open(next(pages.glob('page-*.png'))) as image:self.assertEqual(image.size,(300,200))
        text=self.root/'text';cli.invoke('poppler','text',{'input':str(source),'output':str(text)})
        self.assertIn('RigHaven 60',(text/'text.txt').read_text());self.assertEqual(source.read_bytes(),before)

    def test_validator_failure_and_warning_are_not_promoted_to_clean_pass(self):
        source=self.root/'document.pdf';pdf(source)
        for code,status in [(2,'failed'),(3,'uncertain')]:
            def execute(app,argv,root,**kwargs):
                spec=json.loads(Path(argv[-1]).read_text());Path(spec['stdout']).write_text('diagnostic');Path(spec['stderr']).write_text('problem')
                return subprocess.CompletedProcess(argv,code,'','')
            with patch.object(cli,'run',side_effect=execute):
                result=cli.invoke('qpdf','check',{'input':str(source),'output':str(self.root/str(code))})
            self.assertEqual(result['status'],status)

    def test_qgis_rejects_escaping_output_paths(self):
        source=self.root/'parameters.json';source.write_text(json.dumps({'OUTPUT':'../../outside.gpkg'}))
        with patch.object(cli,'run') as run:
            with self.assertRaises(ValueError):cli.invoke('qgis','process',{'input':str(source),'output':str(self.root/'out'),'algorithm':'native:buffer'})
            run.assert_not_called()
