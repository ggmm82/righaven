import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from righaven import capability_policy as policy


class NativePolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.names = {'skill-workspace', 'skill-blender', 'skill-freecad', 'writing-method'}
        self.packages = {}
        for name in self.names:
            folder = self.root / 'packages' / name; folder.mkdir(parents=True)
            (folder / 'SKILL.md').write_text('Native procedure ' + name)
            self.packages[name] = folder
        outer = self
        class Storage:
            def __init__(self, user): self.user = user
            def set_skill_enabled_state(self, name, enabled):
                path = outer.root / self.user / 'skills/_skill_states.json'
                path.parent.mkdir(parents=True, exist_ok=True)
                data = json.loads(path.read_text()) if path.exists() else {}
                data[name] = {'enabled': enabled}; path.write_text(json.dumps(data))
            def load_skills(self, enabled_only=False):
                path = outer.root / self.user / 'skills/_skill_states.json'
                data = json.loads(path.read_text()) if path.exists() else {}
                return [SimpleNamespace(name=n, skill_dir=outer.packages[n]) for n in outer.names
                        if not enabled_only or data.get(n, {}).get('enabled', True)]
        self.store = Storage
        self.agents = {'all': SimpleNamespace(skills=None), 'none': SimpleNamespace(skills=[]),
                       'cad': SimpleNamespace(skills=['skill-workspace', 'skill-freecad', 'writing-method'])}
        modules = {}
        for name in ('righaven_core', 'righaven_core.skills', 'righaven_core.config', 'righaven_core.skills.storage',
                     'righaven_core.config.paths', 'righaven_core.config.agents_config', 'righaven_core.agents',
                     'righaven_core.agents.lead_agent', 'righaven_core.agents.lead_agent.prompt',
                     'righaven_core.runtime', 'righaven_core.runtime.user_context'):
            module = ModuleType(name); module.__path__ = []; modules[name] = module
        modules['righaven_core.skills.storage'].get_or_new_user_skill_storage = Storage
        modules['righaven_core.config.paths'].get_paths = lambda: SimpleNamespace(user_dir=lambda u: self.root / u)
        modules['righaven_core.config.agents_config'].load_agent_config = lambda n, **kw: self.agents.get(n)
        modules['righaven_core.runtime.user_context'].resolve_runtime_user_id = lambda runtime: 'one'
        modules['righaven_core.agents.lead_agent.prompt'].invalidate_user_skill_cache = lambda u: None
        modules['righaven_core.agents.lead_agent.prompt'].publish_skills_cache_reset = lambda **kw: None
        context = patch.dict(sys.modules, modules); context.start(); self.addCleanup(context.stop)
        context = patch.object(policy, 'catalog', return_value={'blender': {'enabled': False}})
        context.start(); self.addCleanup(context.stop)

    def test_native_state_wins_after_one_time_legacy_import_without_cross_user_changes(self):
        self.assertIn('blender', policy.native_policy('one')['blocked'])
        self.store('one').set_skill_enabled_state('skill-blender', True)
        self.assertIn('blender', policy.native_policy('one')['allowed'])
        self.assertIn('blender', policy.native_policy('two')['blocked'])
        self.assertIn('blender', policy.native_policy('one')['allowed'])

    def test_saved_native_choice_is_not_overwritten_by_legacy_disabled_flag(self):
        self.store('one').set_skill_enabled_state('skill-blender', True)
        self.assertIn('blender', policy.native_policy('one')['allowed'])

    def test_native_agent_scope_survives_a_child_runtime_context(self):
        runtime = SimpleNamespace(config={'configurable': {'righaven_agent_name': 'cad'}},
                                  context={'agent_name': 'all'})
        self.assertEqual(policy.runtime_policy(runtime)['allowed'], ['freecad'])

    def test_agent_none_empty_and_selected_skills_follow_native_semantics(self):
        self.assertIn('freecad', policy.native_policy('one', 'all')['allowed'])
        self.assertEqual(policy.native_policy('one', 'none')['allowed'], [])
        cad = policy.native_policy('one', 'cad')
        self.assertEqual(cad['allowed'], ['freecad'])
        self.assertEqual(cad['extra_skills'], ['writing-method'])
        with self.assertRaises(ValueError): policy.require_tools(cad, ['blender'])
        with self.assertRaises(ValueError): policy.native_policy('one', 'missing')

    def test_actual_selected_skill_content_and_references_are_projected(self):
        folder = self.packages['writing-method']; (folder / 'references').mkdir()
        (folder / 'references/recipe.md').write_text('Actual native reference')
        cad = policy.native_policy('one', 'cad')
        target = policy.stage_skills(cad, ['writing-method'], self.root / 'projection')
        self.assertEqual((target / 'writing-method/SKILL.md').read_text(), 'Native procedure writing-method')
        self.assertEqual((target / 'writing-method/references/recipe.md').read_text(), 'Actual native reference')
        self.assertFalse((target / 'skill-blender').exists())
        (folder / 'escape').symlink_to(self.root / 'one', target_is_directory=True)
        with self.assertRaises(ValueError): policy.stage_skills(cad, ['writing-method'], self.root / 'unsafe')
        with self.assertRaises(ValueError): policy.stage_skills(cad, ['../secret'], self.root / 'invalid')

    def test_worker_masks_cover_native_paths_even_for_roles_with_no_tool_declarations(self):
        scoped = policy.policy_from_names({'skill-freecad'})
        args = policy.worker_arguments(scoped, '/host/tool-disabled', projected_skills=True)
        self.assertIn('/opt/righaven/apps/blender:ro,size=1m', args)
        self.assertIn('type=bind,src=/host/tool-disabled,dst=/usr/bin/ffmpeg,readonly', args)
        self.assertIn('type=bind,src=/host/tool-disabled,dst=/usr/bin/ffprobe,readonly', args)
        self.assertFalse(any('/mnt/skills/custom/' in a for a in args))
        self.assertFalse(any('dst=/usr/lib/freecad/bin' in a for a in args))
        with self.assertRaises(ValueError): policy.require_tools(scoped, ['blender'])
        blocked_cad = policy.policy_from_names({'skill-blender'})
        args = policy.worker_arguments(blocked_cad, '/host/tool-disabled')
        self.assertIn('/opt/righaven/apps/freecad:ro,size=1m', args)
        self.assertNotIn('/usr/lib/freecad-python3/lib:ro,size=1m', args)
        self.assertNotIn('/usr/lib/freecad-python3:ro,size=1m', args)
        self.assertNotIn('/usr/lib/freecad/lib:ro,size=1m', args)
