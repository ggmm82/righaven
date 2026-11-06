import tempfile,unittest
from pathlib import Path
from scripts.install_environment_tools import select_binary,install_binaries
from righaven.environment_preparation import diagnosis


class EnvironmentInstallerTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        self.destination=self.root/'unpacked';self.destination.mkdir();self.bin=self.root/'bin';self.bin.mkdir()

    def file(self,path,data):
        result=self.destination/path;result.parent.mkdir(parents=True,exist_ok=True);result.write_bytes(data);return result

    def test_cli_is_selected_without_executing_or_linking_shell_completion(self):
        binary=self.file('photocraft-0.16.0/bin/photocraft-cli',b'\x7fELFfixture')
        completion=self.file('photocraft-0.16.0/share/bash-completion/completions/photocraft-cli',b'#!/bin/sh\ncomplete photocraft-cli')
        before=completion.stat().st_mode
        chosen=install_binaries({'id':'photocraft','executable':'photocraft-cli'},self.destination,self.bin)
        self.assertEqual(chosen,binary);self.assertEqual((self.bin/'photocraft-cli').resolve(),binary)
        self.assertEqual(completion.stat().st_mode,before)

    def test_ambiguous_real_binaries_and_external_links_are_rejected(self):
        self.file('first/craft-cli',b'\x7fELFone');self.file('second/craft-cli',b'\x7fELFtwo')
        with self.assertRaises(RuntimeError):select_binary(self.destination,'craft-cli')
        outside=self.root/'outside';outside.write_bytes(b'\x7fELFout')
        (self.destination/'escape-cli').symlink_to(outside)
        with self.assertRaises(RuntimeError):select_binary(self.destination,'escape-cli')
        with self.assertRaises(RuntimeError):select_binary(self.destination,'craft-cli','../outside')
        with self.assertRaises(ValueError):select_binary(self.destination,'../outside')

    def test_documentation_only_is_not_made_executable(self):
        self.file('docs/craft-cli',b'#!/bin/sh\nnot the app')
        with self.assertRaises(RuntimeError):select_binary(self.destination,'craft-cli')

    def test_missing_release_is_not_misreported_as_a_native_verification_failure(self):
        result=diagnosis('Installazione musescore v4.7.5 (amd64)\nurllib.error.HTTPError: HTTP Error 404: Not Found')
        self.assertEqual(result['kind'],'release_missing')
        self.assertEqual(result['tool'],'musescore')
        self.assertIn('404',result['message'])

    def test_official_musescore_asset_identity_is_not_rebranded(self):
        import json
        catalog=json.loads((Path(__file__).resolve().parents[1]/'versions.lock.json').read_text())
        app=next(a for a in catalog['applications'] if a['id']=='musescore')
        for asset in app['assets'].values():
            self.assertTrue(asset['name'].startswith('MuseScore-Studio-'))
            self.assertTrue(asset['url'].endswith('/'+asset['name']))

    def test_package_layout_failure_is_named_before_native_checks_start(self):
        result=diagnosis('Installazione photocraft v0.16.0 (amd64)\nRuntimeError: Atteso un eseguibile interno photocraft-cli, trovati [...]')
        self.assertEqual(result['tool'],'photocraft');self.assertEqual(result['kind'],'package_layout')
        self.assertIn('pacchetto',result['message'])
