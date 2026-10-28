import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from righaven import source_packages as packages
from righaven.deliveries import build_delivery, read_review


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def film(self, ref='Media/movie.mp4', clips=None):
        return {'format': 'filmcraft.project', 'project': {'items': {
            '1': {'kind': {'Media': {'media': {'File': {'path': ref}}}}},
            '2': {'kind': {'Sequence': {'video_tracks': [{'items': [{'item': 1}] if clips is None else clips}]}}}}}}

    def archive(self, files):
        path = self.root / 'sources.zip'
        with zipfile.ZipFile(path, 'w') as z:
            for name, data in files.items():
                z.writestr(name, data)
        return path

    def test_real_missing_dependency_rejected_even_when_manifest_claims_success(self):
        archive = self.archive({'project.fcproj': json.dumps(self.film()), 'unrelated.mp4': 'some bytes'})
        with self.assertRaisesRegex(ValueError, 'Dipendenza mancante'):
            packages.verify_archive(archive)

    def test_empty_timeline_absolute_paths_and_unprepared_relative_projects_rejected(self):
        for value, expected in [(self.film(clips=[]), 'vuota'), (self.film('/mnt/user-data/outputs/movie.mp4'), 'assoluto'),
                                (self.film(), 'preparato')]:
            archive = self.archive({'project.fcproj': json.dumps(value), 'Media/movie.mp4': 'movie'})
            with self.assertRaisesRegex(ValueError, expected):
                packages.verify_archive(archive)

    def test_preparation_is_local_and_originals_stay_portable(self):
        archive = self.archive({'project.fcproj': json.dumps(self.film()), 'Media/movie.mp4': 'movie',
                               'PREPARA_SORGENTI.py': Path(packages.__file__).read_text()})
        self.assertEqual(packages.verify_archive(archive)['status'], 'passed')
        moved = self.root / 'a different folder'; moved.mkdir()
        packages.extract(archive, moved)
        original = (moved / 'project.fcproj').read_bytes()
        local, = packages.prepare(moved)
        ref = list(packages.references(json.loads(local.read_text())))[0][2]
        self.assertEqual(ref, str(moved / 'Media/movie.mp4'))
        self.assertEqual((moved / 'project.fcproj').read_bytes(), original)
        shutil.move(moved, self.root / 'moved-again')
        local, = packages.prepare(self.root / 'moved-again')
        self.assertIn('moved-again/Media/movie.mp4', local.read_text())

    def test_released_preparers_remain_recognized_but_unknown_code_is_rejected(self):
        archive = self.archive({'project.fcproj': json.dumps(self.film()), 'Media/movie.mp4': 'movie',
                               'PREPARA_SORGENTI.py': 'declared historical fixture; never executed'})
        real_digest = packages.digest
        for old_hash in ('6d050d55f4d4d6ea6b78fb35b0f762cb5cbc114e7ff80fb5e00c0e938efbc1d4',
                         'dc64bb7d149025adba6c380ab676d0d19bbb74ea0779f70e0e514dd1a8b4c73a',
                         '12eabd2a5fef37534081cf20cf1b6eba22a9512caae9b857b1cce1d78024ea79'):
            def historical(path):
                return old_hash if Path(path).name == 'PREPARA_SORGENTI.py' else real_digest(path)
            with self.subTest(released_helper=old_hash), patch.object(packages, 'digest', side_effect=historical):
                self.assertEqual(packages.verify_archive(archive)['status'], 'passed')
        with self.assertRaisesRegex(ValueError, 'preparato'):
            packages.verify_archive(archive)

    def test_nested_broken_colleague_and_path_escape_are_rejected(self):
        effect = {'items': {'1': {'kind': {'type': 'Comp', 'layers': [{}]}},
                            '2': {'kind': {'type': 'Footage', 'path': 'missing-texture.png'}}}}
        nested = self.archive({'robot.ecproj': json.dumps(effect)}).read_bytes()
        archive = self.archive({'EffectCraft/sources.zip': nested})
        with self.assertRaisesRegex(ValueError, 'missing-texture'):
            packages.verify_archive(archive)
        archive = self.archive({'../escape.txt': 'bad'})
        with self.assertRaisesRegex(ValueError, 'non sicuro'):
            packages.verify_archive(archive)

    def test_runtime_does_not_accept_false_reopen_claim(self):
        archive = self.archive({'project.fcproj': json.dumps(self.film())})
        item = {'path': str(archive), 'role': 'source_archive', 'reopen': {'status': 'passed'}}
        handoff = {'task': 'Final delivery', 'delivery': {'source_status': 'included', 'source_note': 'all media included', 'files': [item]}, 'checks': []}
        result = build_delivery(handoff, self.root, native=False)
        self.assertEqual(result['technical_status'], 'needs_revision')
        self.assertIn('Dipendenza mancante', result['issues'][0])
        self.assertTrue((self.root / 'delivery-manifest.json').is_file())

    def test_filmcraft_cannot_call_readme_only_archive_editable_source(self):
        archive = self.archive({'README.txt': 'Pretend this is a complete editable project'})
        item = {'path': str(archive), 'role': 'source_archive', 'reopen': {'status': 'passed'}}
        handoff = {'task': 'Final', 'delivery': {'source_status': 'included', 'source_note': 'Complete', 'files': [item]}, 'checks': []}
        record = build_delivery(handoff, self.root, purpose='delivery', agent='filmcraft', native=False)
        self.assertEqual(record['technical_status'], 'needs_revision')
        self.assertIn('.fcproj', record['issues'][0])
        record = build_delivery(handoff, self.root, purpose='delivery', agent='workspace', tools=['filmcraft'], native=False)
        self.assertEqual(record['technical_status'], 'needs_revision')
        self.assertIn('.fcproj', record['issues'][0])

    def test_render_sources_follow_actual_component_producers_not_the_available_toolbox(self):
        image=self.root/'render.png';image.write_bytes(b'image fixture; this test checks source obligations')
        recipe=self.root/'render.py';recipe.write_text('# editable rendering recipe')
        mesh=self.root/'input.stl';mesh.write_bytes(b'unchanged input mesh')
        def item(path,role):return {'path':str(path),'role':role,'reopen':{'status':'passed','evidence':'fixture'},'limitations':[]}
        component={'name':'Render','tool':'python3','artifacts':[{'path':str(image)}],
                   'sources':[{'path':str(recipe)},{'path':str(mesh)}]}
        handoff={'task':'Render an existing model','checks':[],'source_files':[],
                 'delivery':{'source_status':'included','source_note':'Rendering recipe and input mesh',
                             'files':[item(image,'preview'),item(recipe,'editable_source'),item(mesh,'dependency')],
                             'components':[component]}}
        result=build_delivery(handoff,self.root,purpose='delivery',agent='workspace',
                              tools=['freecad','blender','filmcraft'],require_components=True)
        self.assertEqual(result['technical_status'],'passed',result['issues'])
        self.assertEqual(result['source_coverage']['status'],'documented')
        for engine,suffix in [('freecad','.FCStd'),('blender','.blend'),('filmcraft','.fcproj')]:
            with self.subTest(engine=engine):
                # Claiming native production still requires the real native source.
                component['tool']=engine
                result=build_delivery(handoff,self.root,purpose='delivery',agent='workspace',tools=[engine])
                self.assertEqual(result['technical_status'],'needs_revision')
                self.assertTrue(any(suffix.lower() in message.lower() for message in result['issues']),result['issues'])
                component['tool']='python3'
                result=build_delivery(handoff,self.root,purpose='delivery',agent=engine)
                self.assertEqual(result['technical_status'],'needs_revision')
        handoff['delivery'].pop('components')
        result=build_delivery(handoff,self.root,purpose='delivery',agent='workspace',tools=['freecad'])
        self.assertEqual(result['technical_status'],'needs_revision')

    def test_review_binds_real_product_and_text_model_cannot_claim_sensory_evaluation(self):
        product = self.root / 'video.mp4'; product.write_text('fixture')
        folder = self.root / 'review'; folder.mkdir()
        report = folder / 'quality-review.json'
        report.write_text(json.dumps({'product_path': str(product), 'criteria': [
            {'criterion': 'Good pose', 'method': 'visual', 'status': 'passed', 'evidence': 'I saw it'}]}))
        handoff = {'source_files': [str(product)], 'output_files': [str(report)]}
        review = read_review(handoff, folder, self.root, 'deepseek')
        self.assertEqual(review['status'], 'needs_review')
        self.assertEqual(review['criteria'][0]['status'], 'not_run')
        self.assertEqual(review['sha256'], packages.digest(product))
        handoff['source_files'] = []
        with self.assertRaisesRegex(ValueError, 'source_files'):
            read_review(handoff, folder, self.root, 'codex')


if __name__ == '__main__':
    unittest.main()
