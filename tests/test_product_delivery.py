"""Source-only products, bounded OOXML checks and truthful delivery state."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from righaven import projects
from righaven.deliveries import build_delivery
from righaven.handoff import blocking_checks, product_files
from righaven.source_packages import OFFICE_PARTS, inspect_office


class ProductDeliveryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def document(self, suffix='.docx', missing=False):
        path = self.root / ('result'+suffix)
        main, mime = OFFICE_PARTS[suffix]
        with ZipFile(path, 'w') as archive:
            archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/'+main+'" ContentType="'+mime+'"/></Types>')
            archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="'+main+'"/></Relationships>')
            vocabulary,tag={'.docx':('wordprocessingml','document'),'.xlsx':('spreadsheetml','workbook'),'.pptx':('presentationml','presentation')}[suffix]
            archive.writestr(main, '<'+tag+' xmlns="http://schemas.openxmlformats.org/'+vocabulary+'/2006/main">Example requested text</'+tag+'>')
            if missing:
                folder = main.rsplit('/',1)[0]
                archive.writestr(folder+'/_rels/'+main.rsplit('/',1)[1]+'.rels', '<Relationships><Relationship Target="media/missing.png"/></Relationships>')
        return path

    def handoff(self, path):
        return {'task':'Create the requested document', 'checks':[],
            'delivery':{'source_status':'included', 'source_note':'The native document is the editable product.',
                'files':[{'path':str(path), 'role':'editable_source', 'primary':True,
                    'reopen':{'status':'not_run','evidence':'GUI not available'}, 'limitations':['Visual layout not inspected.']}]}}

    def test_native_document_can_be_product_without_duplicate_export(self):
        source = {'path':'document.docx','role':'editable_source'}
        report = {'path':'review.json','role':'report'}
        self.assertEqual(product_files([report,source]),[source])
        self.assertEqual(product_files([source,{**source,'path':'other.docx'}]),[])
        self.assertEqual(product_files([source,{**report,'primary':True}]),[source])
        self.assertEqual(product_files([{**source,'primary':False}]),[])
        explicit = {**source,'primary':True}
        self.assertEqual(product_files([{'path':'other.pdf','role':'export'},explicit]),[explicit])

    def test_office_structural_verification_is_not_a_gui_claim(self):
        for suffix in OFFICE_PARTS:
            result = inspect_office(self.document(suffix))
            self.assertEqual(result['status'],'passed')
            self.assertFalse(result['native_application_reopened'])
            self.assertFalse(result['visual_inspection'])
        path = self.document()
        delivery = build_delivery(self.handoff(path),self.root,native=False,purpose='delivery')
        self.assertEqual(delivery['technical_status'],'passed')
        self.assertEqual(delivery['files'][0]['reopen']['status'],'not_run')
        self.assertTrue(delivery['files'][0]['limitations'])

    def test_missing_linked_assets_and_failed_reopening_still_block(self):
        path = self.document(missing=True)
        self.assertEqual(build_delivery(self.handoff(path),self.root,native=False)['technical_status'],'needs_revision')
        path = self.document()
        handoff = self.handoff(path)
        handoff['delivery']['files'][0]['reopen']['status']='failed'
        self.assertEqual(build_delivery(handoff,self.root,native=False)['technical_status'],'needs_revision')

    def test_environment_probe_is_kept_separate_from_failed_product_checks(self):
        probe = {'name':'Optional library','status':'failed','scope':'environment','evidence':'Not installed; verified CLI fallback used.'}
        failure = {'name':'Required contents','status':'failed','evidence':'Missing text'}
        self.assertEqual(list(blocking_checks([probe,failure])),[failure])
        handoff = self.handoff(self.document());handoff['checks']=[probe]
        delivery=build_delivery(handoff,self.root,native=False)
        self.assertEqual(delivery['technical_status'],'passed')
        self.assertEqual(delivery['environment_checks'],[probe])
        handoff['checks'].append(failure)
        self.assertEqual(build_delivery(handoff,self.root,native=False)['technical_status'],'needs_revision')

    def test_source_only_delivery_selected_and_completed_only_after_matching_review(self):
        projects.create_plan(self.root,'Create document',[])
        acceptance=projects.sync_acceptance(self.root,['Create the requested document'])
        path = self.document(); handoff = self.handoff(path)
        handoff.update(output_files=[str(path)],source_files=[],previews=[])
        delivery=build_delivery(handoff,self.root,native=False,purpose='delivery')
        response={'ok':True,'output_dir':str(self.root),'handoff':handoff,'delivery_record':delivery}
        def invoke(task,started): return json.dumps(response)
        projects.execute_step(self.root,'workspace','Produce document','production',invoke,purpose='delivery')
        value=projects.read_project(self.root)
        self.assertTrue(value['product_path'].endswith('result.docx'))
        self.assertFalse(projects.reconcile_completion(self.root))
        reviewfile=self.root/'review.json';reviewfile.write_text('{}')
        review={'contract_hash':projects.read_project(self.root)['acceptance']['hash'],'status':'passed','product_path':str(path),'sha256':projects.digest(path),'criteria':[{'status':'passed','method':'structural'}]}
        response={'ok':True,'handoff':{'output_files':[str(reviewfile)],'source_files':[str(path)],'checks':[]},'quality_review':review}
        projects.execute_step(self.root,'workspace','Independent review','review',invoke,purpose='review')
        self.assertEqual(projects.read_project(self.root)['status'],'ready')
        path.write_text('changed after review')
        with self.assertRaises(ValueError):projects.create_plan(self.root,'',[],status='ready')
