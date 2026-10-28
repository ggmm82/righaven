import json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from righaven import projects
from righaven.project_skills import load_compiled,validate_roles
from righaven.skill_composition import bind,execution_skills,execution_policy,inventory,package_revision,verify,verify_projection
from righaven.run_agent import verify_project_context


class SkillCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.sources={}
        for name,tools in [('method-a',[]),('method-b',['soundcraft'])]:
            folder=self.root/name;folder.mkdir();(folder/'references').mkdir()
            (folder/'SKILL.md').write_text('---\nname: '+name+'\ndescription: General reusable method\nmetadata:\n  righaven-tools: '+json.dumps(tools)+'\n---\nUse evidence, not assumptions.\n')
            (folder/'references/QUALITY.md').write_text('Reopen and compare the exact result.')
            self.sources[name]=str(folder)
        self.policy={'source':'righaven_core','allowed':['soundcraft','ffmpeg','blender'],'blocked':[],
                     'skill_names':[*self.sources,'skill-workspace','skill-soundcraft','skill-ffmpeg','skill-blender'],
                     'skill_sources':self.sources,'extra_skills':['method-a','method-b']}
        self.spec={'id':'unexpected-domain','title':'Responsabile del contributo','mission':'Risolvere il requisito',
                   'expertise':['Competenza pertinente al brief'],'procedure':['Eseguire la prova decisiva'],
                   'checks':['Confrontare il risultato reale'],'deliverables':['Risultato modificabile'],
                   'tools':[],'skills':['method-a']}
        projects.create_plan(self.root,'Prodotto richiesto',[]);projects.sync_acceptance(self.root,['Richiesta originale'])

    def compile(self):
        projects.sync_project_context(self.root,[self.spec],skill_policy=self.policy)
        return projects.read_project(self.root)['roles'][0]

    def test_method_only_role_needs_no_native_app_and_does_not_load_all_profile_skills(self):
        role=self.compile();self.assertEqual(role['tools'],[])
        self.assertEqual(execution_skills({'skills':['skill-workspace','skill-blender']},role,self.policy),['skill-workspace','method-a'])
        self.assertIn('method-a',load_compiled(self.root,role))
        from righaven.environment_runtime import recipe
        self.assertEqual(recipe(role['tools'],identity='sha256:core'),recipe([],identity='sha256:core'))

    def test_selected_method_resolves_cli_dependencies_but_never_reenables_a_disabled_tool(self):
        self.spec['skills']=['method-b'];role=self.compile()
        self.assertEqual(role['tools'],['ffmpeg','soundcraft'])
        with projects.locked(self.root) as folder:self.assertEqual(projects.load(folder,self.root)['role_specs'][0]['tools'],[])
        scoped=execution_policy(role,self.policy,role['tools'])
        self.assertNotIn('blender',scoped['allowed']);self.assertIn('blender',scoped['blocked'])
        self.assertEqual(scoped['available_on_request'],['blender'])
        self.policy['allowed'].remove('ffmpeg')
        with self.assertRaises(ValueError):self.compile()

    def test_versions_cover_references_and_disable_or_edit_requires_recompilation(self):
        first=self.compile();verify(first,self.policy)
        self.policy['skill_names'].remove('method-a')
        with self.assertRaises(ValueError):verify(first,self.policy)
        with self.assertRaises(ValueError):self.compile()
        self.policy['skill_names'].append('method-a')
        Path(self.sources['method-a'],'references/QUALITY.md').write_text('A newly reviewed method')
        with self.assertRaises(ValueError):verify(first,self.policy)
        second=self.compile();self.assertNotEqual(first['version'],second['version'])
        self.assertNotEqual(first['skill_bindings'],second['skill_bindings'])
        verify(second,self.policy);load_compiled(self.root,first)

    def test_internal_memory_and_learning_updates_preserve_binding_without_new_authority(self):
        first=self.compile()
        projects.sync_project_context(self.root,memory={'decision':'Revised with evidence'})
        second=projects.read_project(self.root)['roles'][0]
        self.assertEqual(first['skill_bindings'],second['skill_bindings'])
        self.assertNotEqual(first['version'],second['version'])
        spec=validate_roles([{**self.spec,'skills':['method-b']}],projects.applications())[0]
        with self.assertRaises(ValueError):bind(spec,previous=second)

    def test_projection_verified_in_worker_including_references_and_scope_integrity(self):
        role=self.compile();projection=self.root/'projection';projection.mkdir()
        shutil.copytree(self.sources['method-a'],projection/'method-a')
        verify_projection(role,projection);verify_project_context({'role':role},self.root,projection)
        (projection/'method-a/references/QUALITY.md').write_text('Changed after compilation')
        with self.assertRaises(ValueError):verify_project_context({'role':role},self.root,projection)
        changed={**role,'tools':['blender']}
        with self.assertRaises(ValueError):load_compiled(self.root,changed)

    def test_catalog_is_authorized_compact_metadata_not_installation_or_bulk_prompt(self):
        with patch('righaven.skill_composition.package_revision',side_effect=AssertionError('No package hashing for catalog')):
            value=inventory(self.policy,limit=1)
        self.assertEqual(len(value['skills']),1);self.assertTrue(value['more'])
        self.assertNotIn('content',value['skills'][0]);self.assertEqual(inventory(self.policy,'method-b')['total'],1)
        self.assertEqual(inventory({**self.policy,'skill_sources':{}},'method-a')['total'],0)

    def test_malformed_names_external_references_and_incomplete_bindings_are_rejected(self):
        for names in [['../other'],[{}],['method-a','method-a']]:
            with self.assertRaises(ValueError):validate_roles([{**self.spec,'skills':names}],projects.applications())
        role=self.compile()
        with self.assertRaises(ValueError):verify({**role,'skill_bindings':[]},self.policy)
        folder=Path(self.sources['method-a']);(folder/'references/outside').symlink_to(self.root/'method-b/SKILL.md')
        with self.assertRaises(ValueError):package_revision(folder)

    def test_legacy_roles_keep_compatibility_until_explicitly_recompiled(self):
        legacy={**self.spec};legacy.pop('skills')
        self.assertEqual(bind(legacy,self.policy),legacy)
        self.assertEqual(execution_skills({'skills':['skill-workspace']},legacy,self.policy),['skill-workspace','method-a','method-b'])

    def test_compiler_format_upgrade_keeps_old_immutable_role_files_readable(self):
        from righaven.project_skills import compile_role,scoped_file
        from righaven.acceptance import fingerprint
        legacy={**self.spec,'inputs':[],'risks':[]};legacy.pop('skills')
        acceptance={'hash':'old-request'};memory={}
        old_version=fingerprint({'spec':legacy,'request_hash':'old-request','memory':memory,'tools':[],'experience':None})
        old_skill=scoped_file(self.root,f'roles/{legacy["id"]}/{old_version}/SKILL.md','Previous compiler content')
        old_role={**legacy,'version':old_version,'skill':old_skill}
        updated=compile_role(self.root,legacy,acceptance,memory,projects.applications())
        self.assertNotEqual(updated['version'],old_version)
        self.assertEqual(load_compiled(self.root,old_role),'Previous compiler content')
        self.assertIn('Skill native selezionate',load_compiled(self.root,updated))

    def test_automatic_cli_and_protocol_packages_are_versioned_and_entire_projection_is_checked(self):
        for name in ('skill-workspace','skill-soundcraft','skill-ffmpeg'):
            path=self.root/name;path.mkdir()
            (path/'SKILL.md').write_text('---\nname: '+name+'\ndescription: Native package fixture\n---\nA verified procedure.\n')
            self.policy['skill_sources'][name]=str(path)
        self.spec['skills']=['method-b'];role=self.compile()
        self.assertEqual({b['name'] for b in role['package_bindings']},{'skill-workspace','skill-soundcraft','skill-ffmpeg'})
        projection=self.root/'projection';projection.mkdir()
        for binding in [*role['skill_bindings'],*role['package_bindings']]:
            shutil.copytree(self.policy['skill_sources'][binding['name']],projection/binding['name'])
        job={'role':role,'environment':{'skill_revision':package_revision(projection,require_skill=False)}}
        verify_project_context(job,self.root,projection)
        (projection/'unexpected-helper.txt').write_text('Not in the Gateway projection')
        with self.assertRaises(ValueError):verify_project_context(job,self.root,projection)
        Path(self.policy['skill_sources']['skill-soundcraft'],'SKILL.md').write_text('Changed CLI procedure')
        with self.assertRaises(ValueError):verify(role,self.policy)
        updated=self.compile();self.assertNotEqual(role['version'],updated['version'])

    def test_saved_output_recovery_checks_task_authority_and_methods_not_project_catalog_equality(self):
        from righaven.skill_composition import verify_recovery
        self.spec['skills']=['method-b'];role=self.compile()
        scoped=execution_policy(role,self.policy,role['tools'])
        verify_recovery(scoped,self.policy,role)
        with self.assertRaises(ValueError):verify_recovery(scoped,{**self.policy,'allowed':['soundcraft']},role)
        with self.assertRaises(ValueError):verify_recovery(scoped,{**self.policy,'skill_names':[]},role)
