import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from righaven import projects
from righaven.project_guide import build, markdown, bundle
from righaven.command_details import sanitized, describe, public
from righaven.progress import Reporter, read_status


class GuideTests(unittest.TestCase):
    def test_followup_brief_does_not_relabel_previous_delivery(self):
        self.production('first')
        first=build(self.root,'first')
        projects.create_plan(self.root,'An entirely new requested product',[])
        self.production('followup')
        earlier=build(self.root,'first')
        self.assertEqual(earlier['title'],first['title'])
        self.assertEqual(earlier['brief'],first['brief'])
        self.assertNotIn('entirely new',earlier['brief'])
        self.assertEqual(build(self.root)['brief'],'An entirely new requested product')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        projects.create_plan(self.root, 'Create a reusable project', [])

    def production(self, identifier, content='Product', notes=True, purpose='delivery', **metadata):
        folder = self.root / 'outputs/workspace' / identifier
        (folder / 'work').mkdir(parents=True)
        product, source, archive = [folder / name for name in ('product.txt', 'source.txt', 'sources.zip')]
        product.write_text(content); source.write_text('Editable source')
        readme = folder / 'LEGGIMI.txt'; readme.write_text('Open the source and rebuild the product. Original instructions.')
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('source.txt', source.read_bytes())
        (folder / 'work/method.json').write_text(json.dumps({'approach': 'Construct curves, then compose',
            'steps': ['Build source', 'Render result'], 'scripts': ['source.txt'], 'limits': ['Physical use not tested']}))
        if notes:
            (folder / 'work/guide.json').write_text(json.dumps({'overview': 'Start from the source',
                'use': ['Open the delivered product'], 'editing': [
                    {'goal': 'Change a value', 'files': ['source.txt'], 'steps': ['Edit the parameter', 'Rebuild'], 'check': 'Inspect the result'},
                    {'goal': 'Foreign private file', 'files': ['/mnt/user-data/.secret'], 'steps': ['Should not be published']}]}))
        files = [{'path': str(path), 'role': role, 'sha256': projects.digest(path), 'open_with': 'Text editor',
                  'editability': 'Parameters are editable', 'limitations': []}
                 for path, role in [(product, 'export'), (source, 'editable_source'), (archive, 'source_archive'), (readme, 'report')]]
        result = {'ok': True, 'output_dir': str(folder), 'handoff': {'output_files': [str(p) for p in (product, source, archive, readme)], 'checks': []},
            'delivery_record': {'id': identifier, 'title': 'Usable result', 'technical_status': 'passed', 'files': files, **metadata}}
        projects.execute_step(self.root, 'workspace', 'Build usable result', identifier, lambda *a: json.dumps(result), purpose=purpose)
        return folder

    def test_sample_package_has_an_entrypoint_without_claiming_final_or_portable_sources(self):
        folder=self.production('sample',purpose='preview',source_package_status='incomplete',finalization_pending=['Linked media must be packaged'])
        guide=build(self.root,'sample')
        self.assertEqual(guide['delivery']['label'],'Campione')
        self.assertEqual(guide['delivery']['source_package_status'],'incomplete')
        with bundle(self.root,guide) as stream,zipfile.ZipFile(stream) as archive:
            readme=archive.read('LEGGIMI.md').decode()
            self.assertIn('Campione',readme)
            self.assertIn('pacchetto',readme.lower())
            self.assertIn('da completare',readme)
            self.assertIn('Linked media must be packaged',readme)
            self.assertIn('[product.txt](File/product.txt)',readme)
            self.assertEqual(archive.read('File/sources.zip'),(folder/'sources.zip').read_bytes())
            self.assertEqual(json.loads(archive.read('manifest-consegna.json'))['delivery']['purpose'],'preview')

    def test_legacy_archive_presence_does_not_imply_verified_portability(self):
        self.production('legacy-archive')
        guide=build(self.root)
        self.assertEqual(guide['delivery']['source_package_status'],'not_verified')
        self.production('verified-archive',source_package_status='verified')
        self.assertEqual(build(self.root)['delivery']['source_package_status'],'verified')

    def test_guide_preserves_construction_and_distinguishes_identical_copy_from_new_content(self):
        self.production('first')
        folder = self.production('copy')
        (folder / 'work/method.json').write_text('{"approach":"Packaging only","steps":["Copy unchanged files"]}')
        self.production('revised', 'Changed product')
        guide = build(self.root, 'copy')
        self.assertFalse(guide['is_current'])
        self.assertEqual(guide['delivery_id'], 'copy')
        self.assertEqual(guide['method']['approach'], 'Packaging only')
        self.assertEqual(guide['methods'][0]['approach'], 'Construct curves, then compose')
        self.assertEqual([e['change'] for e in guide['history']], ['first_export', 'identical_export', 'different_export'])
        self.assertEqual([e['goal'] for e in guide['instructions']['editing']], ['Change a value'])
        self.assertIn('Inspect the result', markdown(guide))
        self.assertEqual(build(self.root)['delivery_id'], 'revised')
        with self.assertRaises(ValueError):
            build(self.root, 'not-a-delivery')

    def test_outer_bundle_preserves_original_zip_and_binds_guide_to_selected_version(self):
        folder = self.production('selected')
        original = (folder / 'sources.zip').read_bytes()
        guide = build(self.root)
        with bundle(self.root, guide) as stream, zipfile.ZipFile(stream) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(z.read('File/sources.zip'), original)
            self.assertEqual(json.loads(z.read('guida-progetto.json'))['delivery_id'], 'selected')
            manifest = json.loads(z.read('manifest-consegna.json'))
            for item in manifest['files']:
                self.assertEqual(hashlib.sha256(z.read(item['path'])).hexdigest(), item['sha256'])
            self.assertIn('[source.txt](File/source.txt)', z.read('GUIDA-PROGETTO.md').decode())
            self.assertFalse(any('..' in Path(n).parts or n.startswith('/') for n in z.namelist()))
        self.assertEqual((folder / 'sources.zip').read_bytes(), original)
        (folder / 'product.txt').write_text('Changed after delivery')
        with self.assertRaisesRegex(ValueError, 'modificato|diverso'):
            bundle(self.root, guide)

    def test_legacy_missing_notes_and_unavailable_or_external_files_are_truthful(self):
        folder = self.production('legacy', notes=False)
        (folder / 'work/method.json').unlink()
        guide = build(self.root)
        self.assertFalse(guide['instructions']['editing'])
        self.assertIn('Procedure di modifica dettagliate non registrate', markdown(guide))
        self.assertIn('Original instructions', guide['documents'][0]['text'])
        (folder / 'source.txt').unlink()
        (folder / 'source.txt').symlink_to('/etc/hosts')
        guide = build(self.root)
        self.assertFalse(any(f['name'] == 'source.txt' for f in guide['files']))
        self.assertNotIn('/etc/hosts', json.dumps(guide))
        with self.assertRaisesRegex(ValueError, 'non sono disponibili'):
            bundle(self.root, guide)


