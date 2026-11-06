"""Editors share native environment profiles and never turn keep-ready into a running process."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock,patch
from righaven import state,editor_documents as documents,editor_profiles,environments,environment_preparation
try:
    from righaven import environment_routes
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    environment_routes=None


class Fixture:
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        for mocked in (patch.object(state,'STATE',self.root/'state'),patch.object(environments,'preferences_path',side_effect=lambda user:self.root/(user+'-preferences.json'))):
            mocked.start();self.addCleanup(mocked.stop)
        self.workspace=self.root/'workspace';(self.workspace/'outputs').mkdir(parents=True)
        (self.workspace/'outputs/program.py').write_text('print(1)')
        self.document=documents.start(self.workspace,'/mnt/user-data/outputs/program.py','jupyter',['jupyter'])


class EditorProfileState(Fixture,unittest.TestCase):
    def test_software_identity_survives_session_close_without_pinning_on_demand_forever(self):
        name='editor-jupyter-fixture';environments.set_deployment('owner',name,'on_demand',True,tool_versions={'jupyter':'builtin'})
        editor_profiles.mark('owner',name,'jupyter',{'jupyter':'builtin'})
        editor_profiles.bind(self.workspace,self.document['id'],['jupyter'],name)
        editor_profiles.remember(self.workspace,self.document['id'],['jupyter'],'owner',{'id':'e'*64},'a'*64)
        saved=documents.metadata(self.workspace,self.document['id'],['jupyter'])
        self.assertEqual(saved['environment_profile'],name);self.assertEqual(saved['runtime_environment_id'],'e'*64);self.assertEqual(saved['revision'],0)
        prefs=environments.preferences('owner')[name]
        self.assertEqual(prefs['editors'],[]);self.assertEqual(prefs['mode'],'on_demand')
        self.assertEqual(environment_preparation.read('owner',name)['ready_id'],'e'*64)
        kept=environments.set_deployment('owner',name,'preload',False,tool_versions={'jupyter':'builtin'})
        self.assertEqual(kept['editor_for'],'jupyter');self.assertEqual(kept['editors'],['jupyter'])
        self.assertEqual(kept['editor_software']['jupyter']['interface_id'],'a'*64)
        released=environments.set_deployment('owner',name,'on_demand',True,tool_versions={'jupyter':'builtin'})
        self.assertEqual(released['editors'],[]);self.assertEqual(released['editor_software'],kept['editor_software'])
        self.assertEqual(documents.metadata(self.workspace,self.document['id'],['jupyter'])['environment_profile'],name)

    def test_editor_adapters_use_the_private_working_directory_and_read_only_capability_contract(self):
        from righaven.editor_runtime import cli_arguments
        with patch('righaven.docker_runtime.runtime_arguments',return_value=['--mount','readonly-code']),patch('righaven.docker_runtime.mount',side_effect=lambda source,target,readonly=False:f'{target}:{readonly}'):
            args=cli_arguments(self.root,['duckdb','jupyter'])
        self.assertIn('readonly-code',args);self.assertIn('/job.json:True',args)
        self.assertIn('RIGHAVEN_WORKSPACE_ROOT=/workspace/output',args)
        self.assertEqual(json.loads((self.root/'capabilities.json').read_text()),{'capability_policy':{'allowed':['duckdb','jupyter']}})


@unittest.skipIf(environment_routes is None,'Requires native Gateway SDK')
class EditorProfileRegistration(Fixture,unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        super().setUp();self.agents=[]
        def resolved(user,names,**kwargs):return {'skills':names,'tools':['jupyter'] if 'skill-jupyter' in names else [],'disabled':[]}
        async def create(value,request,create):
            self.assertTrue(create)
            self.agents.append(SimpleNamespace(name=value.name,description=value.purpose,skills=value.skills,display_name=value.display_name,soul=value.instructions))
            environments.set_deployment('owner',value.name,value.mode,value.ephemeral,value.preload_tools,value.tool_versions)
            return {'name':value.name}
        self.creation=AsyncMock(side_effect=create)
        for mocked in (patch.object(environment_routes,'native_agents',new=AsyncMock(side_effect=lambda request:SimpleNamespace(agents=self.agents).agents)),patch.object(environment_routes,'write_definition',new=self.creation),patch.object(environments,'resolve_skills',side_effect=resolved)):
            mocked.start();self.addCleanup(mocked.stop)

    async def test_registers_one_ordinary_environment_and_reuses_it_for_other_drafts(self):
        name=await editor_profiles.ensure(self.workspace,self.document['id'],'owner',object(),['jupyter'])
        self.assertTrue(name.startswith('editor-jupyter-'));self.assertEqual(self.creation.await_count,1)
        self.assertEqual(environments.preferences('owner')[name]['mode'],'on_demand')
        self.assertEqual(environments.preferences('owner')[name]['tool_versions'],{'jupyter':'builtin'})
        second=documents.open_with(self.workspace,self.document['id'],'jupyter',['jupyter'])
        self.assertNotIn('environment_profile',second)
        self.assertEqual(await editor_profiles.ensure(self.workspace,second['id'],'owner',object(),['jupyter']),name)
        self.assertEqual(self.creation.await_count,1)
        self.agents[0].skills=[]
        with self.assertRaisesRegex(ValueError,'no longer enables'):await editor_profiles.ensure(self.workspace,self.document['id'],'owner',object(),['jupyter'])
        self.assertEqual(self.creation.await_count,1)

    async def test_reuses_a_prepared_user_profile_without_overwriting_configuration(self):
        self.agents.append(SimpleNamespace(name='data',description='My laboratory',skills=['skill-jupyter'],display_name='Data',soul='User instructions'))
        environments.set_deployment('owner','data','preload',False,tool_versions={'jupyter':'builtin'})
        with patch('righaven.environment_runtime.available',return_value={'status':'ready'}):
            name=await editor_profiles.ensure(self.workspace,self.document['id'],'owner',object(),['jupyter'])
        self.assertEqual(name,'data');self.creation.assert_not_awaited()
        self.assertNotIn('editor_for',environments.preferences('owner')['data'])
        with self.assertRaisesRegex(ValueError,'disabled'):await editor_profiles.ensure(self.workspace,self.document['id'],'owner',object(),[])

    async def test_recovery_checks_thread_ownership_and_does_not_start_any_runtime(self):
        home=self.root/'native/owner/threads';(home/'conversation').mkdir(parents=True);(home/'foreign').mkdir()
        documents.start(self.workspace,'/mnt/user-data/outputs/program.py','text',[])
        paths=SimpleNamespace(user_dir=lambda user:self.root/'native'/user,sandbox_user_data_dir=lambda thread,user_id:self.workspace)
        store=SimpleNamespace(check_access=AsyncMock(side_effect=lambda thread,user,require_existing=False:thread=='conversation' and user=='owner'))
        with patch('righaven_core.config.paths.get_paths',return_value=paths),patch('app.gateway.deps.get_thread_store',return_value=store),patch('righaven.editor_runtime.start') as start:
            recovered=await editor_profiles.recover('owner',object(),['jupyter'])
        self.assertEqual(len(recovered['environments']),1);self.assertFalse(recovered['limited']);start.assert_not_called()
        self.assertEqual(self.creation.await_count,1)

    async def test_unprepared_generic_profile_is_not_mistaken_for_a_ready_editor_environment(self):
        self.agents.append(SimpleNamespace(name='data',description='Laboratory',skills=['skill-jupyter'],display_name='Data',soul=''))
        environments.set_deployment('owner','data','preload',False,tool_versions={'jupyter':'builtin'})
        with patch('righaven.environment_runtime.available',return_value={'status':'on_demand'}):
            name=await editor_profiles.ensure(self.workspace,self.document['id'],'owner',object(),['jupyter'])
        self.assertNotEqual(name,'data');self.assertEqual(self.creation.await_count,1)

    async def test_ready_when_needed_profile_is_reused_without_forcing_preload(self):
        self.agents.append(SimpleNamespace(name='data',description='Laboratory',skills=['skill-jupyter'],display_name='Data',soul=''))
        environments.set_deployment('owner','data','on_demand',False,tool_versions={'jupyter':'builtin'})
        with patch('righaven.environment_runtime.available',return_value={'status':'ready'}):
            name=await editor_profiles.ensure(self.workspace,self.document['id'],'owner',object(),['jupyter'])
        self.assertEqual(name,'data');self.creation.assert_not_awaited()
        self.assertEqual(environments.preferences('owner')['data']['mode'],'on_demand')

    async def test_runtime_honors_all_configured_programs_and_keeps_the_primary_release_frozen(self):
        from righaven import editor_versions
        document={**self.document,'environment_profile':'data'}
        with patch('righaven_core.config.agents_config.load_agent_config',return_value=SimpleNamespace(skills=['skill-jupyter','skill-duckdb'])),patch.object(environments,'resolve_skills',return_value={'tools':['duckdb','jupyter']}),patch('righaven.capability_policy.native_policy',return_value={'allowed':['duckdb','jupyter']}),patch('righaven.capability_policy.require_tools'),patch('righaven.tool_versions.software_selections',return_value={'duckdb':'builtin','jupyter':'a'*64}),patch('righaven.tool_versions.resolved',return_value={}) as resolve,patch('righaven.environment_runtime.ensure',return_value={'id':'e'*64}) as prepare:
            editor_versions.software(document,'jupyter','owner',None,user='owner')
        self.assertEqual(prepare.call_args.args[0],['duckdb','jupyter'])
        self.assertEqual(resolve.call_args.args[0]['jupyter'],'builtin')
        self.assertEqual(resolve.call_args.args[0]['duckdb'],'builtin')
        self.assertFalse(resolve.call_args.kwargs['refresh'])

    async def test_builtin_editor_prepares_with_the_real_version_resolver(self):
        from righaven import editor_versions
        document={**self.document,'environment_profile':'data'}
        with patch('righaven_core.config.agents_config.load_agent_config',return_value=SimpleNamespace(skills=['skill-jupyter'])),patch.object(environments,'resolve_skills',return_value={'tools':['jupyter']}),patch('righaven.capability_policy.native_policy',return_value={'allowed':['jupyter']}),patch('righaven.capability_policy.require_tools'),patch('righaven.tool_versions.software_selections',return_value={}),patch('righaven.environment_runtime.ensure',return_value={'id':'e'*64}) as prepare:
            editor_versions.software(document,'jupyter','owner',None,user='owner')
        self.assertEqual(prepare.call_args.kwargs['versions'],{})

    async def test_original_single_program_image_cannot_hide_a_new_configured_dependency(self):
        from righaven import editor_versions
        document={**self.document,'environment_profile':'data','runtime_environment_id':'e'*64}
        image={'id':'e'*64,'tools':['jupyter'],'status':'ready','tool_version_names':{'jupyter':self.document['editor_version']}}
        with patch('righaven_core.config.agents_config.load_agent_config',return_value=SimpleNamespace(skills=['skill-jupyter','skill-duckdb'])),patch.object(environments,'resolve_skills',return_value={'tools':['duckdb','jupyter']}),patch('righaven.capability_policy.native_policy',return_value={'allowed':['duckdb','jupyter']}),patch('righaven.capability_policy.require_tools'),patch('righaven.tool_versions.software_selections',return_value={}),patch('righaven.tool_versions.resolved',return_value={}),patch('righaven.environment_runtime.read',return_value=image),patch('righaven.environment_runtime.image_exists',return_value=True),patch('righaven.environment_runtime.claim_environment') as claim,patch('righaven.environment_runtime.ensure',return_value={'id':'f'*64}) as prepare:
            editor_versions.software(document,'jupyter','owner',None,user='owner')
        claim.assert_not_called();self.assertEqual(prepare.call_args.args[0],['duckdb','jupyter']);self.assertEqual(prepare.call_args.kwargs['prefer'],'e'*64)

