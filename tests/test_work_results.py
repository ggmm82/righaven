"""Real media acceptance and bounded recoverable inventories, no provider account."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from righaven.work_results import failure_info, partial_files, validate_media
from real_tools import requires


class WorkResultTests(unittest.TestCase):
    def test_quota_and_auth_are_actions_not_creative_retry_failures(self):
        for message in ['You’ve hit your usage limit', 'RESOURCE_EXHAUSTED quota reached', 'billing unavailable']:
            self.assertEqual(failure_info(message)['code'], 'provider_quota')
            self.assertFalse(failure_info(message)['retryable'])
        self.assertEqual(failure_info('Chiave DeepSeek rifiutata')['code'], 'provider_auth')
        self.assertTrue(failure_info('Limite dei turni DeepSeek')['retryable'])

    def test_interrupted_provider_stream_is_not_an_environment_installation_failure(self):
        value=failure_info('Antigravity: The stream was interrupted. Please continue the task you were working on.')
        self.assertEqual(value['code'],'provider_stream_interrupted')
        self.assertTrue(value['retryable'])
        self.assertIn('non richiede di reinstallare',value['action'])

    def test_inventory_keeps_useful_files_without_claiming_delivery_or_following_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'work').mkdir(); (root / 'assets').mkdir()
            for filename in ['mix.wav', 'session.scraft', 'work/log.txt', 'assets/media.wav', 'handoff.json']:
                (root / filename).write_text('fixture')
            (root / 'link.wav').symlink_to('/etc/passwd')
            self.assertEqual({Path(p).name for p in partial_files(root)}, {'mix.wav', 'session.scraft'})

    @requires('ffmpeg', 'ffprobe')
    def test_silent_or_audio_free_video_cannot_pass_final_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = ['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=blue:size=160x90:rate=10']
            for name, audio in [('mute', None), ('silent', 'anullsrc=r=48000:cl=stereo'),
                                ('audible', 'sine=frequency=440:sample_rate=48000')]:
                path = root / (name + '.mp4')
                args = base + (['-f', 'lavfi', '-i', audio] if audio else [])
                subprocess.run(args + ['-t', '0.6', '-c:v', 'libx264', '-pix_fmt', 'yuv420p'] +
                    (['-c:a', 'aac'] if audio else []) + [str(path)], capture_output=True, check=True, timeout=20)
                checks = validate_media(path, {'video': True, 'audio': True})
                self.assertEqual(all(c['status'] == 'passed' for c in checks), name == 'audible', json.dumps(checks))
