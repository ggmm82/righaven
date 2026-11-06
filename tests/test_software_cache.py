"""Idle editors cannot grow an unbounded software cache or retain AI workers."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from righaven import state,environment_runtime as runtime,runtime_settings,editor_interface_cache as interfaces


class SoftwareCache(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);changed=patch.object(state,'STATE',self.root);changed.start();self.addCleanup(changed.stop)

    def test_shared_budget_evicts_least_recently_used_and_keeps_active_software(self):
        # The add-on is newer than the idle worker image; the active image is oldest.
        for key,last in [('a',10),('b',20),('c',30)]:runtime.save(key*64,status='ready',size_bytes=1024**3,created_at=1,last_used=last)
        addon={'id':'d'*64,'editor_interface':True,'size_bytes':1024**3,'created_at':1,'last_used':25}
        removed=[]
        with patch.object(runtime,'cache_settings',return_value={'max_gib':2,'max_idle_days':365}),patch.object(runtime,'pinned',return_value={'a'*64}),patch.object(runtime.time,'time',return_value=100),patch.object(interfaces,'entries',return_value=[addon]),patch.object(runtime,'evict',side_effect=lambda key:removed.append(key) or {'removed':True}),patch.object(interfaces,'evict',side_effect=lambda key:removed.append(key) or {'removed':True}):runtime.prune()
        self.assertEqual(removed,['b'*64,'d'*64]);self.assertNotIn('a'*64,removed)

    def test_idle_expiry_removes_software_but_never_project_data(self):
        source=self.root/'project/source.svg';source.parent.mkdir();source.write_text('keep')
        runtime.save('a'*64,status='ready',size_bytes=1,created_at=1,last_used=1)
        with patch.object(runtime,'cache_settings',return_value={'max_gib':20,'max_idle_days':1}),patch.object(runtime,'pinned',return_value=set()),patch.object(runtime.time,'time',return_value=90000),patch.object(runtime,'evict',return_value={'removed':True}) as evict:runtime.prune()
        evict.assert_called_once_with('a'*64);self.assertEqual(source.read_text(),'keep')
        self.assertEqual(runtime.read('a'*64)['cache_cleanup']['reason'],'idle_limit')

    def test_resource_updates_preserve_cache_preferences_and_validate_bounds(self):
        with patch.object(runtime_settings,'capacity',return_value={'cpus':4,'memory_mib':8192,'detected':True}):
            runtime_settings.save({'mode':'auto','cpus':1,'memory_mib':1024,'cache_max_gib':7,'cache_idle_days':3})
            runtime_settings.save({'mode':'auto','cpus':2,'memory_mib':1024})
            self.assertEqual(runtime.cache_settings(),{'max_gib':7,'max_idle_days':3})
            for field,value in [('cache_max_gib',0),('cache_idle_days',366),('cache_max_gib',True)]:
                with self.assertRaisesRegex(ValueError,'Software cache'):runtime_settings.save({'mode':'auto','cpus':2,'memory_mib':1024,field:value})
        self.assertEqual(runtime.cache_settings(),{'max_gib':7,'max_idle_days':3})

    def test_interface_eviction_checks_claims_and_running_containers(self):
        key='d'*64;interfaces.folder().mkdir();path=interfaces.folder()/(key+'.json')
        path.write_text(json.dumps({'id':key,'editor_interface':True,'image':'righaven-editor:'+key,'image_id':'sha256:addon'}))
        with patch.object(runtime,'pinned',return_value={key}),patch.object(runtime,'docker') as docker:
            self.assertFalse(interfaces.evict(key)['removed']);docker.assert_not_called()
        inspected=json.dumps([{'Id':'sha256:addon','Config':{'Labels':{'org.righaven.harness.installation':'fixture'}}}])
        with patch.object(runtime,'installation',return_value='fixture'),patch.object(runtime,'pinned',return_value=set()),patch.object(runtime,'docker',side_effect=[inspected,'container']) as docker:
            self.assertFalse(interfaces.evict(key)['removed']);self.assertTrue(path.exists());self.assertEqual(docker.call_count,2)
        with patch.object(runtime,'installation',return_value='fixture'),patch.object(runtime,'pinned',return_value=set()),patch.object(runtime,'docker',side_effect=[inspected,'','deleted']):
            self.assertTrue(interfaces.evict(key)['removed']);self.assertFalse(path.exists())

    def test_explicit_editor_preload_records_software_before_releasing_preparation_claims(self):
        from righaven import editor_preparation as preparation,environments,tool_versions
        prefs={'studio':{'editors':['jupyter']}};source='a'*64;addon='b'*64
        with patch('righaven.capability_policy.native_policy',return_value={'allowed':['jupyter']}),patch.object(environments,'preferences',return_value=prefs),patch.object(environments,'preferences_path',return_value=self.root/'preferences.json'),patch.object(tool_versions,'resolved',return_value={}),patch.object(tool_versions,'software_selections',return_value={}),patch.object(runtime,'ensure',return_value={'id':source,'image_id':'sha256:source'}) as ensure,patch('righaven.editor_runtime.interface',return_value='righaven-editor:'+addon),patch.object(runtime,'release_claim') as release:
            preparation.prepare('owner','studio','jupyter')
        self.assertEqual(preparation.JOBS[('owner','studio','jupyter')]['state'],'ready')
        self.assertEqual(json.loads((self.root/'preferences.json').read_text())['studio']['editor_software']['jupyter'],{'environment_id':source,'interface_id':addon})
        self.assertTrue(ensure.call_args.kwargs['claim'].startswith('editor-preload-'));self.assertEqual(release.call_count,2)
