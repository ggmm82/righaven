"""Health must distinguish a live subsequent cycle from a failed or abandoned one."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('exported_pipeline_runtime',Path(__file__).resolve().parents[1]/'scripts/pipeline_runtime.py')
runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime)

class PipelineHealth(unittest.TestCase):
    def test_live_cycle_after_success_is_healthy_but_failure_first_boot_and_dead_process_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'last-cycle.json'
            with patch.object(runtime,'paths',return_value=(root,root)),patch('sys.argv',['orchestrate.py','health']):
                for state in ({'status':'passed'},{'status':'running','last_completed_status':'passed','pid':os.getpid()}):
                    path.write_text(json.dumps(state));runtime.main()
                for state in ({'status':'failed','last_completed_status':'passed','pid':os.getpid()},
                              {'status':'running','last_completed_status':None,'pid':os.getpid()},
                              {'status':'running','last_completed_status':'failed','pid':os.getpid()},
                              {'status':'running','last_completed_status':'passed','pid':-1}):
                    path.write_text(json.dumps(state))
                    with self.assertRaises(SystemExit) as result:runtime.main()
                    self.assertEqual(result.exception.code,1)
                path.write_text(json.dumps({'status':'running','last_completed_status':'passed','pid':123}))
                with patch.object(runtime.os,'kill',side_effect=ProcessLookupError()):
                    with self.assertRaises(SystemExit):runtime.main()
