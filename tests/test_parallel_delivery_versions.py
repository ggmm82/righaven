"""User-visible concurrency, explicit closure, stable release and rollback contracts."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from righaven import state,tool_versions,release_catalog,environment_runtime
from righaven.resource_budget import ResourceBudget,BudgetBusy
from righaven.worker_slots import WorkerSlots
from righaven.early_delivery import draft_handoff


class ParallelTests(unittest.TestCase):
    def test_two_workers_leave_control_and_terminal_reserves_and_third_waits(self):
        limits={'cpus':4,'memory_mib':4096,'threads':4,'tmp_mib':512,'max_workers':2}
        budget=ResourceBudget()
        with patch('righaven.runtime_settings.effective',return_value=limits):
            jobs=[budget.acquire(str(i),'worker',timeout=0) for i in range(2)]
            control=budget.acquire('coordinator','control',timeout=0)
            terminal=budget.acquire('terminal','terminal',timeout=0)
            self.assertLessEqual(sum(j['memory_mib'] for j in [*jobs,control,terminal]),4096)
            self.assertLessEqual(sum(j['cpus'] for j in [*jobs,control,terminal]),4)
            with self.assertRaises(BudgetBusy):budget.acquire('third','worker',timeout=0)
            budget.release('0')
            budget.acquire('third','worker',timeout=0)
            self.assertIn('1',budget.leases)

    def test_slot_limit_and_release_belong_to_individual_threads(self):
        limits={'cpus':4,'memory_mib':4096,'max_workers':2}
        slots=WorkerSlots();release=threading.Event();admitted=threading.Barrier(3)
        def work():
            self.assertTrue(slots.acquire(timeout=1));admitted.wait();release.wait(2);slots.release()
        with patch('righaven.runtime_settings.effective',return_value=limits):
            threads=[threading.Thread(target=work) for _ in range(2)]
            for thread in threads:thread.start()
            try:
                admitted.wait(2)
                self.assertFalse(slots.acquire(blocking=False))
                with self.assertRaisesRegex(RuntimeError,'posseduto'):slots.release()
            finally:
                release.set()
                for thread in threads:thread.join(2)
            self.assertFalse(slots.locked());self.assertTrue(slots.acquire());slots.release()

    def test_out_of_order_parallel_completion_keeps_newer_delivery_selected(self):
        from righaven import projects
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            projects.create_plan(root,'Independent contributions',[
                {'id':name,'agent':'workspace','goal':name,'depends_on':[]} for name in ('first','second')])
            started=threading.Event();second_finished=threading.Event();errors=[]
            def run(name):
                try:
                    output=root/'outputs/workspace'/name;output.mkdir(parents=True)
                    product=output/'result.txt';product.write_text(name)
                    def invoke(task,callback):
                        if name=='first':
                            started.set()
                            if not second_finished.wait(3):raise AssertionError('Other activity could not run concurrently')
                        return json.dumps({'ok':True,'environment':{'tools':['d2'],'version_names':{'d2':'v0.7.0'}},'verified_products':[str(product)],'handoff':{'output_files':[str(product)],'checks':[]}})
                    projects.execute_step(root,'workspace',name,name,invoke,purpose='delivery')
                except Exception as error:errors.append(error)
                finally:
                    if name=='second':second_finished.set()
            first=threading.Thread(target=run,args=('first',));first.start()
            self.assertTrue(started.wait(2))
            second=threading.Thread(target=run,args=('second',));second.start()
            first.join(5);second.join(5)
            self.assertFalse(first.is_alive());self.assertFalse(second.is_alive());self.assertEqual(errors,[])
            project=projects.read_project(root)
            self.assertEqual(project['product_path'],'/mnt/user-data/outputs/workspace/second/result.txt')
            self.assertEqual(len(project['results']),2)
            self.assertEqual((root/'outputs/workspace/first/result.txt').read_text(),'first')
            from righaven.project_skills import read_document
            raw=json.loads((root/'.righaven-project/project.json').read_text())
            selected=next(s for s in raw['steps'] if s['id']=='second')['attempts'][-1]
            self.assertEqual(json.loads(read_document(root,selected['tool_environment'])),{'d2':'v0.7.0'})

    def test_private_credentials_use_compare_and_swap_for_rotating_tokens(self):
        from righaven.credential_sessions import CredentialSession
        with tempfile.TemporaryDirectory() as temporary,patch.object(state,'STATE',Path(temporary)):
            source=state.credential_dir('codex');(source/'auth.json').write_text('{"account":"old"}')
            first=CredentialSession('codex',Path(temporary)/'first')
            second=CredentialSession('codex',Path(temporary)/'second')
            (first.directory/'auth.json').write_text('{"account":"new"}')
            (second.directory/'auth.json').write_text('{"account":"stale"}')
            first.close();second.close()
            self.assertEqual(json.loads((source/'auth.json').read_text()),{'account':'new'})
            self.assertFalse(first.directory.exists());self.assertFalse(second.directory.exists())


class EarlyDeliveryTests(unittest.TestCase):
    def test_saved_work_has_honest_unverified_checks_and_keeps_original_handoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'draft.svg').write_text('<svg/>')
            (root/'handoff.json').write_text('{"incomplete":true}')
            (root/'empty.png').touch();(root/'temp.tmp').write_text('temporary')
            result=draft_handoff(root)
            self.assertEqual(result['checks'][0]['status'],'not_run')
            self.assertEqual(result['output_files'],[str(root/'draft.svg')])
            self.assertEqual(result['delivery']['files'][0]['reopen']['status'],'not_run')
            self.assertEqual(json.loads((root/'work/handoff-before-early-delivery.json').read_text()),{'incomplete':True})

    def test_worker_finalizer_can_close_missing_handoff_without_claiming_complete_product(self):
        from righaven.run_agent import finalize_saved
        with tempfile.TemporaryDirectory() as temporary:
            workspace=Path(temporary);output=workspace/'outputs/workspace/rh-job-123456789abc';output.mkdir(parents=True)
            (output/'draft.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><rect width="10" height="10"/></svg>')
            job={'agent':'workspace','run_id':output.name,'engine':'openai','purpose':'delivery','requirements':{}}
            result=finalize_saved(job,output,workspace,early=True)
            self.assertTrue(result['ok']);self.assertTrue(result['early_delivery'])
            self.assertEqual(result['delivery_record']['technical_status'],'needs_revision')
            self.assertEqual(result['delivery_record']['quality_status'],'not_reviewed')
            self.assertEqual(result['handoff']['checks'][0]['status'],'not_run')

    def test_review_only_batch_does_not_authorize_new_production(self):
        from righaven.completion_policy import production_call
        def call(items):return {'name':'harness_delegate_batch','args':{'assignments_json':json.dumps(items)}}
        self.assertFalse(production_call(call([{'purpose':'review'},{'purpose':'review'}])))
        self.assertTrue(production_call(call([{'purpose':'review'},{'purpose':'delivery'}])))

    def test_deliver_now_blocks_new_assignments_and_completion_nudges_until_resume(self):
        from righaven import projects
        from righaven.completion_policy import needs_continuation
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);projects.create_plan(root,'A project',[])
            projects.request_project_delivery(root)
            project=projects.read_project(root)
            self.assertFalse(needs_continuation(project))
            with self.assertRaisesRegex(ValueError,'Consegna ora'):projects.assert_user_allows_work(project)
            projects.assert_user_allows_work(project,allow_delivery=True)
            projects.set_user_control(root,False)
            projects.assert_user_allows_work(projects.read_project(root))

    def test_empty_staging_and_symbolic_link_do_not_become_delivery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'outside').mkdir();output=root/'output';output.mkdir()
            (root/'outside/private.txt').write_text('private')
            (output/'linked.txt').symlink_to(root/'outside/private.txt')
            with self.assertRaisesRegex(ValueError,'Nessun prodotto'):draft_handoff(output)


class VersionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        patcher=patch.object(state,'STATE',Path(temporary.name));patcher.start();self.addCleanup(patcher.stop)
        self.app=copy.deepcopy(tool_versions.builtins()['d2'])

    def register(self,version):
        app=copy.deepcopy(self.app);app['version']=version
        bundle={'app':app,'files':{}};revision=tool_versions.identifier(bundle)
        state.atomic_json(tool_versions.directory()/(revision+'.json'),{'id':revision,'state':'ready','bundle':bundle,'updated_at':'now'})
        return revision

    def test_updated_release_discovers_actual_commands_without_relabelling_removed_capabilities(self):
        from scripts.apply_tool_versions import refresh_capabilities
        base={'applications':[{'id':'d2','version':'old','groups':[{'goal':'Existing method','commands':['kept','removed'],'evidence':'registered'}]}]}
        app={'id':'d2','version':'new','executable':'d2-cli','registry_args':['commands'],'repository':'https://example.invalid/d2'}
        with patch('scripts.apply_tool_versions.subprocess.check_output',return_value='kept description\nadded description\n'):
            entry=refresh_capabilities(base,{'d2':{'app':app}})['applications'][0]
        self.assertEqual(entry['version'],'new');self.assertEqual(entry['catalog_ids'],['added','kept'])
        self.assertEqual(entry['groups'][0]['commands'],['kept'])
        self.assertEqual(entry['groups'][1]['commands'],['added'])

    def test_official_appimage_discovery_handles_changing_build_numbers(self):
        base=copy.deepcopy(tool_versions.builtins()['musescore'])
        asset={'name':'MuseScore-RigHaven-4.8.0.269999001-x86_64.AppImage','browser_download_url':base['repository']+'/releases/download/v4.8.0/new.AppImage','digest':'sha256:'+'a'*64,'size':123}
        with patch.object(release_catalog,'data',return_value={'tag_name':'v4.8.0','assets':[asset]}):
            result=release_catalog.candidate(base,'v4.8.0','amd64')
        self.assertEqual(result['app']['assets']['amd64']['name'],asset['name'])
        self.assertEqual(result['app']['assets']['amd64']['sha256'],'a'*64)

    def test_latest_excludes_prereleases_even_if_tagged_latest(self):
        app={'id':'playwright','repository':'https://github.com/microsoft/playwright'}
        metadata={'versions':{v:{} for v in ['1.9.0','1.10.0','2.0.0-beta.1','2.0.0-dev.1']},'dist-tags':{'latest':'2.0.0-beta.1'}}
        with patch.object(release_catalog,'data',return_value={'version':'2.0.0-beta.1'}),patch.object(release_catalog,'read',return_value=json.dumps(metadata).encode()):
            self.assertEqual(release_catalog.latest(app),'1.10.0')
        for version in ('1.1.0rc1','1.1.0a1','1.1.0b2','v2.0.0-preview.1','2.0.0-SNAPSHOT','3.0.0-canary.1','3.0.0-next.4','6.3.0-M1'):
            self.assertTrue(release_catalog.prerelease(version),version)
        self.assertFalse(release_catalog.prerelease('2025.7.post1'))

    def test_latest_snapshots_an_exact_verified_revision_and_old_pins_keep_working(self):
        old=self.register('v0.8.0');new=self.register('v0.9.0')
        tool_versions.activate('d2','latest')
        with patch.object(tool_versions,'latest_version',return_value='v0.9.0'):
            selected=tool_versions.resolved({'d2':'latest'},wait=True)
        self.assertEqual(selected,{'d2':new})
        tool_versions.activate('d2',old)
        self.assertEqual(selected,{'d2':new})
        self.assertEqual(tool_versions.selections(tools=['d2']),{'d2':old})
        self.assertEqual(tool_versions.resolved({'d2':'latest'}),{'d2':new})

    def test_unused_version_changes_do_not_invalidate_environment_and_rollback_reuses_key(self):
        old=self.register('v0.8.0');new=self.register('v0.9.0')
        kwargs={'core':'sha256:stable','identity':'installation'}
        a,_=environment_runtime.recipe(['d2'],versions={'d2':old},**kwargs)
        b,_=environment_runtime.recipe(['d2'],versions={'d2':new},**kwargs)
        unrelated,_=environment_runtime.recipe(['d2'],versions={'d2':old,'blender':'b'*64},**kwargs)
        self.assertNotEqual(a,b);self.assertEqual(a,unrelated)
        self.assertEqual(a,environment_runtime.recipe(['d2'],versions={'d2':old},**kwargs)[0])
        default,_=environment_runtime.recipe(['d2'],**kwargs)
        self.assertNotEqual(default,a)

    def test_imported_provider_pin_is_kept_even_when_the_active_model_uses_another_provider(self):
        with patch('righaven.environments.preferences',return_value={'profile':{'tool_versions':{'provider-agy':'a'*64}}}):
            self.assertEqual(tool_versions.selections('owner','profile',['d2'],'deepseek'),{'provider-agy':'a'*64})
        tool_versions.activate('provider-agy','latest')
        self.assertEqual(tool_versions.selections(tools=['d2'],engine='deepseek'),{})

    def test_runtime_latest_reuses_verified_pointer_without_network_until_explicit_refresh(self):
        old=self.register('v0.8.0');new=self.register('v0.9.0')
        state.atomic_json(tool_versions.directory()/'latest.json',{'d2':{'revision':old,'version':'v0.8.0','checked_at':0}})
        with patch.object(tool_versions,'latest_version',return_value='v0.9.0') as latest:
            self.assertEqual(tool_versions.resolved({'d2':'latest'},wait=True,refresh=False),{'d2':old})
            latest.assert_not_called()
            self.assertEqual(tool_versions.resolved({'d2':'latest'},wait=True,refresh=True),{'d2':new})
            latest.assert_called_once()

    def test_builtin_codex_reset_restores_the_preserved_global_binary_without_reinstalling_apps(self):
        from scripts import apply_tool_versions as installer
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);bin_dir=root/'bin';bin_dir.mkdir();npm=root/'npm'
            binary=npm/'@openai/codex/bin/codex.js';binary.parent.mkdir(parents=True);binary.write_text('fixture global CLI')
            app_file=root/'existing-application';app_file.write_text('unchanged')
            (root/'catalog.lock.json').write_text(json.dumps({'cli_runtimes':{'codex':'custom'}}))
            (bin_dir/'codex').symlink_to(root/'custom-prefix/codex')
            with patch.object(installer,'ROOT',root),patch.object(installer,'BIN',bin_dir),patch.object(installer.subprocess,'check_output',side_effect=[str(npm),'codex-cli builtin-test-version']):
                installer.reset_providers({'provider-codex':{'id':'provider-codex','version':'builtin-test-version'}})
            self.assertEqual((bin_dir/'codex').resolve(),binary)
            self.assertEqual(app_file.read_text(),'unchanged')
            self.assertEqual(json.loads((root/'catalog.lock.json').read_text())['cli_runtimes']['codex'],'builtin-test-version')

    def test_application_readiness_is_independent_of_a_previously_selected_provider(self):
        spec={'tools':['d2'],'core':'sha256:base'}
        old={'tools':['d2'],'core':spec['core'],'versions':{'provider-agy':'a'*64}}
        self.assertTrue(environment_runtime.matching_versions(old,spec))
        self.assertTrue(environment_runtime.matching_versions(old,spec,True,reset_providers=True))
        old['versions']['d2']='b'*64
        self.assertFalse(environment_runtime.matching_versions(old,spec,True,reset_providers=True))

    def test_provider_reset_cannot_reuse_an_image_with_an_old_custom_cli(self):
        old={'tools':['d2'],'versions':{'provider-agy':'a'*64}}
        self.assertFalse(environment_runtime.matching_versions(old,{'tools':['d2']},subset=True))
        self.assertTrue(environment_runtime.matching_versions(old,{'tools':['d2'],'versions':{'provider-agy':'b'*64}},subset=True))
        self.assertFalse(environment_runtime.matching_versions(old,{'tools':['d2'],'versions':{'provider-codex':'b'*64}},subset=True))

    def test_failed_or_modified_release_cannot_replace_ready_default(self):
        old=self.register('v0.8.0');new=self.register('v0.9.0');tool_versions.activate('d2',old)
        path=tool_versions.directory()/(new+'.json');row=json.loads(path.read_text());row['state']='failed';state.atomic_json(path,row)
        with self.assertRaisesRegex(ValueError,'Verifica'):tool_versions.activate('d2',new)
        row['bundle']['app']['version']='tampered';state.atomic_json(path,row)
        with self.assertRaisesRegex(ValueError,'modificato'):tool_versions.read(new)
        self.assertEqual(tool_versions.defaults()['d2'],old)

    def test_rebuild_preserves_exact_dependency_plan_without_accounts(self):
        from righaven.environment_portability import rebuild_files
        revision=self.register('v0.8.0')
        with tempfile.TemporaryDirectory() as temporary:
            rebuild_files(Path(temporary)/'recipe',['d2'],{'d2':revision})
            request=json.loads((Path(temporary)/'recipe/request.json').read_text())
            self.assertEqual(request['versions'],{'d2':revision})
            self.assertEqual(tool_versions.identifier(request['version_packages']['d2']),revision)
            self.assertFalse(any('credential' in str(p) for p in (Path(temporary)/'recipe').rglob('*')))
