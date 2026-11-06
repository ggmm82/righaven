import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import docker_runtime, progress
from righaven.work_results import failure_info


class WorkerControlTests(unittest.TestCase):
    def test_stop_is_scoped_to_installation_and_conversation_and_keeps_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);state=root/'state';state.mkdir();(state/'installation-id').write_text('this-installation')
            workspace=root/'conversation';job='rh-job-123456abcdef'
            path=progress.create_job(workspace,job,'workspace','codex','fixture')
            progress.update(path,'waiting_model')
            saved=workspace/'partial.txt';saved.write_text('keep')
            info={'Config':{'Labels':{'org.righaven.harness.installation':'this-installation',
                                      'org.righaven.harness.workspace':progress.workspace_key(workspace)}},'State':{'Running':True}}
            with patch.object(docker_runtime,'STATE',state),patch.object(docker_runtime,'docker',return_value=json.dumps(info)) as docker:
                self.assertTrue(docker_runtime.request_stop(workspace,job)['requested'])
                self.assertEqual(docker.call_args.args,('stop','--time','10',job))
            self.assertTrue(progress.read_status(path)['cancel_requested'])
            self.assertEqual(saved.read_text(),'keep')
            info['Config']['Labels']['org.righaven.harness.workspace']='another-conversation'
            with patch.object(docker_runtime,'STATE',state),patch.object(docker_runtime,'docker',return_value=json.dumps(info)) as docker:
                with self.assertRaises(ValueError):docker_runtime.request_stop(workspace,job)
                self.assertEqual(docker.call_count,1)
            self.assertFalse(failure_info('Interruzione della fase richiesta dall’utente')['retryable'])
            self.assertEqual(failure_info("Command 'codex' timed out after 1500 seconds")['code'],'work_limit')
            with self.assertRaises(ValueError):docker_runtime.request_stop(workspace,'../another-job')

    def test_stop_signal_unwinds_cleanup_instead_of_abandoning_refreshed_credentials(self):
        import subprocess,sys,time
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);marker=root/'ready';cleanup=root/'cleaned'
            code="""import signal,time,pathlib,sys
from righaven.run_agent import handle_stop,WorkerCancelled
signal.signal(signal.SIGTERM,handle_stop)
try:
 pathlib.Path(sys.argv[1]).write_text('ready')
 time.sleep(10)
except WorkerCancelled:
 pass
finally:
 pathlib.Path(sys.argv[2]).write_text('cleanup')
"""
            process=subprocess.Popen([sys.executable,'-c',code,str(marker),str(cleanup)])
            try:
                until=time.monotonic()+5
                while not marker.exists() and time.monotonic()<until:time.sleep(.01)
                self.assertTrue(marker.exists())
                process.terminate();process.wait(timeout=5)
                self.assertEqual(cleanup.read_text(),'cleanup')
            finally:
                if process.poll() is None:process.kill();process.wait()
