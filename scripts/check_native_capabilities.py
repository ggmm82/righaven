"""Gateway acceptance against the pinned, real RigHaven storage and Agent loader."""
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, '/app/backend')


def main():
    with tempfile.TemporaryDirectory(prefix='native-capabilities-') as folder:
        root = Path(folder)
        os.environ['RIGHAVEN_STATE'] = str(root / 'harness')
        os.environ['RIGHAVEN_HOME'] = str(root / 'home')
        config = root / 'config.yaml'
        config.write_text(Path('/app/backend/righaven/righaven.yaml').read_text())
        os.environ['RIGHAVEN_CONFIG_PATH'] = str(config)
        os.environ['RIGHAVEN_EXTENSIONS_CONFIG_PATH'] = str(root / 'extensions.json')
        (root / 'extensions.json').write_text('{}')
        from righaven_core.config import get_app_config
        from righaven_core.config.paths import get_paths
        from righaven_core.skills.storage import get_or_new_user_skill_storage
        from righaven_core.persistence.agents import get_agent_store
        from righaven.capability_policy import native_policy, stage_skills, install_managed_skills, migrate_existing_users
        from righaven.state import update_agent
        assert get_app_config().agents_api.enabled is True
        install_managed_skills()
        update_agent('blender', {'engine': 'inherit', 'enabled': False})
        one, two = 'native-policy-a', 'native-policy-b'
        for user in (one, two):
            get_paths().user_dir(user).mkdir(parents=True, exist_ok=True)
        migrate_existing_users()
        assert (get_paths().user_dir(one) / 'righaven-native-skills-migrated.json').is_file()
        assert 'blender' in native_policy(one)['blocked']
        store = get_or_new_user_skill_storage(one)
        # An unrelated user-authored skill must not hide the managed CLI skills.
        custom = store.get_custom_skill_dir('custom-method'); custom.mkdir(parents=True)
        (custom / 'SKILL.md').write_text('---\nname: custom-method\ndescription: A native custom method\n---\nUse a representative sample.\n')
        assert 'freecad' in native_policy(one)['allowed']
        store.set_skill_enabled_state('skill-blender', True)
        assert 'blender' in native_policy(one)['allowed']
        assert 'blender' in native_policy(two)['blocked']
        agents = get_agent_store()
        agents.create('cad-profile', {'name': 'cad-profile', 'skills': ['skill-workspace', 'skill-freecad']},
                      'Use native parametric CAD when pertinent.', user_id=one)
        selected = native_policy(one, 'cad-profile')
        assert selected['allowed'] == ['freecad']
        from righaven.skill_composition import environment_inventory
        from righaven.environments import profile
        from righaven_core.config.agents_config import load_agent_config
        discovered=environment_inventory(native_policy(one))
        assert any(item['name']=='cad-profile' and item['tools']==['freecad'] for item in discovered), discovered
        assert not environment_inventory(native_policy(two)), 'Another user discovered private environments'
        definition=load_agent_config('cad-profile',user_id=one)
        active=profile(one,definition)
        store.set_skill_enabled_state('skill-freecad',False)
        inactive=profile(one,definition)
        assert inactive['tools']==[] and 'skill-freecad' not in inactive['active_skills']
        assert inactive['revision']!=active['revision']
        assert not any(item['name']=='cad-profile' for item in environment_inventory(native_policy(one)))
        store.set_skill_enabled_state('skill-freecad',True)
        agents.create('no-skills', {'name': 'no-skills', 'skills': []}, '', user_id=one)
        assert native_policy(one, 'no-skills')['allowed'] == []
        agents.create('audio-profile',{'name':'audio-profile','skills':['skill-workspace','skill-soundcraft']},'',user_id=one)
        audio=native_policy(one,'audio-profile')
        assert audio['allowed']==['ffmpeg','soundcraft'],audio
        assert 'skill-ffmpeg' in audio['skill_sources']
        store.set_skill_enabled_state('skill-ffmpeg',False)
        try:native_policy(one,'audio-profile')
        except ValueError as error:assert 'disabilitato' in str(error)
        else:raise AssertionError('Audio dependencies re-enabled a global disable')
        store.set_skill_enabled_state('skill-ffmpeg',True)

        # The projection is real package content + references, not just names.
        target = stage_skills(selected, ['skill-freecad'], root / 'projection')
        assert (target / 'skill-freecad/SKILL.md').read_bytes() == Path(selected['skill_sources']['skill-freecad']).joinpath('SKILL.md').read_bytes()
        assert (target / 'skill-freecad/references/CLI-RECIPE.md').is_file()
        assert not (target / 'skill-blender').exists()
        # A dynamic role reuses only its chosen real native method packages;
        # an Agent/profile supplies authority, not a fixed profession or image.
        from righaven import projects
        from righaven.skill_composition import inventory,execution_skills,verify,verify_projection,execution_policy
        agents.create('method-profile',{'name':'method-profile','skills':['skill-workspace','skill-freecad','skill-blender','custom-method','skill-quality-review']},'',user_id=one)
        method_policy=native_policy(one,'method-profile')
        assert any(s['name']=='custom-method' for s in inventory(method_policy)['skills'])
        workspace=root/'project'
        projects.create_plan(workspace,'A result in an unanticipated domain',[])
        projects.sync_acceptance(workspace,['Create the editable result'])
        spec={'id':'responsible','title':'Responsabile del contributo','mission':'Risolvere il requisito',
              'expertise':['Metodo pertinente'],'procedure':['Confrontare il risultato'],
              'checks':['Riaprire il sorgente'],'deliverables':['Prodotto modificabile'],
              'skills':['custom-method'],'tools':['freecad']}
        projects.sync_project_context(workspace,[spec],skill_policy=method_policy)
        role=projects.read_project(workspace)['roles'][0];verify(role,method_policy)
        names=execution_skills({'skills':['skill-workspace']},role,method_policy)
        assert names==['skill-workspace','custom-method','skill-freecad'],names
        projection=stage_skills(method_policy,names,root/'method-projection')
        verify_projection(role,projection)
        assert not (projection/'skill-quality-review').exists()
        assert not (projection/'skill-blender').exists()
        task_policy=execution_policy(role,method_policy,role['tools'])
        assert task_policy['allowed']==['freecad'] and 'blender' in task_policy['blocked']
        store.set_skill_enabled_state('custom-method',False)
        try:verify(role,native_policy(one,'method-profile'))
        except ValueError:pass
        else:raise AssertionError('A disabled method remained executable after queuing')
        store.set_skill_enabled_state('custom-method',True)
        from righaven.tools import harness_skills
        from langchain_core.utils.function_calling import convert_to_openai_tool
        assert 'runtime' not in convert_to_openai_tool(harness_skills)['function']['parameters']['properties']
        from unittest.mock import patch
        with patch('righaven.capability_policy.runtime_policy',return_value=native_policy(one,'method-profile')):
            import json
            read=json.loads(harness_skills.func(runtime=None,name='custom-method'))
            assert read['content']==(custom/'SKILL.md').read_text()
            assert read['revision']==role['skill_bindings'][0]['revision']
            for reference in ('../SKILL.md','references/../../config.yaml'):
                try:harness_skills.func(runtime=None,name='custom-method',reference=reference)
                except ValueError:pass
                else:raise AssertionError('Skill reader escaped its native package')
        print('Native role composition OK: exact native packages, projected references, tool scope, model-tool schema, disabled method and safe discovery.')
        assert get_paths().user_dir(one) != get_paths().user_dir(two)
        print('Native capability policy OK: legacy migration, user isolation, Agent None/[]/selection and real package projection')


if __name__ == '__main__': main()
