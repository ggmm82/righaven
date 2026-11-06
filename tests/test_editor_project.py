"""Direct manual editing shares the public project; legacy drafts stay isolated."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import editor_documents as docs


class ProjectEditing(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.folder=self.root/'outputs/project';self.folder.mkdir(parents=True)
        self.original=self.folder/'example.py';self.original.write_text('print(1)\n')
        self.path='/mnt/user-data/outputs/project/example.py'

    def start(self):return docs.start(self.root,self.path,'text',[],direct=True)

    def test_folder_is_shared_without_dependency_copy_and_legacy_draft_stays_private(self):
        (self.folder/'texture.svg').write_text('<svg/>')
        legacy=docs.start(self.root,self.path,'text',[])
        session=self.start();self.assertEqual(session['mode'],'project')
        self.assertNotEqual(session['id'],legacy['id'])
        self.assertEqual({row['name'] for row in session['files']},{'project/example.py','project/texture.svg'})
        changed=docs.save(self.root,session['id'],session['entry'],b'print(2)',0,[],True)
        self.assertEqual(self.original.read_text(),'print(2)')
        self.assertEqual(docs.file(self.root,legacy['id'],legacy['entry'],[]).read_text(),'print(1)\n')
        self.assertEqual(self.start()['id'],session['id'])
        self.assertEqual(changed['revision'],1)
        saved=self.root/'.righaven-project/editors'/session['id']
        self.assertEqual((saved/'original-source').read_text(),'print(1)\n')
        self.assertEqual((saved/'history/0/project/example.py').read_text(),'print(1)\n')

    def test_running_kernel_does_not_lock_project_download_or_asset_upload(self):
        session=self.start()
        with patch.object(docs,'active_service',return_value=object()):
            with docs.open_file(self.root,session['id'],session['entry'],[]) as stream:self.assertEqual(stream.read(),b'print(1)\n')
            docs.save(self.root,session['id'],'project/new.svg',b'<svg/>',0,[])
            self.assertIn('project/new.svg',[row['name'] for row in docs.get(self.root,session['id'],[])['files']])

    def test_public_folder_access_rejects_symlinks_control_files_and_other_chats(self):
        session=self.start()
        for name in ('../.righaven-project/project.json','/etc/passwd','.private','project/../../secret'):
            with self.assertRaises(ValueError):docs.open_file(self.root,session['id'],name,[])
        (self.folder/'secret').symlink_to('/etc/passwd')
        with self.assertRaises(ValueError):docs.open_file(self.root,session['id'],'project/secret',[])
        with self.assertRaises(ValueError):docs.get(self.root/'other-chat',session['id'],[])

    def test_streamed_save_keeps_previous_version_and_conflict_does_not_overwrite(self):
        session=self.start();staged=self.root/'upload';staged.write_bytes(b'new')
        docs.save_project_file(self.root,session['id'],session['entry'],staged,0,[])
        self.assertEqual(self.original.read_bytes(),b'new')
        staged.write_bytes(b'stale')
        with self.assertRaisesRegex(ValueError,'changed'):docs.save_project_file(self.root,session['id'],session['entry'],staged,0,[])
        self.assertEqual(self.original.read_bytes(),b'new')

    def test_native_writes_are_immediately_visible_to_downloads(self):
        session=self.start();root,_=docs.record(self.root/'.righaven-project',session['id'],[])
        (docs.file_root(root)/session['entry']).write_text('written by kernel')
        with docs.open_file(self.root,session['id'],session['entry'],[]) as stream:self.assertEqual(stream.read(),b'written by kernel')
        (self.folder/'results.csv').write_text('a,b\n1,2')
        self.assertIn('project/results.csv',[row['name'] for row in docs.get(self.root,session['id'],[])['files']])

    def test_large_companions_are_not_hashed_or_loaded_when_opening_project(self):
        large=self.folder/'video.mp4'
        with large.open('wb') as stream:stream.truncate(docs.MAX_FILE+1)
        session=self.start()
        row=next(r for r in session['files'] if r['name'].endswith('video.mp4'))
        self.assertEqual(row['bytes'],docs.MAX_FILE+1)
        with docs.open_file(self.root,session['id'],'project/video.mp4',[]) as stream:self.assertEqual(len(stream.read(3)),3)

    def test_source_archive_becomes_one_persistent_editable_project(self):
        import zipfile
        archive=self.root/'outputs/sources.zip'
        with zipfile.ZipFile(archive,'w') as bundle:
            bundle.writestr('project/notes.md','Original')
            bundle.writestr('project/assets/logo.svg','<svg/>')
        kwargs={'entry':'project/notes.md','direct':True}
        first=docs.start(self.root,'/mnt/user-data/outputs/sources.zip','text',[],**kwargs)
        second=docs.start(self.root,'/mnt/user-data/outputs/sources.zip','text',[],**kwargs)
        self.assertEqual(first['id'],second['id'])
        self.assertEqual(first['mode'],'project')
        docs.save(self.root,first['id'],first['entry'],b'Changed',0,[],True)
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as bundle:self.assertEqual(bundle.read('project/notes.md'),b'Original')
        current=docs.get(self.root,first['id'],[])
        with docs.open_file(self.root,first['id'],current['entry'],[]) as stream:self.assertEqual(stream.read(),b'Changed')

    def test_http_save_cannot_be_redirected_by_a_native_directory_swap(self):
        session=self.start();upload=self.root/'upload';upload.write_bytes(b'new')
        outside=self.root/'outside';outside.mkdir();(outside/'example.py').write_text('Untouched')
        original=docs.os.replace
        def race(source,target,*args,**kwargs):
            if kwargs.get('dst_dir_fd') is not None:
                self.folder.rename(self.root/'outputs/owned-before-swap')
                self.folder.symlink_to(outside,target_is_directory=True)
            return original(source,target,*args,**kwargs)
        with patch.object(docs.os,'replace',side_effect=race):
            with self.assertRaises(ValueError):docs.save_project_file(self.root,session['id'],session['entry'],upload,0,[])
        self.assertEqual((outside/'example.py').read_text(),'Untouched')
        self.assertEqual((self.root/'outputs/owned-before-swap/example.py').read_bytes(),b'new')

    def test_public_chat_resources_are_readable_writable_and_keep_source_locations(self):
        uploads=self.root/'uploads';uploads.mkdir();resource=uploads/'logo.svg';resource.write_text('<svg/>')
        session=self.start();sid=session['id']
        with docs.open_file(self.root,sid,'@chat/uploads/logo.svg',[]) as stream:self.assertEqual(stream.read(),b'<svg/>')
        changed=docs.save(self.root,sid,'@chat/uploads/logo.svg',b'<svg>changed</svg>',0,[],True)
        self.assertEqual(resource.read_text(),'<svg>changed</svg>')
        self.assertEqual(changed['virtual_path'],'/mnt/user-data/uploads/logo.svg')
        for name in ('@chat/.righaven-project/project.json','@chat/uploads/../../secret'):
            with self.assertRaises(ValueError):docs.open_file(self.root,sid,name,[])

    def test_effect_resource_discovery_includes_external_uploads_and_sequence_frames(self):
        uploads=self.root/'uploads';uploads.mkdir();(uploads/'logo.svg').write_text('<svg/>')
        frames=self.folder/'frames';frames.mkdir();(frames/'0001.png').write_bytes(b'frame1');(frames/'0002.png').write_bytes(b'frame2')
        project={'items':{'1':{'kind':{'type':'Comp','layers':[{'source':2}]}},'2':{'kind':{'type':'Footage','path':'frames/0001.png','sequence':['frames/0001.png','frames/0002.png']}},'3':{'kind':{'type':'Footage','path':'/mnt/user-data/uploads/logo.svg'}}}}
        (self.folder/'scene.ecproj').write_text(json.dumps(project))
        version={'editor_version':'0.16.0','cli_version':'0.16.0','tool_versions':{}}
        with patch('righaven.editor_versions.selection',return_value=version):
            session=docs.start(self.root,'/mnt/user-data/outputs/project/scene.ecproj','effectcraft',['effectcraft'],direct=True)
        self.assertEqual(set(session['dependencies']),{'project/frames/0001.png','project/frames/0002.png','@chat/uploads/logo.svg'})
        self.assertEqual(session['missing_dependencies'],[])
        # Opening an unfinished composition must still load all its media.
        project['items']['1']['kind']['layers']=[]
        (self.folder/'scene.ecproj').write_text(json.dumps(project))
        reopened=docs.get(self.root,session['id'],['effectcraft'])
        self.assertEqual(set(reopened['dependencies']),set(session['dependencies']))
        project['items']['0']={'kind':{'type':'Footage','path':'/outside/project/missing.svg'}}
        (self.folder/'scene.ecproj').write_text(json.dumps(project))
        reopened=docs.get(self.root,session['id'],['effectcraft'])
        self.assertEqual(set(reopened['dependencies']),set(session['dependencies']))
        self.assertEqual(len(reopened['missing_dependencies']),1)


        self.assertIn('@chat/uploads/logo.svg',[row['name'] for row in session['files']])
