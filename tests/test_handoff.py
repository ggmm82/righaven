import json
import tempfile
import unittest
from pathlib import Path

from righaven.handoff import validate_handoff


class HandoffFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp.name)
        self.output = self.workspace / 'outputs' / 'run'
        self.output.mkdir(parents=True)
        self.source = self.workspace / 'input.txt'
        self.source.write_text('input')
        self.file = self.output / 'report.txt'
        self.file.write_text('report')
        self.value = {'task': 'Analisi', 'source_files': [str(self.source)],
                      'output_files': [str(self.file)], 'previews': [],
                      'checks': [{'name': 'Contenuto', 'status': 'passed', 'evidence': 'Riletto report.txt'}],
                      'warnings': []}

    def tearDown(self):
        self.temp.cleanup()

    def validate(self):
        (self.output / 'handoff.json').write_text(json.dumps(self.value))
        return validate_handoff(self.output, self.workspace)


class HandoffTests(HandoffFixture):
    def test_identical_copies_in_one_delivery_are_reported_once(self):
        (self.output / 'assets').mkdir()
        for name in ('tavola.svg', 'assets/tavola.svg'):
            (self.output / name).write_text('<svg/>')
        (self.output / 'assets/altra.svg').write_text('<svg id="b"/>')
        self.value['output_files'] += [str(self.output / n) for n in ('tavola.svg', 'assets/tavola.svg', 'assets/altra.svg')]
        value = self.validate()
        self.assertEqual(value['duplicate_outputs'], [['assets/tavola.svg', 'tavola.svg']])
        self.assertEqual(sum('File identici' in w for w in value['warnings']), 1)
        self.assertIn('assets/tavola.svg = tavola.svg', value['warnings'][-1])
        (self.output / 'handoff.json').write_text(json.dumps(value))
        self.assertEqual(sum('File identici' in w for w in validate_handoff(self.output, self.workspace)['warnings']), 1)

    def test_distinct_outputs_raise_no_duplicate_warning(self):
        self.assertNotIn('duplicate_outputs', self.validate())

    def test_valid_report_preserves_quality_failures(self):
        self.value['checks'][0]['status'] = 'failed'
        self.assertEqual(self.validate()['checks'][0]['status'], 'failed')

    def test_bookkeeping_reports_are_retained_outside_the_downloads_without_weakening_source_checks(self):
        work=self.output/'work';work.mkdir();technical=work/'method.json';technical.write_text('{}')
        def metadata(path,role):
            return {'path':str(path),'role':role,'format':'JSON','open_with':'Text editor','editability':'Text',
                    'reopen':{'status':'passed','evidence':'Parsed JSON'},'limitations':[]}
        self.value['output_files'].append(str(technical))
        self.value['delivery']={'source_status':'not_applicable','source_note':'Review report',
                               'files':[metadata(self.file,'report'),metadata(technical,'report')]}
        self.value['checks'][0]['status']='failed'
        result=self.validate()
        self.assertEqual(result['output_files'],[str(self.file)])
        self.assertEqual(result['checks'][0]['status'],'failed')
        self.assertTrue(technical.exists())
        self.assertIn(str(technical),json.loads((self.output/'handoff.json').read_text())['output_files'])
        self.value['delivery']['files'][1]['role']='editable_source'
        with self.assertRaisesRegex(ValueError,'file tecnici'):self.validate()

    def test_missing_or_empty_output_is_rejected(self):
        self.file.unlink()
        with self.assertRaisesRegex(ValueError, 'mancante o vuoto'):
            self.validate()
        self.file.touch()
        with self.assertRaisesRegex(ValueError, 'mancante o vuoto'):
            self.validate()

    def test_empty_input_is_allowed(self):
        self.source.write_text('')
        self.assertEqual(self.validate()['source_files'], [str(self.source)])

    def test_output_cannot_be_an_input_or_escape_via_symlink(self):
        for filename in (str(self.source), 'report.txt'):
            self.value['output_files'] = [filename]
            with self.assertRaisesRegex(ValueError, 'percorso esterno'):
                self.validate()
        self.file.unlink()
        self.file.symlink_to(self.source)
        self.value['output_files'] = [str(self.file)]
        with self.assertRaisesRegex(ValueError, 'percorso esterno'):
            self.validate()

    def test_checks_require_status_and_evidence(self):
        for value in ([], ['ok'], [{'name': 'Contenuto', 'status': 'passed'}]):
            self.value['checks'] = value
            with self.assertRaises(ValueError):
                self.validate()

    def test_manifest_cannot_be_external_symlink(self):
        external = self.workspace / 'manifest.json'
        external.write_text(json.dumps(self.value))
        (self.output / 'handoff.json').symlink_to(external)
        with self.assertRaisesRegex(ValueError, 'esterno'):
            validate_handoff(self.output, self.workspace)


