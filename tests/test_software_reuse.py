"""Software identity and incremental choices: tools are independent of provider CLIs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import environment_runtime as runtime,software_identity as software,state


class SoftwareReuseTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        replacement=patch.object(state,'STATE',self.root);replacement.start();self.addCleanup(replacement.stop)
        (self.root/'installation-id').write_text('fixture')
        self.tools=['d2','plantuml','typst','pandoc','qpdf','poppler','trivy','opengrep','duckdb','sqlglot']

    def test_metadata_and_provider_releases_do_not_change_compatible_software_identity(self):
        with patch.object(runtime,'docker',return_value='sha256:first'),patch.object(software,'inspect',return_value={'abi':'a'*64}):
            first,spec=runtime.recipe(['d2'])
        with patch.object(runtime,'docker',return_value='sha256:second'),patch.object(software,'inspect',return_value={'abi':'a'*64}):
            second,later=runtime.recipe(['d2'])
        self.assertNotEqual(spec['core'],later['core']);self.assertEqual(first,second)
        with patch.object(runtime,'docker',return_value='sha256:third'),patch.object(software,'inspect',return_value={'abi':'b'*64}):
            self.assertNotEqual(first,runtime.recipe(['d2'])[0])

    def test_unrelated_catalog_and_documentation_updates_do_not_invalidate_an_installed_tool(self):
        import copy
        apps=copy.deepcopy(state.applications())
        with patch.object(state,'applications',return_value=apps):
            first,_=runtime.recipe(['d2'],identity='sha256:base')
            for app in apps:
                if app['id']=='qpdf':app['version']='unrelated update'
                if app['id']=='d2':app['description']='Edited documentation'
            second,_=runtime.recipe(['d2'],identity='sha256:base')
            self.assertEqual(first,second)
            next(app for app in apps if app['id']=='d2')['version']='actual software update'
            self.assertNotEqual(first,runtime.recipe(['d2'],identity='sha256:base')[0])

    def test_closest_reusable_software_wins_over_an_unrelated_larger_image(self):
        key,spec=runtime.recipe(self.tools,identity='sha256:base')
        for count,size in ((8,1000000),(9,1)):
            kept=spec['tools'][:count]
            runtime.save(str(count)*64,status='ready',core=spec['core'],tools=kept,
                tool_fingerprints={t:spec['tool_fingerprints'][t] for t in kept},image_id='sha256:'+str(count),size_bytes=size)
        with patch.object(runtime,'image_exists',return_value=True):
            selected=runtime.subset(spec)
        self.assertEqual(len(selected['tools']),9)

    def test_partial_overlap_can_reuse_nine_tools_even_with_an_unrequested_extra(self):
        key,spec=runtime.recipe(self.tools,identity='sha256:base')
        kept=spec['tools'][:9]+['calibre']
        runtime.save('e'*64,status='ready',core=spec['core'],tools=kept,
            tool_fingerprints={**spec['tool_fingerprints'],'calibre':'unused'},image_id='sha256:extra')
        with patch.object(runtime,'image_exists',return_value=True):
            self.assertEqual(runtime.subset(spec)['id'],'e'*64)

    def test_one_changed_tool_retains_the_other_nine(self):
        key,spec=runtime.recipe(self.tools,identity='sha256:base')
        old={**spec['tool_fingerprints'],'d2':'old release'}
        runtime.save('b'*64,status='ready',core=spec['core'],tools=spec['tools'],tool_fingerprints=old,image_id='sha256:previous')
        with patch.object(runtime,'image_exists',return_value=True):
            self.assertEqual(runtime.candidates(spec),[])
            base=runtime.subset(spec)
        self.assertEqual(base['id'],'b'*64)
        same=[t for t in base['tools'] if old[t]==spec['tool_fingerprints'][t]]
        self.assertEqual(len(same),9)

    def test_a_legacy_provider_pin_does_not_disqualify_verified_application_software(self):
        key,spec=runtime.recipe(['d2'],identity='sha256:base')
        runtime.save('c'*64,status='ready',core=spec['core'],tools=['d2'],tool_fingerprints=spec['tool_fingerprints'],
            versions={'provider-agy':'old-cli'},image_id='sha256:old')
        with patch.object(runtime,'image_exists',return_value=True):
            self.assertEqual(runtime.candidates(spec)[0]['id'],'c'*64)
        # A provider image itself still needs an exact CLI choice.
        self.assertFalse(runtime.matching_versions({'versions':{'provider-agy':'old'}},{'tools':[],'versions':{'provider-agy':'new'}}))

    def test_persistent_compatibility_probe_is_not_run_again_after_gateway_restart(self):
        image='sha256:'+'f'*64
        result={'abi':'d'*64,'fingerprints':{'d2':'x'}}
        with patch.object(software,'_CACHE',{}),patch.object(runtime,'docker',return_value=json.dumps(result)) as docker:
            self.assertEqual(software.inspect(image,docker)['abi'],'d'*64)
            self.assertEqual(docker.call_count,1)
        with patch.object(software,'_CACHE',{}),patch.object(runtime,'docker',side_effect=AssertionError('Unexpected probe')) as docker:
            self.assertEqual(software.inspect(image,docker)['abi'],'d'*64)
            docker.assert_not_called()


class IncrementalInstallerTests(unittest.TestCase):
    def test_updating_one_of_ten_tools_keeps_the_other_nine_payloads(self):
        from scripts import prepare_environment as installer
        arch=__import__('platform').machine();arch={'x86_64':'amd64','aarch64':'arm64'}[arch]
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);bin_dir=root/'bin';bin_dir.mkdir();records=[];known={}
            for index in range(10):
                tool='tool'+str(index);target=root/'apps'/tool;target.mkdir(parents=True)
                binary=target/'cli';binary.write_text('existing '+tool);(bin_dir/tool).symlink_to(binary)
                records.append({'id':tool,'version':'1','sha256':'old','binary':str(binary)})
                known[tool]={'version':'2' if index==0 else '1','assets':{arch:{'sha256':'new' if index==0 else 'old'}}}
            (root/'installed.json').write_text(json.dumps(records))
            with patch.object(installer,'ROOT',root):
                reused,changed=installer.retain_unchanged(list(known),known,bin_dir)
            self.assertEqual(len(reused),9);self.assertEqual(changed,['tool0'])
            self.assertFalse((root/'apps/tool0').exists());self.assertFalse((bin_dir/'tool0').is_symlink())
            for index in range(1,10):self.assertEqual((bin_dir/('tool'+str(index))).read_text(),'existing tool'+str(index))
