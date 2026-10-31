"""Prevent invented tool IDs, stale version guidance and unbounded discovery output."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from scripts.capability_catalog import command_ids
from scripts.check_tool_capabilities import validate, check_bounce
from scripts.render_capability_docs import render
from real_tools import requires

ROOT=Path(__file__).resolve().parents[1]
APP_COUNT=len(json.loads((ROOT/'versions.lock.json').read_text())['applications'])


class ToolCapabilitiesTests(unittest.TestCase):
    @requires('ffmpeg','ffprobe')
    def test_extensible_pcm24_is_decoded_but_silence_and_wrong_duration_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def encode(name,source='sine=frequency=440:sample_rate=48000',duration='2',channels='2'):
                path=root/name
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i',source,'-t',duration,
                    '-ac',channels,'-c:a','pcm_s24le',str(path)],capture_output=True,check=True,timeout=30)
                return path
            native=encode('extensible.wav')
            header=native.read_bytes();fmt=header.index(b'fmt ')
            self.assertEqual(int.from_bytes(header[fmt+8:fmt+10],'little'),65534)
            check_bounce(native)
            for path in (encode('silent.wav',source='anullsrc=r=48000:cl=stereo'),
                         encode('short.wav',duration='1'),encode('mono.wav',channels='1')):
                with self.assertRaises(AssertionError):check_bounce(path)

    def test_catalog_formats_keep_real_ids_and_strip_undo_marker(self):
        self.assertEqual(command_ids('[{"id":"midi.note_add"},{"id":"midi.note_add"}]'),['midi.note_add'])
        self.assertEqual(command_ids('{"tools":[{"name":"calibre.check"}]}'),['calibre.check'])
        self.assertEqual(command_ids('node.create*  Create node\nframe.create  Create frame\n\n'),['frame.create','node.create'])
        with self.assertRaises(ValueError):command_ids('123')

    def fixture(self,root):
        shutil.copy2(ROOT/'versions.lock.json',root/'versions.lock.json')
        data=json.loads((ROOT/'config/tool-capabilities.json').read_text())
        (root/'tool-capabilities.json').write_text(json.dumps(data))
        return data

    def test_catalog_drift_and_fabricated_capability_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=self.fixture(root)
            self.assertEqual(len(validate(root)),APP_COUNT)
            for mutate in (
                lambda a:a.update(version='unverified-upgrade'),
                lambda a:a['groups'][0]['commands'].append('invented.generate_perfect_product'),
                lambda a:a['catalog_ids'].append(a['catalog_ids'][0]),
                lambda a:a.update(ids_sha256='0'*64),
            ):
                data=self.fixture(root);mutate(data['applications'][0]);(root/'tool-capabilities.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):validate(root)

    def test_discovery_is_compact_and_checks_version_even_for_index(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);data=self.fixture(root)
            def run(*args):
                return subprocess.run([sys.executable,str(ROOT/'scripts/craft.py'),'capabilities',*args],
                    env={**os.environ,'RIGHAVEN_INSTALL_ROOT':str(root)},capture_output=True,text=True,check=False)
            index=run();self.assertEqual(index.returncode,0);self.assertEqual(len(json.loads(index.stdout)),APP_COUNT)
            self.assertNotIn('catalog_ids',index.stdout)
            sound=run('soundcraft');self.assertNotIn('catalog_ids',json.loads(sound.stdout))
            self.assertIn('midi.note_add',sound.stdout)
            complete=run('soundcraft','--all-commands');self.assertGreater(len(json.loads(complete.stdout)['catalog_ids']),400)
            self.assertNotEqual(run('nonexistent').returncode,0)
            data['applications'][0]['version']='unknown';(root/'tool-capabilities.json').write_text(json.dumps(data))
            self.assertNotEqual(run().returncode,0)

    def test_generated_guidance_covers_installed_apps_without_drift(self):
        pages=render(ROOT)
        self.assertEqual(len(pages),APP_COUNT+1)
        for path,text in pages.items():
            self.assertEqual(path.read_text(),text,str(path))