class CommandInspectionTests(unittest.TestCase):
    def test_actual_command_and_inline_code_are_distinct_and_credentials_redacted(self):
        values = [
            'tool render --api-key "fixture-private-one" --password fixture-private-two',
            'API_KEY=fixture-private-three tool info',
            'python3 - <<\'PY\'\nconfig={"api_key":"fixture-private-four"}\nprint("rebuild curves")\nPY',
            'curl -H "Authorization: Basic Zml4dHVyZTpwYXNzd29yZA==" https://host/api',
            'curl https://user:fixture-private-five@host/api',
            'AWS_SECRET_ACCESS_KEY=fixture-private-six command',
        ]
        for command in values:
            value = sanitized(command)
            self.assertNotIn('fixture-private', value)
            self.assertNotIn('Zml4dHVyZTpwYXNzd29yZA==', value)
            self.assertEqual(sanitized(value), value)
        one = describe('python3 - <<\'PY\'\nprint("rebuild curves")\nPY')
        two = describe('python3 - <<\'PY\'\nprint("verify source")\nPY')
        self.assertNotEqual(one['command_sha256'], two['command_sha256'])
        self.assertIn('rebuild curves', one['command_preview'])
        self.assertNotEqual(describe('effectcraft-cli render scene.ecproj')['command_preview'],
                            describe('effectcraft-cli info scene.ecproj')['command_preview'])

    def test_reporter_stores_command_for_inspection_but_never_the_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / 'outputs/workspace/rh-job-123456abcdef'; out.mkdir(parents=True)
            reporter = Reporter(out, {'agent':'workspace','engine':'codex','model':'fixture','run_id':out.name})
            command = 'python3 build.py --api-key "fixture-private-seven"\nprint("operation trace")'
            reporter.cli_event('codex', {'type':'item.started','item':{'id':'command-one','type':'command_execution','command':command}})
            reporter.cli_event('codex', {'type':'item.completed','item':{'id':'command-one','type':'command_execution','exit_code':0}})
            context = read_status(reporter.path)['events'][-1]['context']
            saved, = (out / 'work/commands').glob('*/command.txt')
            self.assertIn('build.py', saved.read_text())
            self.assertNotIn('fixture-private-seven', saved.read_text())
            self.assertEqual(hashlib.sha256(saved.read_bytes()).hexdigest(), context['command_sha256'])
            self.assertNotIn('fixture-private-seven', json.dumps(context))
            self.assertFalse(public({'command_path':'/mnt/user-data/.private/command.txt'}).get('command_path'))
