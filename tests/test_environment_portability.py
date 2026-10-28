import hashlib,io,json,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from righaven import environment_portability as portable,environment_transfers as transfers,environment_activity as activity,state


def add(archive,name,data):
    entry=tarfile.TarInfo(name);entry.size=len(data);archive.addfile(entry,io.BytesIO(data))


class PortableEnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def package(self,*,tags=None,corrupt=False,extra=None):
        inner=io.BytesIO();layer=io.BytesIO()
        with tarfile.open(fileobj=layer,mode='w') as filesystem:add(filesystem,'etc/example',b'fixture file')
        layer_data=layer.getvalue();diff='sha256:'+hashlib.sha256(layer_data).hexdigest()
        config=json.dumps({'architecture':'amd64','os':'linux','rootfs':{'type':'layers','diff_ids':[diff]}}).encode()
        identity='sha256:'+hashlib.sha256(config).hexdigest()
        with tarfile.open(fileobj=inner,mode='w') as archive:
            add(archive,'manifest.json',json.dumps([{'Config':'config.json','RepoTags':tags,'Layers':['layer.tar']}]).encode())
            add(archive,'config.json',config);add(archive,'layer.tar',layer_data)
        payload=inner.getvalue()
        manifest={'format':portable.FORMAT,'version':1,'tools':['d2'],'image_id':identity,
                  'image_sha256':'0'*64 if corrupt else hashlib.sha256(payload).hexdigest()}
        path=self.root/'environment.tar'
        with tarfile.open(path,'w') as archive:
            add(archive,'manifest.json',json.dumps(manifest).encode());add(archive,'image.tar',payload)
            if extra:archive.addfile(extra)
        return path

    def test_checksum_and_docker_identity_are_verified_without_loading_image(self):
        archive=self.package();destination=self.root/'unpack';destination.mkdir()
        with patch.object(portable,'capacity'):
            manifest,image=portable.unpack(archive,destination)
            self.assertEqual(manifest['tools'],['d2']);self.assertTrue(image.exists())
            self.package(corrupt=True)
            with self.assertRaisesRegex(ValueError,'Checksum'):portable.unpack(archive,destination)

    def test_import_cannot_overwrite_local_tags_or_extract_external_paths(self):
        destination=self.root/'unpack';destination.mkdir()
        with patch.object(portable,'capacity'):
            with self.assertRaisesRegex(ValueError,'senza tag'):portable.unpack(self.package(tags=['production:latest']),destination)
            entry=tarfile.TarInfo('../outside');entry.size=0
            with self.assertRaisesRegex(ValueError,'non valido'):portable.unpack(self.package(extra=entry),destination)
            entry=tarfile.TarInfo('linked');entry.type=tarfile.SYMTYPE;entry.linkname='/etc/passwd'
            with self.assertRaisesRegex(ValueError,'non valido'):portable.unpack(self.package(extra=entry),destination)
        self.assertFalse((self.root/'outside').exists())

    def test_bundle_includes_actual_rebuild_inputs_and_uses_read_only_code(self):
        portable.rebuild_files(self.root/'rebuild',['d2'])
        root=self.root/'rebuild'
        self.assertTrue((root/'versions.lock.json').is_file())
        self.assertTrue((root/'config/toolkit/system-packages.json').is_file())
        self.assertIn('FROM node:',(root/'Dockerfile.software').read_text())
        dockerfile=(root/'Dockerfile').read_text()
        self.assertIn('ARG SOFTWARE_IMAGE=',dockerfile)
        self.assertIn('--mount=type=bind,source=bundle/harness',dockerfile)
        self.assertIn('/opt/righaven/prepare_environment.py',dockerfile)
        self.assertNotIn('COPY bundle',dockerfile)
        self.assertEqual(json.loads((root/'request.json').read_text()),{'tools':['d2'],'versions':{},'version_packages':{}})
        self.assertFalse(list(root.rglob('api.json')));self.assertFalse(list(root.rglob('auth.json')))

    def test_transfers_are_owner_scoped_and_independent_environments_can_overlap(self):
        with patch.object(state,'STATE',self.root/'state'),patch('righaven.runtime_settings.effective',return_value={'max_workers':2}):
            directory,job=transfers.create('owner','documenti','export')
            self.assertEqual(transfers.read('owner',job['id'])[1]['name'],'documenti')
            with self.assertRaises(FileNotFoundError):transfers.read('other',job['id'])
            with self.assertRaises(ValueError):transfers.create('owner','documenti','export')
            transfers.create('owner','grafica','export')
            with self.assertRaises(ValueError):transfers.create('owner','terzo','export')
            self.assertEqual(len(transfers.for_user('owner')),2);self.assertEqual(transfers.for_user('other'),[])
            self.assertNotIn('user',transfers.public(job))
            transfers.update(directory,state='ready')
            transfers.create('owner','terzo','export')

    def test_incompatible_base_is_rejected_before_loading_docker_archive(self):
        archive=self.package();target=self.root/'unpack';target.mkdir()
        with patch.object(portable,'capacity'),patch.object(portable.factory,'recipe',return_value=('a'*64,{'core':'sha256:local-base'})),patch.object(portable.factory,'docker',return_value=json.dumps([{'RootFS':{'Layers':['local-base-layer']}}])),patch.object(portable.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'Base software diversa'):portable.import_image(archive,target,['d2'])
            run.assert_not_called()

    def test_import_cannot_execute_checks_for_a_tool_excluded_from_the_native_profile(self):
        archive=self.package();target=self.root/'unpack';target.mkdir()
        with patch.object(portable,'capacity'),patch.object(portable.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'esclusi dal profilo'):portable.import_image(archive,target,[],allowed_tools=[])
            run.assert_not_called()

    def test_restart_marks_transfer_failed_and_removes_partial_archives(self):
        with patch.object(state,'STATE',self.root/'state'):
            directory,job=transfers.create('owner','documenti','import')
            (directory/'upload.tar').write_bytes(b'partial')
            transfers.recover()
            self.assertEqual(transfers.read('owner',job['id'])[1]['state'],'failed')
            self.assertFalse((directory/'upload.tar').exists())

    def test_live_activity_includes_only_the_current_users_workspace(self):
        import sys,types
        from types import SimpleNamespace
        from righaven import docker_runtime,environment_terminal
        from righaven.progress import create_job,update,workspace_key
        def workspace(thread,user_id):return self.root/'users'/user_id/'threads'/thread/'user-data'
        own=workspace('own','owner');foreign=workspace('foreign','other')
        own.mkdir(parents=True);foreign.mkdir(parents=True)
        job='rh-job-123456abcdef'
        progress=create_job(own,job,'workspace','codex','fixture')
        update(progress,'waiting_model',role_title='Revisore',work_summary='Controllo il campione',environment={'id':'a'*64,'tools':['d2']})
        paths=SimpleNamespace(user_dir=lambda user:self.root/'users'/user,sandbox_user_data_dir=workspace)
        module=types.ModuleType('righaven_core.config.paths');module.get_paths=lambda:paths
        def docker(*args):
            if args[0]=='ps':return 'own-container\nforeign-container'
            return json.dumps([{'Name':'/'+job,'Config':{'Labels':{'org.righaven.harness.workspace':workspace_key(w)}},'State':{'Running':True}} for w in (own,foreign)])
        with patch.dict(sys.modules,{'righaven_core.config.paths':module}),patch.object(docker_runtime,'docker',side_effect=docker),patch.object(portable.factory,'installation',return_value='fixture'),patch.dict(environment_terminal.SESSIONS,{},clear=True):
            result=activity.collect('owner')
        self.assertTrue(result['observed']);self.assertEqual(len(result['jobs']),1)
        self.assertEqual(result['jobs'][0]['thread_id'],'own')
        self.assertEqual(result['jobs'][0]['role'],'Revisore')

    def test_legacy_ready_export_without_image_validation_is_not_offered_as_a_download(self):
        result=transfers.public({'id':'a'*32,'name':'documenti','kind':'export','state':'ready','message':'ready','size_bytes':2385920})
        self.assertEqual(result['state'],'failed')
        self.assertIn('precedente non verificata',result['message'])
        result=transfers.public({'id':'a'*32,'name':'documenti','kind':'export','state':'ready','message':'ready','image_validated':True,'image_bytes':100000,'layer_count':3})
        self.assertEqual(result['state'],'ready');self.assertEqual(result['layer_count'],3)

    def test_transfer_progress_uses_real_file_sizes_and_missing_ready_archive_is_not_downloadable(self):
        with patch.object(state,'STATE',self.root/'state'):
            directory,job=transfers.create('owner','documenti','export')
            transfers.update(directory,phase='exporting_image')
            raw=directory/'image.tar.raw';raw.write_bytes(b'actual bytes')
            current=transfers.public(transfers.read('owner',job['id'])[1],directory)
            self.assertEqual(current['bytes_written'],len(b'actual bytes'))
            self.assertEqual(current['last_output_at'],raw.stat().st_mtime)
            transfers.update(directory,state='ready',image_validated=True)
            current=transfers.for_user('owner')[0]
            self.assertEqual(current['state'],'failed');self.assertIn('non è più disponibile',current['message'])

    def test_transfer_error_retains_redacted_docker_details_and_removes_partial_package(self):
        from righaven.docker_archives import ImageExportError
        with patch.object(state,'STATE',self.root/'state'):
            directory,job=transfers.create('owner','documenti','export')
            (directory/'environment.righaven-env.tar').write_bytes(b'incomplete package')
            def fail():raise ImageExportError('daemon failed; https://user:private-password@localhost token=private-fixture-token')
            from types import SimpleNamespace
            with patch.object(transfers.threading,'Thread',side_effect=lambda **kw:SimpleNamespace(start=kw['target'])):
                transfers.start(directory,fail)
            value=transfers.read('owner',job['id'])[1]
            self.assertEqual(value['state'],'failed');self.assertIn('daemon failed',value['error_detail'])
            self.assertNotIn('private-fixture-token',value['error_detail']);self.assertNotIn('private-password',value['error_detail'])
            self.assertFalse((directory/'environment.righaven-env.tar').exists())

    def test_unobserved_docker_never_means_idle_and_shared_runtime_shows_actual_jobs(self):
        job={'environment_id':'same','thread_id':'own-chat','role':'Revisore','summary':'Controllo il campione'}
        self.assertEqual(activity.for_runtime({'observed':False,'jobs':[]},'same')['state'],'unknown')
        result=activity.for_runtime({'observed':True,'jobs':[job]},'same')
        self.assertEqual(result['state'],'busy');self.assertEqual(result['jobs'],[job])
        self.assertEqual(activity.for_runtime({'observed':True,'jobs':[job]},'different')['state'],'idle')
        self.assertEqual(activity.for_runtime({'observed':True,'jobs':[]},'same',True)['state'],'preparing')
        scoped={**job,'profile':'documenti','environment_id':'requested-subset'}
        self.assertEqual(activity.for_runtime({'observed':True,'jobs':[scoped]},'full-preload',False,'documenti')['state'],'busy')


class TerminalOwnershipTests(unittest.TestCase):
    def test_terminal_lookup_is_owner_scoped_and_input_is_bounded(self):
        from types import SimpleNamespace
        from righaven import environment_terminal as terminal
        session=SimpleNamespace(user='owner')
        with patch.dict(terminal.SESSIONS,{'id':session},clear=True):
            self.assertIs(terminal.get('owner','id'),session)
            with self.assertRaises(FileNotFoundError):terminal.get('other','id')
        fake=SimpleNamespace(closed=False,cancelled=__import__('threading').Event(),process=SimpleNamespace(poll=lambda:None))
        with self.assertRaises(ValueError):terminal.Session.write(fake,'x'*8193)
        fake.fd=10
        with patch.object(terminal.os,'write') as write:
            terminal.Session.write(fake,'\x1b[A\x03\x00')
            write.assert_called_once_with(10,b'\x1b[A\x03\x00')


if __name__=='__main__':unittest.main()