class DeliveryTests(HandoffFixture):
    def test_same_sandbox_cli_preflight_uses_the_provider_schema_and_never_approves_quality(self):
        import subprocess
        import sys
        from righaven import handoff
        from righaven.deepseek import HANDOFF_TOOL
        self.assertEqual(HANDOFF_TOOL['function']['parameters'],handoff.HANDOFF_SCHEMA)
        self.delivery()
        self.value['checks'][0]['status']='failed'
        self.validate()
        command=[sys.executable,handoff.__file__,'validate',str(self.output),'--workspace',str(self.workspace)]
        result=subprocess.run(command,capture_output=True,text=True,check=True)
        response=json.loads(result.stdout)
        self.assertTrue(response['ok'])
        self.assertFalse(response['product_approved'])
        self.assertEqual(response['failed_checks'],['Contenuto'])
        self.value['delivery']['files'][0]['limitations']=[]
        self.value['delivery']['files'][0]['reopen']['status']='not_run'
        (self.output/'handoff.json').write_text(json.dumps(self.value))
        original=(self.output/'handoff.json').read_bytes()
        failed=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(failed.returncode,1)
        self.assertIn('limite esplicito',json.loads(failed.stdout)['error'])
        self.assertEqual((self.output/'handoff.json').read_bytes(),original)

    def metadata(self, path=None, role='editable_source'):
        return {'path': str(path or self.file), 'role': role, 'format': 'DXF',
                'open_with': 'CADCraft', 'editability': 'Polilinee e layer',
                'reopen': {'status': 'passed', 'evidence': 'cadcraft-cli run: riaperto e modificato'},
                'limitations': []}

    def delivery(self, files=None, status='included'):
        self.value['delivery'] = {'source_status': status, 'source_note': 'Sorgente del risultato',
                                  'files': files if files is not None else [self.metadata()]}

    def test_valid_zip_without_required_native_project_does_not_claim_verified_sources(self):
        import zipfile
        from righaven.deliveries import build_delivery
        archive=self.output/'sources.zip'
        with zipfile.ZipFile(archive,'w') as z:z.writestr('README.txt','Instructions only')
        self.value['output_files']=[str(archive)]
        self.delivery([self.metadata(archive,role='source_archive')])
        result=build_delivery(self.validate(),self.output,purpose='delivery',native=False,agent='filmcraft')
        self.assertEqual(result['technical_status'],'needs_revision')
        self.assertEqual(result['source_package_status'],'incomplete')

    def test_report_only_final_does_not_require_artificial_editable_components(self):
        from righaven.deliveries import build_delivery
        self.delivery([self.metadata(role='report')], status='not_applicable')
        result=build_delivery(self.validate(),self.output,purpose='delivery',require_components=True)
        self.assertEqual(result['technical_status'],'passed')
        self.assertEqual(result['source_coverage']['issues'],[])
        self.assertEqual(result['source_package_status'],'not_applicable')

    def test_unverified_sound_is_not_a_false_failure_or_a_passed_timing_check(self):
        from righaven.deliveries import build_delivery
        from unittest.mock import patch
        self.delivery()
        with patch('righaven.timing.check_timing',return_value={'status':'not_run','cues':[],
                'issues':['Continuous audio needs a relevant review']}):
            result=build_delivery(self.validate(),self.output,require_timing=True)
        self.assertEqual(result['technical_status'],'passed')
        self.assertEqual(result['timing']['status'],'not_run')
        self.assertEqual(result['quality_status'],'not_reviewed')
        with patch('righaven.timing.check_timing',return_value={'status':'failed','cues':[],
                'issues':['Observed transient is delayed']}):
            result=build_delivery(self.validate(),self.output,require_timing=True)
        self.assertEqual(result['technical_status'],'needs_revision')
        self.assertIn('Observed transient is delayed',result['issues'])

    def test_new_worker_requires_metadata_but_legacy_reading_still_works(self):
        self.validate()
        with self.assertRaisesRegex(ValueError, 'delivery'):
            validate_handoff(self.output, self.workspace, require_delivery=True)
        self.delivery()
        self.assertEqual(self.validate()['delivery']['source_status'], 'included')

    def test_glb_export_and_input_dxf_do_not_count_as_delivered_source(self):
        glb = self.output / 'robot.glb'
        glb.write_bytes(b'glTF export fixture')
        self.value['output_files'] = [str(glb)]
        self.value['source_files'] = [str(self.source)]
        export = self.metadata(glb, role='export')
        export.update(format='GLB', open_with='GLB viewer', editability='Mesh di scambio; compatibilità CADCraft non verificata')
        self.delivery([export])
        with self.assertRaisesRegex(ValueError, 'sorgenti consegnati'):
            self.validate()
        # A source actually delivered, separately from its export, satisfies the contract.
        self.value['output_files'].append(str(self.file))
        self.value['delivery']['files'].append(self.metadata())
        self.assertEqual(len(self.validate()['delivery']['files']), 2)

    def test_sources_must_be_downloadable_not_only_inputs_or_previews(self):
        self.delivery([self.metadata(self.source)])
        with self.assertRaisesRegex(ValueError, 'già elencato'):
            self.validate()
        self.value['previews'] = [str(self.file)]
        self.value['output_files'] = [str(self.output / 'final.pdf')]
        (self.output / 'final.pdf').write_bytes(b'export')
        self.delivery([self.metadata(), self.metadata(self.output / 'final.pdf', 'export')])
        with self.assertRaisesRegex(ValueError, 'scaricabile'):
            self.validate()

    def test_every_output_requires_unique_metadata_and_opening_instructions(self):
        self.delivery()
        self.value['delivery']['files'] *= 2
        with self.assertRaisesRegex(ValueError, 'unico'):
            self.validate()
        self.delivery([self.metadata(role='export')])
        other = self.output / 'native.dxf'
        other.write_text('native fixture')
        self.value['output_files'].append(str(other))
        with self.assertRaisesRegex(ValueError, 'mancano metadati'):
            self.validate()
        self.value['output_files'].pop()
        self.delivery()
        self.value['delivery']['files'][0]['open_with'] = ' '
        with self.assertRaisesRegex(ValueError, 'open_with'):
            self.validate()

    def test_missing_sources_are_explicit_partial_delivery_not_silent_success(self):
        self.delivery([self.metadata(role='export')], status='unavailable')
        with self.assertRaisesRegex(ValueError, 'warnings'):
            self.validate()
        self.value['warnings'] = ['Sorgente equivalente non disponibile: consegna parziale']
        self.assertEqual(self.validate()['delivery']['source_status'], 'unavailable')
        self.value['delivery']['source_status'] = 'not_applicable'
        with self.assertRaisesRegex(ValueError, 'prodotto esportato'):
            self.validate()

    def test_auxiliary_not_run_is_explicit_without_discarding_work_or_faking_success(self):
        self.delivery([self.metadata(role='report')], status='not_applicable')
        self.value['delivery']['files'][0]['reopen'] = {'status':'not_run','evidence':'File ausiliario; nessuna riapertura eseguita'}
        result = self.validate()
        self.assertEqual(result['delivery']['files'][0]['reopen']['status'],'not_run')
        self.assertIn('Riapertura non eseguita',result['delivery']['files'][0]['limitations'][0])
        self.assertTrue(result['warnings'])
        self.value['delivery']['files'][0]['reopen']['status'] = 'failed'
        with self.assertRaisesRegex(ValueError,'limite esplicito'): self.validate()
        self.delivery()
        self.value['delivery']['files'][0]['reopen'] = {'status':'not_run','evidence':'Sorgente non riaperto'}
        with self.assertRaisesRegex(ValueError,'limite esplicito'): self.validate()

    def test_unverified_source_keeps_failure_and_requires_limit_and_warning(self):
        self.delivery()
        item = self.value['delivery']['files'][0]
        item['reopen'] = {'status': 'failed', 'evidence': 'Importazione fallita nella release installata'}
        with self.assertRaisesRegex(ValueError, 'limite esplicito'):
            self.validate()
        item['limitations'] = ['Apribilità non confermata; non presentare come compatibile']
        with self.assertRaisesRegex(ValueError, 'warnings'):
            self.validate()
        self.value['warnings'] = ['Riapertura fallita: revisione necessaria']
        self.assertEqual(self.validate()['delivery']['files'][0]['reopen']['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
