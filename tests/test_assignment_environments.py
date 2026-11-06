"""Assignment configuration reuse and ordinary terminal retention boundaries."""
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from righaven import assignment_environments as assignment, environment_terminal as terminal, state
from righaven.progress import create_job, workspace_key


class AssignmentEnvironments(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.workspace=self.root/'project';self.workspace.mkdir()
        self.job='rh-job-'+'a'*12;self.environment='e'*64
        self.patch=patch.object(state,'STATE',self.root/'state');self.patch.start();self.addCleanup(self.patch.stop)
        create_job(self.workspace,self.job,'typst','codex','model')
        self.runtime={'id':self.environment,'image_id':'sha256:verified','tools':['typst'],
                      'versions':{'typst':'builtin','provider-agy':'latest'}}
        assignment.capture(self.workspace,self.job,['skill-workspace','skill-typst'],self.runtime)
        self.policy={'allowed':['typst'],'blocked':[],'skill_names':['skill-workspace','skill-typst']}
        self.policy_patch=patch('righaven.capability_policy.native_policy',return_value=self.policy);self.policy_patch.start();self.addCleanup(self.policy_patch.stop)
        self.skills_patch=patch('righaven.environments.resolve_skills',return_value={'skills':['skill-workspace','skill-typst'],'tools':['typst'],'disabled':[]})
        self.resolve=self.skills_patch.start();self.addCleanup(self.skills_patch.stop)

    def test_saved_configuration_excludes_provider_and_prompts_and_uses_trusted_versions(self):
        result,_,_,_=assignment.configuration('alice',self.workspace,self.job)
        self.assertEqual(result['tool_versions'],{'typst':'builtin'})
        self.assertEqual(result['instructions'],'');self.assertEqual(result['mode'],'on_demand')
        self.assertEqual(result['name'],'assignment-'+'a'*12)
        self.assertNotIn('image_id',result);self.assertNotIn('connections',result)
        path=assignment.snapshot_path(self.workspace,self.job)
        original=path.read_bytes()
        assignment.configuration('alice',self.workspace,self.job)
        self.assertEqual(path.read_bytes(),original)

    def test_disabled_skills_and_foreign_workspace_are_not_reopened(self):
        self.resolve.return_value['disabled']=['skill-typst']
        with self.assertRaisesRegex(ValueError,'disabled'):assignment.configuration('alice',self.workspace,self.job)
        self.resolve.return_value['disabled']=[]
        file=self.workspace/'.righaven-jobs'/self.job/'progress.json'
        value=json.loads(file.read_text());value['workspace_key']='foreign';state.atomic_json(file,value)
        with self.assertRaisesRegex(ValueError,'conversation'):assignment.configuration('alice',self.workspace,self.job)
        with self.assertRaises(ValueError):assignment.snapshot_path(self.workspace,'../../foreign')

    def test_saved_builtin_programs_do_not_adopt_a_different_global_latest(self):
        from righaven import environments,tool_versions
        self.runtime['versions']={}
        assignment.capture(self.workspace,self.job,['skill-workspace','skill-typst'],self.runtime)
        definition,_,_,_=assignment.configuration('alice',self.workspace,self.job)
        with patch.object(environments,'preferences_path',return_value=self.root/'preferences.json'),patch.object(tool_versions,'defaults',return_value={'typst':'latest'}):
            environments.set_deployment('alice',definition['name'],'preload',tool_versions=definition['tool_versions'])
            self.assertEqual(tool_versions.software_selections('alice',definition['name'],['typst']),{})

    def test_terminal_uses_verified_software_and_only_confined_read_only_project_sources(self):
        output=state.STATE/'task-staging'/workspace_key(self.workspace)/self.job/'output';output.mkdir(parents=True)
        with patch('righaven.environment_runtime.read',return_value=self.runtime),patch('righaven.environment_runtime.image_exists',return_value=True):
            profile,policy=assignment.terminal_profile('alice',self.workspace,self.job)
        self.assertEqual(profile['_terminal_record']['image_id'],'sha256:verified')
        self.assertEqual(profile['_terminal_mounts'],[(self.workspace,'/workspace/project'),(output,'/workspace/output')])
        self.assertEqual(policy['allowed'],['typst'])
        self.assertNotIn('credentials',json.dumps(profile,default=str))
        output.rmdir();output.symlink_to(self.root,target_is_directory=True)
        with patch('righaven.environment_runtime.read',return_value=self.runtime),patch('righaven.environment_runtime.image_exists',return_value=True):
            with self.assertRaisesRegex(ValueError,'output path'):assignment.terminal_profile('alice',self.workspace,self.job)

    def test_missing_software_is_not_silently_rebuilt_or_replaced(self):
        with patch('righaven.environment_runtime.read',return_value=self.runtime),patch('righaven.environment_runtime.image_exists',return_value=False):
            with self.assertRaisesRegex(ValueError,'prepare it again'):assignment.terminal_profile('alice',self.workspace,self.job)
        # Configuration can still be reviewed/saved without starting a terminal.
        self.assertIn('skill-typst',assignment.configuration('alice',self.workspace,self.job)[0]['skills'])


class RetainedTerminal(unittest.TestCase):
    def session(self):
        session=terminal.Session.__new__(terminal.Session)
        session.started=100.;session.last_seen=100.;session.retain_until=0
        session.cancelled=threading.Event();session.closed=False;session.mutex=threading.Lock()
        session.user='alice';session.client_id='a'*32;session.public=lambda:{'id':'one','finished':session.closed}
        return session

    def test_retention_is_explicit_bounded_and_does_not_disable_hard_cleanup(self):
        session=self.session()
        with patch('righaven.environment_terminal.time.monotonic',return_value=200):
            self.assertTrue(session.should_close())
            session.retain(10);self.assertFalse(session.should_close());self.assertEqual(session.retain_until,800)
            session.retain(30);self.assertEqual(session.retain_until,1900)
            for invalid in (True,-1,31,'30'):
                with self.assertRaises(ValueError):session.retain(invalid)
        with patch('righaven.environment_terminal.time.monotonic',return_value=1900):self.assertTrue(session.should_close())
        session.retain_until=9999;session.cancelled.set()
        with patch('righaven.environment_terminal.time.monotonic',return_value=200):self.assertTrue(session.should_close())

    def test_closed_page_preserves_only_explicitly_retained_session_and_reconnect_is_owner_scoped(self):
        session=self.session();session.retain_until=800
        with patch.dict(terminal.SESSIONS,{'one':session},clear=True),patch.dict(terminal.CLOSED_CLIENTS,{},clear=True),patch('righaven.environment_terminal.time.monotonic',return_value=200):
            terminal.close_client('alice','a'*32);self.assertFalse(session.cancelled.is_set())
            with self.assertRaises(FileNotFoundError):terminal.reconnect('bob','one','b'*32)
            terminal.reconnect('alice','one','b'*32)
            terminal.close_client('alice','a'*32);self.assertFalse(session.cancelled.is_set())
            session.retain(0)
            terminal.close_client('alice','b'*32);self.assertTrue(session.cancelled.is_set())
