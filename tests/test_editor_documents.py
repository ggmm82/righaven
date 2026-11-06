"""Durable drafts, optimistic writes, archive assets and native capability policy."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from righaven import state,editor_documents as docs,editor_catalog,editor_assets

class EditorDocuments(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        (self.root/'outputs').mkdir();self.original=self.root/'outputs/report.md';self.original.write_text('Original')
        self.path='/mnt/user-data/outputs/report.md';change=patch.object(state,'STATE',self.root/'state');change.start();self.addCleanup(change.stop)

    def test_resumption_explicit_publication_conflicts_and_immutable_original(self):
        session=docs.start(self.root,self.path,'text',[]);sid=session['id']
        changed=docs.save(self.root,sid,'report.md',b'Edited',0,[],True)
        self.assertEqual(changed['revision'],1);self.assertEqual(self.original.read_text(),'Original')
        self.assertFalse((self.root/'.righaven-project/source-edits.json').exists())
        self.assertEqual(docs.start(self.root,self.path,'text',[])['id'],sid)
        with self.assertRaisesRegex(ValueError,'Draft changed'):docs.save(self.root,sid,'report.md',b'Stale',0,[])
        publication=docs.publish(self.root,sid,1,[]);self.assertEqual(docs.publish(self.root,sid,1,[]),publication)
        target=self.root/publication['path'].removeprefix('/mnt/user-data/');self.assertEqual(target.read_text(),'Edited')
        self.assertFalse(publication['exports_regenerated'])
        docs.save(self.root,sid,'report.md',b'Next draft',1,[]);self.assertEqual(target.read_text(),'Edited')
        self.original.write_text('New delivery')
        with self.assertRaisesRegex(ValueError,'Original source changed'):docs.publish(self.root,sid,2,[])

    def test_interrupted_publication_can_retry_without_overwriting_the_materialized_revision(self):
        session=docs.start(self.root,self.path,'text',[]);sid=session['id'];original=docs.atomic_json
        def interrupted(path,value):
            if Path(path).name=='source-edits.json':raise OSError('fixture interrupted publication')
            return original(path,value)
        with patch.object(docs,'atomic_json',side_effect=interrupted):
            with self.assertRaises(OSError):docs.publish(self.root,sid,0,[])
        targets=list((self.root/'outputs/source-revisions').rglob('report.md'));self.assertEqual(len(targets),1)
        before=targets[0].stat().st_ino
        result=docs.publish(self.root,sid,0,[])
        self.assertEqual(targets[0].stat().st_ino,before);self.assertEqual(result['files_count'],1)
        self.assertEqual(docs.publish(self.root,sid,0,[]),result)

    def test_path_confinement_policy_and_account_roots(self):
        sid=docs.start(self.root,self.path,'text',[])['id']
        for name in ('../secret','/etc/passwd','a/../../secret','.hidden','a\\b','a//b'):
            with self.assertRaises(ValueError):docs.save(self.root,sid,name,b'x',0,[])
        (self.root/'outputs/linked').symlink_to(self.root/'outputs',target_is_directory=True)
        with self.assertRaises(ValueError):docs.start(self.root,'/mnt/user-data/outputs/linked/report.md','text',[])
        with self.assertRaises(ValueError):docs.start(self.root,self.path,'wordcraft',[])
        other=self.root/'another-user';other.mkdir()
        with self.assertRaises(ValueError):docs.get(other,sid,[])
        (self.root/'outputs/image.svg').write_text('<svg/>')
        graphic=docs.start(self.root,'/mnt/user-data/outputs/image.svg','vectorcraft',['vectorcraft'])
        with self.assertRaises(ValueError):docs.get(self.root,graphic['id'],[])
        self.assertEqual(docs.start(self.root,self.path,'text',[])['id'],sid)

    def test_native_project_keeps_referenced_assets_and_missing_media_blocks_publish(self):
        source=self.root/'outputs/session.scraft';source.write_text(json.dumps({'tracks':[{'path':'track.wav'}]}));(self.root/'outputs/track.wav').write_bytes(b'audio')
        session=docs.start(self.root,'/mnt/user-data/outputs/session.scraft','soundcraft',['soundcraft'])
        self.assertEqual(len(session['files']),2)
        native=docs.file(self.root,session['id'],session['entry'],['soundcraft']);ref=json.loads(native.read_text())['tracks'][0]['path']
        self.assertTrue(ref.startswith('assets/'));docs.file(self.root,session['id'],ref,['soundcraft']).unlink()
        with self.assertRaisesRegex(ValueError,'mancante'):docs.publish(self.root,session['id'],0,['soundcraft'])
        self.assertEqual(json.loads(source.read_text())['tracks'][0]['path'],'track.wav')

    def test_archived_source_selector_preserves_relative_bundle_and_rejects_traversal(self):
        archive=self.root/'outputs/sources.zip'
        with zipfile.ZipFile(archive,'w') as z:
            z.writestr('project/session.scraft',json.dumps({'tracks':[{'path':'media/track.wav'}]}));z.writestr('project/media/track.wav',b'audio')
        rows=docs.discovery(self.root,'/mnt/user-data/outputs/sources.zip',['soundcraft']);self.assertEqual(rows[0]['entry'],'project/session.scraft')
        session=docs.start(self.root,'/mnt/user-data/outputs/sources.zip','soundcraft',['soundcraft'],'project/session.scraft')
        result=docs.publish(self.root,session['id'],0,['soundcraft']);self.assertEqual(result['files_count'],2)
        manifest=self.root/result['manifest_path'].removeprefix('/mnt/user-data/');self.assertEqual(len(json.loads(manifest.read_text())['files']),2)
        with zipfile.ZipFile(archive,'w') as z:z.writestr('../escape',b'x')
        with self.assertRaises(ValueError):docs.discovery(self.root,'/mnt/user-data/outputs/sources.zip',['soundcraft'])

    def test_fake_native_document_and_import_source_distinction(self):
        (self.root/'outputs/fake.docx').write_text('Not a Word document')
        with self.assertRaisesRegex(ValueError,'native document'):docs.start(self.root,'/mnt/user-data/outputs/fake.docx','wordcraft',['wordcraft'])
        self.assertEqual(docs.listing(self.root,['wordcraft']),[])
        rows=editor_catalog.candidates('model.glb',['blender','cadcraft']);self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['id'],'blender');self.assertEqual(rows[0]['relationship'],'import');self.assertTrue(rows[0]['notice'])
        self.assertEqual(editor_catalog.candidates('model.blend',[]),[])

    def test_python_can_choose_jupyter_and_switch_preserves_saved_draft_without_publication(self):
        path=self.root/'outputs/program.py';path.write_text('print(1)')
        choices=editor_catalog.candidates('program.py',['jupyter'])
        self.assertEqual([row['id'] for row in choices],['text','jupyter'])
        self.assertEqual(choices[1]['opening_mode'],'text')
        self.assertNotIn('jupyter',[row['id'] for row in editor_catalog.candidates('program.py',[])])
        original=docs.start(self.root,'/mnt/user-data/outputs/program.py','text',[])
        docs.save(self.root,original['id'],'program.py',b'print(2)',0,[],True)
        changed=docs.open_with(self.root,original['id'],'jupyter',['jupyter'])
        self.assertNotEqual(original['id'],changed['id']);self.assertEqual(changed['entry'],'program.py')
        self.assertEqual(docs.file(self.root,changed['id'],'program.py',['jupyter']).read_bytes(),b'print(2)')
        self.assertEqual(path.read_text(),'print(1)');self.assertFalse((self.root/'.righaven-project/source-edits.json').exists())
        docs.save(self.root,changed['id'],'program.py',b'print(3)',0,['jupyter'],True)
        self.assertEqual(docs.file(self.root,original['id'],'program.py',[]).read_bytes(),b'print(2)')
        with self.assertRaisesRegex(ValueError,'disabled'):docs.open_with(self.root,original['id'],'jupyter',[],True)
        with patch.object(docs,'active_service',return_value=object()):
            with self.assertRaisesRegex(ValueError,'Close and save'):docs.open_with(self.root,original['id'],'jupyter',['jupyter'])

    def test_manual_choice_is_explicit_but_does_not_enable_disabled_tools(self):
        with self.assertRaisesRegex(ValueError,'format'):docs.start(self.root,self.path,'photocraft',['photocraft'])
        changed=docs.start(self.root,self.path,'photocraft',['photocraft'],manual=True)
        self.assertTrue(changed['manual_selection']);self.assertEqual(self.original.read_text(),'Original')
        with self.assertRaisesRegex(ValueError,'disabled'):docs.start(self.root,self.path,'photocraft',[],manual=True)
        self.assertNotIn('jupyter',[row['id'] for row in editor_catalog.candidates('picture.png',['jupyter'])])

    def test_release_tags_and_numeric_versions_share_the_same_browser_cache(self):
        self.assertEqual(editor_assets.location('wordcraft','v0.10.0'),editor_assets.location('wordcraft','0.10.0'))

    def test_verified_browser_archive_rejects_traversal(self):
        archive=self.root/'web.zip';destination=self.root/'web';destination.mkdir()
        with zipfile.ZipFile(archive,'w') as z:z.writestr('app-web/index.html','Editor');z.writestr('app-web/app.wasm',b'wasm')
        editor_assets.extract(archive,destination);self.assertTrue((destination/'index.html').is_file())
        with zipfile.ZipFile(archive,'w') as z:z.writestr('app/../../escape',b'x')
        with self.assertRaises(ValueError):editor_assets.extract(archive,self.root/'invalid')

    def test_export_opens_hashed_editable_source_from_its_delivery_and_keeps_export_choice(self):
        import hashlib
        exported=self.root/'outputs/report.pdf';exported.write_bytes(b'%PDF-1.7 fixture')
        original=self.root/'outputs/report.docx'
        with zipfile.ZipFile(original,'w') as z:z.writestr('word/document.xml','<document>Editable</document>')
        folder=self.root/'.righaven-project';folder.mkdir()
        manifest={'steps':[{'attempts':[{'delivery_record':{'files':[
            {'path':'/mnt/user-data/outputs/report.pdf','role':'export','sha256':hashlib.sha256(exported.read_bytes()).hexdigest()},
            {'path':'/mnt/user-data/outputs/report.docx','role':'editable_source','sha256':hashlib.sha256(original.read_bytes()).hexdigest()}]}}]}]}
        (folder/'project.json').write_text(json.dumps(manifest))
        rows=docs.associations(self.root,'/mnt/user-data/outputs/report.pdf',['wordcraft','pdfcraft'])
        self.assertEqual(rows[0]['id'],'wordcraft');self.assertEqual(rows[0]['source_path'],'/mnt/user-data/outputs/report.docx')
        self.assertTrue(any(row['id']=='pdfcraft' for row in rows))
        original.write_bytes(b'changed source')
        rows=docs.associations(self.root,'/mnt/user-data/outputs/report.pdf',['wordcraft','pdfcraft'])
        self.assertEqual([row['id'] for row in rows],['pdfcraft'])

    def test_corrupt_source_archives_are_rejected_as_input_errors(self):
        path=self.root/'outputs/broken.zip';path.write_bytes(b'not a ZIP')
        with self.assertRaisesRegex(ValueError,'native document archive'):docs.discovery(self.root,'/mnt/user-data/outputs/broken.zip',[])

    def test_a_live_runtime_cannot_make_gateway_file_reads_or_publications_follow_links(self):
        from types import SimpleNamespace
        from righaven import editor_runtime
        session=docs.start(self.root,self.path,'text',[]);sid=session['id']
        runtime=SimpleNamespace(workspace=self.root,sid=sid,closed=False,before=session['files'])
        with patch.dict(editor_runtime.SESSIONS,{'fixture':runtime},clear=True):
            link=self.root/'.righaven-project/editors'/sid/'files/leak.txt';link.symlink_to(self.original)
            self.assertEqual(docs.get(self.root,sid,[])['files'],session['files'])
            for operation in [lambda:docs.open_file(self.root,sid,'report.md',[]),lambda:docs.save(self.root,sid,'report.md',b'changed',0,[]),lambda:docs.publish(self.root,sid,0,[])]:
                with self.assertRaisesRegex(ValueError,'Close and save'):operation()
            link.unlink()

    def test_streaming_uses_the_open_file_not_a_path_that_can_be_replaced(self):
        import os
        sid=docs.start(self.root,self.path,'text',[])['id'];target=self.root/'.righaven-project/editors'/sid/'files/report.md'
        stream=docs.open_file(self.root,sid,'report.md',[])
        target.unlink();target.symlink_to(self.original)
        try:self.assertEqual(stream.read(),b'Original')
        finally:stream.close()
        with self.assertRaises(ValueError):docs.open_file(self.root,sid,'report.md',[])
        fifo=target.with_name('fifo.txt');os.mkfifo(fifo)
        with self.assertRaises(ValueError):docs.open_file(self.root,sid,'fifo.txt',[])

    def test_owner_can_choose_the_primary_editable_file_without_overwriting_the_source(self):
        session=docs.start(self.root,self.path,'text',[]);sid=session['id']
        docs.save(self.root,sid,'new.md',b'New primary source',0,[])
        changed=docs.choose_entry(self.root,sid,'new.md',1,[])
        self.assertEqual(changed['entry'],'new.md');self.assertEqual(changed['revision'],2)
        publication=docs.publish(self.root,sid,2,[])
        self.assertTrue(publication['path'].endswith('/new.md'));self.assertEqual(self.original.read_text(),'Original')
        with self.assertRaises(ValueError):docs.choose_entry(self.root,sid,'report.pdf',2,[])

    def test_jupyter_links_scripts_to_text_editor_and_notebooks_to_notebook_ui(self):
        from types import SimpleNamespace
        from righaven.editor_runtime import Service
        service=SimpleNamespace(id='fixture',state='ready',message='',environment_id='a'*64,proxy='/private/',error='',resources=None,interface_version='6',document={'editor':'jupyter','editor_version':'6','entry':'folder/script.py'})
        self.assertEqual(Service.public(service)['url'],'/private/lab/tree/folder/script.py')
        service.document['entry']='test.ipynb'
        self.assertEqual(Service.public(service)['url'],'/private/lab/tree/test.ipynb')
        service.document.update(mode='project',project_root='outputs')
        self.assertEqual(Service.public(service)['url'],'/private/lab/tree/outputs/test.ipynb')
        service.document['entry']='@chat/uploads/test.ipynb'
        self.assertEqual(Service.public(service)['url'],'/private/lab/tree/uploads/test.ipynb')
        service.document['editor']='blender'
        self.assertIn('resize=scale',Service.public(service)['url'])

    def test_manual_unknown_extension_can_edit_and_publish_text_but_never_corrupt_binary(self):
        original=self.root/'outputs/server.log';original.write_text('Initial log')
        value=docs.start(self.root,'/mnt/user-data/outputs/server.log','text',[],manual=True)
        self.assertIn('.log',value['native_extensions'])
        docs.save(self.root,value['id'],'server.log',b'Updated log',0,[],True)
        result=docs.publish(self.root,value['id'],1,[])
        self.assertEqual((self.root/result['path'].removeprefix('/mnt/user-data/')).read_text(),'Updated log')
        self.assertEqual(original.read_text(),'Initial log')
        with self.assertRaisesRegex(ValueError,'UTF-8'):docs.save(self.root,value['id'],'server.log',b'\0binary',1,[],True)
        (self.root/'outputs/binary.unknown').write_bytes(b'\xff\0')
        with self.assertRaisesRegex(ValueError,'UTF-8'):docs.start(self.root,'/mnt/user-data/outputs/binary.unknown','text',[],manual=True)
