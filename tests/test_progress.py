import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from righaven import progress
from righaven.cli_runner import run_cli


class ProgressTests(unittest.TestCase):
    def test_actual_cli_commands_show_useful_actions_without_arguments(self):
        self.assertEqual(progress.tool_label('/usr/local/bin/effectcraft-cli --project /mnt/user-data/robot.ecproj render --out /mnt/user-data/robot.mp4'),
                         'Esporto il risultato con Effectcraft')
        self.assertEqual(progress.tool_label('craft batch filmcraft /mnt/user-data/edit.json'), 'Comando Filmcraft in esecuzione')
        self.assertEqual(progress.tool_label('soundcraft-cli run --in session.scraft --bounce mix.wav'), 'Esporto il risultato con Soundcraft')
        self.assertEqual(progress.tool_label('calibre-cli check /mnt/user-data/private.epub'), 'Comando Calibre in esecuzione')
        self.assertEqual(progress.tool_label('ebook-convert private.docx private.epub'), 'Comando Calibre in esecuzione')
        self.assertEqual(progress.tool_label('craft help photocraft'), 'Consulto i comandi di Photocraft')
        self.assertEqual(progress.tool_label('ffprobe -show_streams private-movie.mp4'), 'Verifico formato, durata e tracce del file')
        self.assertNotIn('private', progress.tool_label('ffmpeg -i private-audio.wav -af volumedetect -f null -'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = {'agent': 'gridcraft', 'engine': 'codex', 'model': 'fixture',
                    'run_id': 'rh-job-123456abcdef'}
        self.output = self.root / 'outputs/gridcraft' / self.job['run_id']
        self.output.mkdir(parents=True)
        self.reporter = progress.Reporter(self.output, self.job)

    def test_recovery_keeps_the_original_clock_and_emits_a_fresh_heartbeat(self):
        original='2026-10-16T08:00:00+00:00'
        progress.update(self.reporter.path,'failed',started_at=original)
        try:
            self.reporter.start(300,preserve_started=True)
            self.reporter.emit('checking',execution_state='tool')
            value=progress.read_status(self.reporter.path)
            self.assertEqual(value['started_at'],original)
            self.assertTrue(value['heartbeat_at'])
            self.assertGreater(value['deadline_at'],original)
            self.assertEqual(value['execution_state'],'tool')
        finally:
            self.reporter.close()

    def test_heartbeat_is_not_faked_work_and_files_are_observed(self):
        before = progress.read_status(self.reporter.path)['last_activity_at']
        with patch.object(progress, 'utcnow', return_value='2026-10-16T09:10:00+00:00'):
            self.reporter.pulse()
        value = progress.read_status(self.reporter.path)
        self.assertEqual(value['last_activity_at'], before)
        self.assertEqual(value['heartbeat_at'], '2026-10-16T09:10:00+00:00')
        (self.output / 'report.xlsx').write_bytes(b'fixture')
        (self.output / 'work').mkdir()
        (self.output / 'work/private.txt').write_text('private command output')
        (self.output / 'external').symlink_to('/etc/passwd')
        self.reporter.pulse()
        public = progress.list_jobs(self.root)[0]
        self.assertEqual(public['files'], [{'name': 'report.xlsx', 'size': 7}])
        self.assertNotEqual(public['last_activity_at'], before)
        (self.output / 'report.xlsx').write_bytes(b'updated')  # Same size, new modification time.
        with patch.object(progress, 'utcnow', return_value='2099-01-01T00:00:00+00:00'):
            self.reporter.pulse()
        self.assertEqual(progress.list_jobs(self.root)[0]['last_activity_at'], '2099-01-01T00:00:00+00:00')

    def test_durable_history_is_bounded_and_contains_no_cli_secrets(self):
        for index in range(75):
            self.reporter.emit('creating', 'Passaggio ' + str(index))
        self.reporter.emit('checking', 'token=fixture-secret sk-test-secret-value-123')
        value = progress.list_jobs(self.root)[0]
        self.assertEqual(len(value['events']), 60)
        self.assertNotIn('fixture-secret', json.dumps(value))
        self.assertNotIn('sk-test', json.dumps(value))
        # A fresh reader after page/process reload sees exactly the same history.
        self.assertEqual(progress.list_jobs(self.root), [value])
        self.assertEqual(self.reporter.path.stat().st_mode & 0o777, 0o600)

    def test_observes_real_codex_and_antigravity_envelopes_without_reasoning(self):
        self.reporter.cli_event('codex', {'type': 'item.started', 'item': {
            'type': 'command_execution', 'command': 'craft cadcraft batch --api-key secret-value'}})
        self.assertIn('Cadcraft', progress.read_status(self.reporter.path)['summary'])
        self.reporter.cli_event('gemini', {'event': 'step_update', 'step_update': {
            'step_index': 4, 'state': 'ACTIVE', 'step_type': 'tool',
            'tool_info': {'parameters': {'command': 'craft gridcraft help'}, 'output': 'private transcript'}}})
        self.assertIn('Gridcraft', progress.read_status(self.reporter.path)['summary'])
        activity = progress.read_status(self.reporter.path)['last_activity_at']
        with patch.object(progress, 'utcnow', return_value='2099-01-01T00:00:00+00:00'):
            self.reporter.cli_event('gemini', {'event': 'step_update', 'step_update': {
                'step_index': 4, 'state': 'ACTIVE', 'step_type': 'tool', 'duration_seconds': 180}})
        self.assertEqual(progress.read_status(self.reporter.path)['last_activity_at'], activity)
        self.reporter.cli_event('gemini', {'event': 'step_update', 'step_update': {
            'step_index': 5, 'state': 'ACTIVE', 'step_type': 'agent_response',
            'text_delta': 'private hidden reasoning'}})
        public = json.dumps(progress.list_jobs(self.root))
        for secret in ('secret-value', 'private transcript', 'private hidden reasoning'):
            self.assertNotIn(secret, public)

    def test_other_workspaces_and_symlinked_metadata_are_not_followed(self):
        import shutil
        self.assertEqual(progress.list_jobs(self.root / 'another-user'), [])
        branch = self.root / 'branched-conversation'
        shutil.copytree(self.root / '.righaven-jobs', branch / '.righaven-jobs')
        self.assertEqual(progress.list_jobs(branch), [])
        outside = self.root / 'other'; outside.mkdir()
        (outside / '.righaven-jobs').symlink_to(self.root / '.righaven-jobs', target_is_directory=True)
        self.assertEqual(progress.list_jobs(outside), [])
        with self.assertRaises(ValueError):
            progress.job_path(self.root, '../credentials')

    def test_cli_events_arrive_before_process_finishes_and_deadline_kills_it(self):
        marker = self.root / 'seen'
        code = '''import json,pathlib,time,sys
print(json.dumps({'type':'turn.started'}),flush=True)
marker=pathlib.Path(sys.argv[1]);deadline=time.monotonic()+3
while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
assert marker.exists(), 'No live event observed before completion'
print(json.dumps({'type':'turn.completed'}),flush=True)
'''
        events = []
        def observe(event):
            events.append(event)
            marker.write_text('observed while running')
        result = run_cli([sys.executable, '-c', code, str(marker)], cwd=self.root,
                         input='fixture', env=None, timeout=5, on_event=observe)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(events), 2)
        with self.assertRaises(subprocess.TimeoutExpired):
            run_cli([sys.executable, '-c', 'import time;time.sleep(20)'], cwd=self.root,
                    input='', env=None, timeout=0.1, on_event=observe)

    def test_background_worker_clock_and_terminal_status_survive_close(self):
        self.reporter.start(1500)
        try:
            self.reporter.emit('exporting', 'Esportazione XLSX e anteprima')
            self.reporter.emit('completed')
            finish = progress.read_status(self.reporter.path)['finished_at']
        finally:
            self.reporter.close()
        value = progress.list_jobs(self.root)[0]
        self.assertEqual(value['finished_at'], finish)
        self.assertEqual(value['phase'], 'completed')
        self.assertTrue(value['deadline_at'])


if __name__ == '__main__':
    unittest.main()

class SignalSeparationTests(unittest.TestCase):
    def test_wait_clock_provider_event_and_file_changes_are_separate_from_heartbeat(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'outputs/workspace/rh-job-123456abcdef';output.mkdir(parents=True)
            reporter=progress.Reporter(output,{'run_id':output.name,'agent':'workspace','engine':'codex','model':'fixture'})
            reporter.emit('running_tool')
            reporter.emit('waiting_model')
            before=progress.read_status(reporter.path)
            with patch.object(progress,'utcnow',return_value='2099-01-01T00:00:00Z'):
                reporter.pulse()
                reporter.cli_event('codex',{'type':'item.updated','item':{'type':'reasoning','text':'private thinking sk-private-secret-value'}})
            after=progress.list_jobs(Path(root))[0]
            self.assertEqual(after['execution_state'],'model')
            self.assertEqual(after['execution_started_at'],before['execution_started_at'])
            self.assertEqual(after['last_activity_at'],before['last_activity_at'])
            self.assertEqual(after['last_model_event_at'],'2099-01-01T00:00:00Z')
            self.assertNotIn('private thinking',json.dumps(after))
            self.assertNotIn('sk-private',json.dumps(after))
            reporter.emit('completed');self.assertEqual(progress.list_jobs(Path(root))[0]['execution_state'],'finished')

class ProviderWaitBudgetTests(unittest.TestCase):
    def test_silent_model_returns_control_and_preserves_partial_files(self):
        from righaven.cli_runner import ProviderSilence
        from righaven.work_results import failure_info
        with tempfile.TemporaryDirectory() as folder:
            marker=Path(folder)/'partial.txt'
            code="import pathlib,time;pathlib.Path('partial.txt').write_text('saved');time.sleep(5)"
            with self.assertRaises(ProviderSilence) as error:
                run_cli([sys.executable,'-c',code],cwd=folder,input='',env=None,timeout=4,
                        on_event=lambda event: None,model_wait_seconds=.05,waiting_model=lambda: True)
            self.assertEqual(marker.read_text(),'saved')
            self.assertEqual(failure_info(str(error.exception))['code'],'provider_wait_limit')

    def test_long_native_command_is_not_killed_by_model_wait_budget(self):
        mode={'waiting':False}
        code="import json,time;print(json.dumps({'type':'command.started'}),flush=True);time.sleep(.5);print(json.dumps({'type':'command.completed'}),flush=True)"
        def event(value): mode['waiting']=value['type']=='command.completed'
        with tempfile.TemporaryDirectory() as folder:
            result=run_cli([sys.executable,'-c',code],cwd=folder,input='',env=None,timeout=3,
                           on_event=event,model_wait_seconds=.05,waiting_model=lambda:mode['waiting'])
            self.assertEqual(result.returncode,0)

class ToolIdentityTests(unittest.TestCase):
    def test_image_generation_is_work_not_model_silence_and_trace_excludes_payload(self):
        with tempfile.TemporaryDirectory() as root:
            output=Path(root)/'outputs/workspace/rh-job-123456abcdef';output.mkdir(parents=True)
            reporter=progress.Reporter(output,{'run_id':output.name,'agent':'workspace','engine':'codex','model':'fixture'})
            reporter.cli_event('codex',{'type':'item.started','item':{'type':'image_generation_call','prompt':'private prompt','arguments':{'api_key':'private key'}}})
            self.assertEqual(reporter.execution_state,'tool')
            text=(output/'work/tool-events.json').read_text()
            self.assertIn('image_generation_call',text)
            self.assertNotIn('private prompt',text);self.assertNotIn('private key',text)
            reporter.cli_event('codex',{'type':'item.completed','item':{'type':'image_generation_call'}})
            self.assertEqual(reporter.execution_state,'model')
