from pathlib import Path
import tempfile
import unittest
import zipfile
from righaven.component_sources import inspect_components


class ComponentSourcesTests(unittest.TestCase):
    def test_packaged_copies_inherit_coverage_only_when_bytes_are_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);video=root/'master.mp4';video.write_bytes(b'export')
            source=root/'animation.py';source.write_text('# editable recipe')
            archive=root/'sources.zip'
            files=[{'path':str(video),'role':'export'}, {'path':str(source),'role':'editable_source'},
                   {'path':str(archive),'role':'source_archive','verification':{'status':'passed'}}]
            handoff={'delivery':{'components':[{'name':'Animation','tool':'code',
                'artifacts':[{'path':str(video)}], 'sources':[{'path':str(source)}]}]}}
            for content,expected in [(b'export','documented'),(b'different video','incomplete')]:
                with zipfile.ZipFile(archive,'w') as z:
                    z.writestr('package/master.mp4',content);z.writestr('animation.py',source.read_bytes())
                result=inspect_components(handoff,files,required=True)
                self.assertEqual(result['status'],expected)
                if expected=='incomplete':self.assertIn('sources.zip:package/master.mp4',str(result['issues']))

    def test_editable_parent_does_not_hide_audio_without_sources(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);video=root/'master.mp4';video.write_bytes(b'fixture')
            archive=root/'sources.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('main.ecproj','native fixture');z.writestr('Audio/mix.wav','wave fixture')
                z.writestr('Audio/generate.py','print("recipe fixture; never executed")')
            files=[{'path':str(video),'role':'export'},
                   {'path':str(archive),'role':'source_archive','verification':{'status':'passed'}}]
            def ref(member):return {'path':str(archive),'member':member}
            parent={'name':'Animation','tool':'effectcraft','artifacts':[{'path':str(video)}],'sources':[ref('main.ecproj')]}
            handoff={'delivery':{'components':[parent]}}
            result=inspect_components(handoff,files,required=True)
            self.assertEqual(result['status'],'incomplete');self.assertIn('mix.wav',str(result['issues']))
            audio={'name':'Effects','tool':'soundcraft','artifacts':[ref('Audio/mix.wav')],'sources':[ref('main.ecproj')]}
            handoff['delivery']['components'].append(audio)
            self.assertIn('.scraft',str(inspect_components(handoff,files)['issues']))
            audio.update(tool='code',sources=[ref('Audio/mix.wav')])
            self.assertIn('appiattiti',str(inspect_components(handoff,files)['issues']))
            audio['sources']=[ref('Audio/generate.py')]
            self.assertEqual(inspect_components(handoff,files)['status'],'documented')
            audio['sources']=[ref('../missing.py')]
            self.assertEqual(inspect_components(handoff,files)['status'],'incomplete')

    def test_provided_original_requires_the_uploaded_input_and_identical_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);upload=root/'uploads/original.wav';upload.parent.mkdir();upload.write_bytes(b'original wave')
            final=root/'mix.wav';final.write_bytes(upload.read_bytes());r={'path':str(final)}
            handoff={'source_files':[str(upload)],'delivery':{'components':[
                {'name':'Original recording','tool':'provided','artifacts':[r],'sources':[r],'provided_inputs':[str(upload)]}]}}
            files=[{'path':str(final),'role':'export'}]
            self.assertEqual(inspect_components(handoff,files,workspace=root)['status'],'documented')
            final.write_bytes(b'a different mix')
            self.assertEqual(inspect_components(handoff,files,workspace=root)['status'],'incomplete')
            handoff['source_files']=[]
            self.assertEqual(inspect_components(handoff,files,workspace=root)['status'],'incomplete')

    def test_nested_colleague_sources_and_media_are_resolved_without_flattening_the_package(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);nested=root/'audio.zip';archive=root/'all.zip'
            with zipfile.ZipFile(nested,'w') as z:
                z.writestr('session.scraft','native fixture');z.writestr('media/mix.wav','wave fixture')
            with zipfile.ZipFile(archive,'w') as z:
                z.write(nested,'SoundCraft/sources.zip')
                z.writestr('Media/other.wav','original bytes')
            upload=root/'uploads/other.wav';upload.parent.mkdir();upload.write_bytes(b'original bytes')
            files=[{'path':str(archive),'role':'source_archive','verification':{'status':'passed'}}]
            def ref(member):return {'path':str(archive),'member':member}
            handoff={'source_files':[str(upload)],'delivery':{'components':[
                {'name':'Music','tool':'soundcraft','artifacts':[ref('SoundCraft/sources.zip/media/')],
                 'sources':[ref('SoundCraft/sources.zip/session.scraft')]},
                {'name':'User recording','tool':'provided','artifacts':[ref('Media/other.wav')],
                 'sources':[ref('Media/other.wav')],'provided_inputs':[str(upload)]}]}}
            self.assertEqual(inspect_components(handoff,files,workspace=root)['status'],'documented')
            handoff['delivery']['components'][0]['artifacts']=[ref('SoundCraft/sources.zip/session.scraft')]
            result=inspect_components(handoff,files,workspace=root)
            self.assertEqual(result['status'],'incomplete')
            self.assertIn('mix.wav',str(result['issues']))
            handoff['delivery']['components'][0]['sources']=[ref('SoundCraft/sources.zip/missing.scraft')]
            self.assertEqual(inspect_components(handoff,files,workspace=root)['status'],'incomplete')

    def test_frame_sequence_can_reference_a_verified_directory_without_enumerating_every_frame(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'sources.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('main.ecproj','native fixture')
                for i in range(1000):z.writestr(f'frames/{i:04d}.png','frame fixture')
            files=[{'path':str(archive),'role':'source_archive','verification':{'status':'passed'}}]
            component={'name':'Frame sequence','tool':'effectcraft',
                'artifacts':[{'path':str(archive),'member':'frames/'}],
                'sources':[{'path':str(archive),'member':'main.ecproj'}]}
            handoff={'delivery':{'components':[component]}}
            self.assertEqual(inspect_components(handoff,files)['status'],'documented')
            component['sources']=[{'path':str(archive),'member':'frames/'}]
            self.assertEqual(inspect_components(handoff,files)['status'],'incomplete')
            component['artifacts']=[{'path':str(archive),'member':'missing/'}]
            self.assertEqual(inspect_components(handoff,files)['status'],'incomplete')

    def test_missing_inventory_is_explicit_for_new_deliveries_and_compatible_with_legacy(self):
        self.assertEqual(inspect_components({},[],required=True)['status'],'not_recorded')
        self.assertTrue(inspect_components({},[],required=True)['issues'])
        self.assertFalse(inspect_components({},[])['issues'])
