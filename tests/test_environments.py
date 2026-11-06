"""Native scopes, install recipes, dependency discovery and cache lifecycle."""
import json, tempfile, threading, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from righaven import environments as profiles, environment_runtime as factory, state


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        from righaven.resource_budget import ResourceBudget
        budget_patch = patch('righaven.resource_budget.BUDGET', ResourceBudget())
        budget_patch.start(); self.addCleanup(budget_patch.stop)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.patch=patch.object(state,'STATE',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        (self.root/'installation-id').write_text('fixture')

    def skill(self,name,enabled=True,tools=None):
        directory=self.root/name;directory.mkdir(exist_ok=True)
        (directory/'SKILL.md').write_text('---\nname: '+name+'\ndescription: Fixture method\nmetadata:\n  righaven-tools: '+json.dumps(tools or [])+'\n---\nInstructions')
        return SimpleNamespace(name=name,enabled=enabled,skill_dir=directory)

    def test_skill_requirements_are_declarative_and_cannot_enable_a_disabled_engine(self):
        skills=[self.skill('skill-d2',False),self.skill('my-method',tools=['d2'])]
        with patch.object(profiles,'skill_inventory',return_value=skills):
            with self.assertRaisesRegex(ValueError,'disabilitato'):profiles.resolve_skills('owner',['my-method'])
            skills[0].enabled=True
            result=profiles.resolve_skills('owner',['my-method'])
            self.assertEqual(result['tools'],['d2']);self.assertIn('skill-d2',result['skills'])
            skills[0].enabled=False
            result=profiles.resolve_skills('owner',['skill-d2'])
            self.assertEqual(result['tools'],[]);self.assertEqual(result['disabled'],['skill-d2'])
        with self.assertRaisesRegex(ValueError,'catalogo'):profiles.skill_requirements(self.skill('bad',tools=['invented']))

    def test_disabling_a_dependency_changes_profile_identity_and_excludes_its_method(self):
        skills=[self.skill('skill-d2'),self.skill('my-method',tools=['d2'])]
        agent=SimpleNamespace(name='custom',description='Purpose',display_name='Custom',skills=['my-method'],soul='Instructions')
        with patch.object(profiles,'skill_inventory',return_value=skills),patch.object(profiles,'preferences',return_value={}):
            before=profiles.profile('owner',agent)
            self.assertIn('d2',before['tools'])
            skills[0].enabled=False
            after=profiles.profile('owner',agent)
            self.assertEqual(after['tools'],[])
            self.assertNotIn('my-method',after['active_skills'])
            self.assertIn('my-method',after['disabled'])
            self.assertNotEqual(before['revision'],after['revision'])

    def test_empty_method_has_no_native_dependency_and_scope_does_not_copy_all_enabled_skills(self):
        skills=[self.skill('method'),self.skill('skill-blender'),self.skill('skill-d2')]
        with patch.object(profiles,'skill_inventory',return_value=skills):
            self.assertEqual(profiles.resolve_skills('owner',['method'])['tools'],[])
            self.assertEqual(profiles.resolve_skills('owner',['skill-d2'])['tools'],['d2'])

    def test_preload_selection_intersects_current_native_scope(self):
        self.assertEqual(profiles.preloaded_tools({'mode':'preload','preload_tools':['d2','blender']},['d2']),['d2'])
        self.assertEqual(profiles.preloaded_tools({'mode':'on_demand','preload_tools':['d2']},['d2']),[])
        self.assertEqual(profiles.preloaded_tools({'mode':'preload'},['d2']),['d2'])

    def test_http_profile_preserves_embedded_instructions_including_empty_soul(self):
        agent=SimpleNamespace(name='custom',description='Scope',display_name=None,skills=[],soul='Keep sources')
        with patch.object(profiles,'resolve_skills',return_value={'skills':[],'tools':[],'disabled':[]}),patch.object(profiles,'preferences',return_value={}):
            first=profiles.profile('owner',agent)
            self.assertEqual(first['instructions'],'Keep sources')
            agent.soul=None
            second=profiles.profile('owner',agent)
            self.assertEqual(second['instructions'],'')
            self.assertNotEqual(first['revision'],second['revision'])

    def test_dependency_closure_identity_and_recipe_invalidation(self):
        with patch.object(factory,'docker',return_value='sha256:core-v1'):
            first,spec=factory.recipe(['mermaid','d2','d2'])
            second,_=factory.recipe(['d2','mermaid'])
        self.assertEqual(first,second);self.assertEqual(spec['tools'],['d2','mermaid','playwright'])
        with patch.object(factory,'docker',return_value='sha256:core-v2'):
            self.assertNotEqual(first,factory.recipe(['mermaid','d2'])[0])
        with self.assertRaises(ValueError):factory.recipe(['unknown'])

    def test_cache_validates_immutable_image_and_installation_owner(self):
        value={'id':'a'*64,'status':'ready','image':'local:env','image_id':'sha256:one'}
        data={'Id':'sha256:one','Config':{'Labels':{'org.righaven.environment':value['id'],'org.righaven.harness.installation':'fixture'}}}
        with patch.object(factory,'docker',return_value=json.dumps([data])):
            self.assertTrue(factory.image_exists(value))
            data['Config']['Labels']['org.righaven.harness.installation']='other'
        with patch.object(factory,'docker',return_value=json.dumps([data])):self.assertFalse(factory.image_exists(value))

    def test_eviction_refuses_pinned_and_in_use_images(self):
        key='a'*64;factory.save(key,status='ready',image='owned:env',image_id='sha256:one')
        with patch.object(factory,'image_exists',return_value=True),patch.object(factory,'pinned',return_value={key}):
            with self.assertRaisesRegex(ValueError,'predeploy'):factory.evict(key)
        with patch.object(factory,'image_exists',return_value=True),patch.object(factory,'pinned',return_value=set()),patch.object(factory,'docker',return_value='running') as docker:
            with self.assertRaisesRegex(ValueError,'in uso'):factory.evict(key)
            self.assertEqual(docker.call_count,1)

    def test_restart_records_interrupted_preparation_without_deleting_files(self):
        key='b'*64;factory.save(key,status='installing',container='old')
        product=self.root/'product.txt';product.write_text('keep')
        factory.reconcile()
        self.assertEqual(factory.read(key)['status'],'failed');self.assertEqual(product.read_text(),'keep')
        with self.assertRaises(ValueError):factory.read('../invalid')

    def test_cancelled_preparation_does_not_create_container(self):
        cancel=threading.Event();cancel.set()
        with patch.object(factory,'docker',return_value='sha256:core') as docker:
            with self.assertRaisesRegex(RuntimeError,'annullata'):factory.ensure(['d2'],cancel=cancel)
            docker.assert_not_called()

    def test_sources_only_add_real_native_formats_not_arbitrary_python(self):
        import zipfile
        source=self.root/'source.zip'
        with zipfile.ZipFile(source,'w') as archive:
            archive.writestr('scene.blend','fixture');archive.writestr('script.py','not manim')
        with patch('righaven.projects.artifact_path',return_value=source):
            result=factory.source_tools(self.root,'Use /mnt/user-data/source.zip',['d2'])
        self.assertEqual(result,['blender','d2'])

    def test_presets_reference_registered_tools_and_cover_requested_purposes(self):
        presets=profiles.preset_catalog()
        self.assertGreaterEqual(len(presets),9)
        self.assertTrue(all(not p['missing_tools'] for p in presets))
        self.assertTrue({'documenti','progettazione','modellazione-3d','grafica','web','sviluppo','sicurezza'}.issubset({p['id'] for p in presets}))

    def test_stale_ready_record_is_not_reported_as_an_available_image(self):
        with patch.object(factory,'docker',return_value='sha256:core'):
            key,spec=factory.recipe(['d2'])
        factory.save(key,status='ready',tools=['d2'],core=spec['core'],image='missing',image_id='sha256:missing')
        with patch.object(factory,'docker',return_value='sha256:core'),patch.object(factory,'image_exists',return_value=False):
            self.assertEqual(factory.available(['d2'])['status'],'on_demand')

    def test_cancellation_during_quiet_install_removes_container_and_descriptor(self):
        import subprocess,sys
        from righaven import docker_runtime
        real_popen=subprocess.Popen
        cancel=threading.Event();children=[]
        def start(argv,**kwargs):
            self.assertIn('readonly',next(a for a in argv if 'dst=/environment-request.json' in a))
            self.assertNotIn('/credentials',' '.join(argv));self.assertNotIn('docker.sock',' '.join(argv))
            child=real_popen([sys.executable,'-c','import time; time.sleep(30)'],**kwargs);children.append(child)
            timer=threading.Timer(.1,cancel.set);timer.start();self.addCleanup(timer.cancel)
            return child
        with patch('righaven.runtime_settings.effective',return_value={'cpus':1,'memory_mib':512,'tmp_mib':128,'threads':1}),patch.object(factory,'docker',return_value='sha256:core'),patch.object(factory,'prune'),patch.object(factory,'image_exists',return_value=False),patch.object(factory,'candidates',return_value=[]),patch.object(docker_runtime,'host_path',side_effect=str),patch.object(docker_runtime,'remove') as remove,patch('righaven.environment_runtime.subprocess.Popen',side_effect=start):
            with self.assertRaisesRegex(RuntimeError,'annullata'):factory.ensure(['d2'],acquire=False,cancel=cancel)
            remove.assert_called_once()
        self.assertIsNotNone(children[0].poll())
        self.assertFalse(list(factory.folder().glob('*.request.json')))
        values=[factory.read(p.stem) for p in factory.folder().glob('*.json')]
        self.assertEqual(values[0]['status'],'failed')

    def test_preempted_install_removes_real_process_and_retries_without_reporting_failure(self):
        import subprocess,sys
        from righaven import docker_runtime
        from righaven.resource_slot import PreparationCancel
        real_popen=subprocess.Popen;yielded=threading.Event();children=[]
        def start(argv,**kwargs):
            child=real_popen([sys.executable,'-c','import time;time.sleep(30)'],**kwargs);children.append(child)
            timer=threading.Timer(.1,yielded.set);timer.start();self.addCleanup(timer.cancel)
            return child
        with patch('righaven.runtime_settings.effective',return_value={'cpus':1,'memory_mib':512,'tmp_mib':128,'threads':1}),patch.object(factory,'docker',return_value='sha256:core'),patch.object(factory,'prune'),patch.object(factory,'image_exists',return_value=False),patch.object(factory,'candidates',return_value=[]),patch.object(docker_runtime,'host_path',side_effect=str),patch.object(docker_runtime,'remove') as remove,patch('righaven.environment_runtime.subprocess.Popen',side_effect=start):
            with self.assertRaises(factory.PreparationDeferred):factory.ensure(['d2'],acquire=False,cancel=PreparationCancel(threading.Event(),yielded))
            remove.assert_called_once()
        self.assertIsNotNone(children[0].poll());self.assertFalse(list(factory.folder().glob('*.request.json')))
        record=next(factory.read(p.stem) for p in factory.folder().glob('*.json'))
        self.assertEqual(record['status'],'waiting_chat');self.assertEqual(record['error'],'')

    def test_unconfirmed_preparation_cleanup_is_explicit_and_never_treated_as_a_yield(self):
        import subprocess,sys
        from righaven import docker_runtime
        real_popen=subprocess.Popen;cancel=threading.Event();children=[]
        def start(argv,**kwargs):
            child=real_popen([sys.executable,'-c','import time;time.sleep(30)'],**kwargs);children.append(child)
            timer=threading.Timer(.1,cancel.set);timer.start();self.addCleanup(timer.cancel)
            return child
        with patch('righaven.runtime_settings.effective',return_value={'cpus':1,'memory_mib':512,'tmp_mib':128,'threads':1}),patch.object(factory,'docker',return_value='sha256:core'),patch.object(factory,'prune'),patch.object(factory,'image_exists',return_value=False),patch.object(factory,'candidates',return_value=[]),patch.object(docker_runtime,'host_path',side_effect=str),patch.object(docker_runtime,'remove',side_effect=RuntimeError('daemon unavailable')),patch('righaven.environment_runtime.subprocess.Popen',side_effect=start):
            with self.assertRaises(factory.PreparationCleanupError):factory.ensure(['d2'],acquire=False,cancel=cancel)
        self.assertIsNotNone(children[0].poll());self.assertFalse(list(factory.folder().glob('*.request.json')))

    def test_system_dependencies_are_selected_from_curated_catalog_only(self):
        from scripts.install_system_packages import packages
        repo=Path(__file__).resolve().parents[1]
        mapping=json.loads((repo/'config/toolkit/system-packages.json').read_text())
        self.assertEqual(set(mapping),{a['id'] for a in state.applications()})
        fixture=self.root/'toolkit-lock';fixture.mkdir();(fixture/'system-packages.json').write_text(json.dumps(mapping))
        self.assertEqual(packages(self.root,['d2','pandoc']),[])
        self.assertIn('g++',packages(self.root,['ffmpeg']))
        self.assertNotIn('g++',packages(self.root,['opengrep']))
        self.assertIn('libgtk-3-0',packages(self.root,['playwright']))
        with self.assertRaises(ValueError):packages(self.root,['made-up'])

    def test_two_installations_on_one_docker_host_cannot_overwrite_each_others_cache_tags(self):
        key='c'*64
        first=factory.image_tag(key)
        (self.root/'installation-id').write_text('other-installation')
        self.assertNotEqual(first,factory.image_tag(key))
        self.assertTrue(factory.image_tag(key).endswith(key))

    def test_managed_audio_skill_includes_decoder_but_cannot_reenable_a_global_disable(self):
        skills=[self.skill('skill-aubio'),self.skill('skill-ffmpeg')]
        with patch.object(profiles,'skill_inventory',return_value=skills):
            result=profiles.resolve_skills('owner',['skill-aubio'])
            self.assertEqual(result['tools'],['aubio','ffmpeg'])
            self.assertIn('skill-ffmpeg',result['skills'])
            skills[1].enabled=False
            with self.assertRaisesRegex(ValueError,'disabilitato'):profiles.resolve_skills('owner',['skill-aubio'])

    def test_rendering_browser_dependency_does_not_enable_automation(self):
        skills=[self.skill('skill-mermaid'),self.skill('skill-playwright',False)]
        with patch.object(profiles,'skill_inventory',return_value=skills):
            self.assertEqual(profiles.resolve_skills('owner',['skill-mermaid'])['tools'],['mermaid'])

    def test_still_image_verification_never_needs_a_video_decoder(self):
        from PIL import Image
        from scripts.acceptance import Case
        image=self.root/'proof.png';Image.new('RGBA',(32,24),(10,40,90,255)).save(image)
        with patch('scripts.acceptance.subprocess.check_output',side_effect=AssertionError('No FFprobe for PNG')):
            info=Case(self.root,'figcraft').probe(image)
        self.assertEqual(info['verification_engine'],'Pillow')
        self.assertEqual((info['streams'][0]['width'],info['streams'][0]['height']),(32,24))

    def test_inherited_installation_is_verified_before_extending_it(self):
        from scripts.install_righaven import existing_installation
        lock=json.loads((Path(__file__).resolve().parents[1]/'versions.lock.json').read_text())
        app=next(a for a in lock['applications'] if a['id']=='d2')
        binary=self.root/'bin/d2';binary.parent.mkdir();binary.write_bytes(b'fixture')
        row={'id':'d2','version':app['version'],'sha256':app['assets']['amd64']['sha256'],'binary':str(binary)}
        path=self.root/'installed.json';path.write_text(json.dumps([row]))
        self.assertEqual(existing_installation(self.root,lock,'amd64'),[row])
        row['sha256']='bad';path.write_text(json.dumps([row]))
        with self.assertRaisesRegex(ValueError,'catalog'):existing_installation(self.root,lock,'amd64')

    def test_expired_total_preparation_budget_does_not_start_another_container(self):
        with patch.object(factory,'docker',return_value='sha256:core'),patch.object(factory,'image_exists',return_value=False),patch.object(factory,'candidates',return_value=[]),patch('righaven.environment_runtime.subprocess.Popen') as popen:
            with self.assertRaisesRegex(TimeoutError,'esaurito'):factory.ensure(['d2'],acquire=False,deadline=0)
            popen.assert_not_called()
        self.assertEqual(next(factory.read(p.stem) for p in factory.folder().glob('*.json'))['status'],'failed')

    def test_preparation_details_include_the_current_dependency_build(self):
        key='d'*64
        child,_=factory.recipe(['ffmpeg'],identity='sha256:core')
        factory.save(key,status='installing',core='sha256:core',dependency_tools=['ffmpeg'])
        factory.save(child,status='installing',core='sha256:core',tools=['ffmpeg'])
        (factory.folder()/(child+'.log')).write_text('Compiling the shared decoder')
        details=factory.preparation_text(key)
        self.assertIn('Prerequisiti: ffmpeg',details)
        self.assertIn('Compiling the shared decoder',details)
        factory.save(child,status='ready')
        self.assertIn('già verificati',factory.preparation_text(key))

    def test_preparation_observation_distinguishes_shared_queue_from_dependency_output(self):
        key='d'*64;queued='e'*64
        child,_=factory.recipe(['ffmpeg'],identity='sha256:core')
        factory.save(key,status='installing',core='sha256:core',tools=['filmcraft','ffmpeg'],dependency_tools=['ffmpeg'])
        factory.save(child,status='installing',core='sha256:core',tools=['ffmpeg'],container='actual-preparer')
        factory.save(queued,status='queued',tools=['vectorcraft'])
        log=factory.folder()/(child+'.log');log.write_text('CC libavformat/first.o\n')
        first=factory.preparation_observation(key)
        self.assertTrue(first['prerequisite']);self.assertEqual(first['tools'],['ffmpeg'])
        self.assertIn('first.o',first['recent_output']);self.assertEqual(first['last_output_at'],log.stat().st_mtime)
        waiting=factory.preparation_observation(queued)
        self.assertEqual(waiting['phase'],'queued');self.assertEqual(waiting['waiting_on']['tools'],['ffmpeg'])
        self.assertIsNone(waiting['last_output_at']);self.assertEqual(waiting['log_bytes'],0)
        log.write_text('CC libavformat/second.o\nLD ffmpeg\n')
        second=factory.preparation_observation(key)
        self.assertGreater(second['log_bytes'],first['log_bytes']);self.assertEqual(second['recent_output'],'LD ffmpeg')
        factory.save(child,status='ready',container='')
        self.assertNotIn('waiting_on',factory.preparation_observation(queued))

    def test_reused_verified_image_does_not_retain_an_old_failed_attempt(self):
        key='c'*64
        factory.save(key,status='ready',tools=['d2'],image='prepared',image_id='sha256:ready',error='Old failure',failure={'message':'Old failure'})
        with patch.object(factory,'recipe',return_value=(key,{'tools':['d2']})),patch.object(factory,'image_exists',side_effect=lambda value:bool(value and value.get('status')=='ready')):
            result=factory.ensure(['d2'])
        self.assertEqual(result['error'],'');self.assertEqual(result['failure'],{})
        self.assertEqual(factory.read(key)['failure'],{})

    def test_a_queued_retry_does_not_present_an_old_failed_attempt_as_live_output(self):
        import os,time
        key='a'*64;factory.save(key,status='queued',tools=['calibre'])
        log=factory.folder()/(key+'.log');log.write_text('FAIL calibre from an earlier attempt')
        os.utime(log,(100,100));start=time.time()
        self.assertIn('FAIL calibre',factory.preparation_text(key))
        self.assertEqual(factory.preparation_text(key,since=start),'')
        observed=factory.preparation_observation(key,since=start)
        self.assertIsNone(observed['last_output_at']);self.assertEqual(observed['recent_output'],'')

    def test_native_frontmatter_delimiters_and_windows_bom_preserve_requirements(self):
        skill=self.skill('portable-method')
        base="""---
name: portable-method
description: "A---B method"
metadata:
  righaven-tools: [d2]
---
Instructions
"""
        for text in (base,'\ufeff'+base,base.replace('\n','\r\n')):
            (skill.skill_dir/'SKILL.md').write_text(text)
            self.assertEqual(profiles.skill_requirements(skill),['d2'])
