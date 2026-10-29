"""Provider boundaries and honest environment version reporting."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from righaven import claude_cli,claude_protocol,environment_versions,state,tool_versions
from righaven.run_agent import copy_credentials
from scripts.data_tools import usql_url,redact


class ClaudeTests(unittest.TestCase):
    def test_coordinator_has_no_file_tools_or_project_settings(self):
        args=claude_cli.command('sonnet',{'type':'object'})
        self.assertEqual(args[args.index('--tools')+1],'')
        self.assertEqual(args[args.index('--setting-sources')+1],'')
        self.assertIn('--strict-mcp-config',args)
        self.assertIn('--no-session-persistence',args)
        worker=claude_cli.command('opus',worker=True)
        self.assertIn('Bash,Read,Write,Edit,Glob,Grep',worker)
        self.assertNotIn('--dangerously-skip-permissions',worker)

    def test_cli_result_requires_success_and_actual_structured_output(self):
        value={'content':'Connected','tool_calls':[]}
        result=SimpleNamespace(returncode=0,stdout=json.dumps({'type':'result','subtype':'success','structured_output':value,'usage':{'input_tokens':3}}))
        with patch.object(claude_cli.subprocess,'run',return_value=result) as run:
            output=claude_cli.generate({'model':'sonnet','schema':{},'prompt':'Hello'})
        self.assertEqual(output['content'],'Connected')
        self.assertEqual(run.call_args.kwargs['input'],'Hello')
        with self.assertRaises(RuntimeError):claude_cli.envelope('{"type":"result","is_error":true}')
        with self.assertRaises(RuntimeError):claude_cli.envelope('{"type":"assistant","message":{}}')

    def test_credentials_copy_only_official_auth_and_reject_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';source.mkdir();target=root/'target'
            (source/'.credentials.json').write_text('{}');(source/'settings.json').write_text('private')
            copy_credentials(source,target,'claude')
            self.assertEqual([p.name for p in target.iterdir()],['.credentials.json'])
            (source/'.credentials.json').unlink();(source/'.credentials.json').symlink_to(source/'settings.json')
            with self.assertRaises(ValueError):copy_credentials(source,target,'claude')

    def test_optional_provider_is_content_addressed_without_changing_core(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(state,'STATE',Path(temp)):
            selected=tool_versions.selections(engine='claude')
            self.assertEqual(set(selected),{'provider-claude'})
            record=tool_versions.read(selected['provider-claude'])
            self.assertEqual(record['source'],'verified-release-artifact')
            self.assertEqual(record['bundle']['app']['version'],json.loads(Path('scripts/claude.lock.json').read_text())['version'])
            self.assertEqual(tool_versions.selections(engine='codex'),{})


class InventoryTests(unittest.TestCase):
    def test_unknown_is_not_current_and_latest_uses_observed_pin(self):
        profile={'tools':['duckdb','dlt'],'runtime':{'status':'ready','installed_versions':{'dlt':'v1.0'}},'deployment':{'tool_versions':{'dlt':'latest'}}}
        rows={r['tool']:r for r in environment_versions.inventory(profile,{'duckdb':{'version':'2.0'}},{},{'dlt':{'revision':'abc'}},lambda revision:{'bundle':{'app':{'version':'1.1'}}})}
        self.assertEqual(rows['duckdb']['status'],'unknown')
        self.assertIsNone(rows['duckdb']['installed'])
        self.assertEqual(rows['dlt']['status'],'update_available')
        self.assertEqual(rows['dlt']['installed'],'v1.0')

    def test_unknown_cleanup_does_not_probe_runtime(self):
        from righaven.resource_budget import ResourceBudget
        budget=ResourceBudget()
        with patch.object(budget,'rebalance') as probe:
            budget.release('already-removed')
            probe.assert_not_called()


class DataBoundaryTests(unittest.TestCase):
    def test_shared_connection_url_normalizes_driver_without_exposing_secrets(self):
        self.assertEqual(usql_url('postgresql+psycopg://name:secret@host/db'),'postgresql://name:secret@host/db')
        self.assertEqual(usql_url('mssql+pymssql://name:secret@host/db'),'sqlserver://name:secret@host/db')
        self.assertEqual(usql_url('sqlite:////tmp/snapshot.sqlite'),'sqlite3:///tmp/snapshot.sqlite')
        self.assertNotIn('secret',redact('connection failed: secret',['secret']))

    def test_every_shipped_gallery_pack_has_a_usable_runtime_manifest(self):
        from righaven.gallery import validate_pack_manifest
        catalog=json.loads(Path('config/gallery-packs.json').read_text())
        for pack in catalog['packs']:
            with self.subTest(pack=pack['id']):validate_pack_manifest(pack)

    def test_all_data_skills_have_resolvable_sources_and_registered_operations(self):
        from scripts.data_specs import TOOLS
        for tool in TOOLS:
            root=Path('skills/custom/skill-'+tool)
            self.assertIn('editable sources',(root/'SKILL.md').read_text())
            self.assertTrue((root/'references/CLI-RECIPE.md').is_file())
            self.assertTrue(TOOLS[tool])


if __name__=='__main__':unittest.main()
