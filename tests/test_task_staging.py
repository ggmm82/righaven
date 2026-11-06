"""Output transactions protect old revisions and preserve complete native trees."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven.task_staging import TaskStaging, inventory
from righaven.progress import create_job, update, read_status


class TaskStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.project = self.root/'project'; self.project.mkdir()
        self.baseline = self.project/'approved.blend'; self.baseline.write_bytes(b'approved source')
        self.stage = TaskStaging(self.root/'state', self.project, 'workspace', 'rh-job-123456abcdef')
        self.stage.prepare()

    def contract(self, stage=None):
        stage = stage or self.stage
        (stage.output/'frames').mkdir(exist_ok=True)
        (stage.output/'frames/frame.png').write_bytes(b'required frame')
        (stage.output/'report.txt').write_text('verified report')
        path = str(stage.logical/'report.txt')
        item = {'path':path,'role':'report','format':'text','open_with':'editor','editability':'text',
                'reopen':{'status':'passed','evidence':'read'},'limitations':[]}
        handoff = {'task':'report','source_files':[], 'output_files':[path],'previews':[],
                   'checks':[{'name':'read','status':'passed','evidence':'read'}],'warnings':[],
                   'delivery':{'source_status':'not_applicable','source_note':'report','files':[item]}}
        (stage.output/'handoff.json').write_text(json.dumps(handoff))
        delivery = {'id':stage.logical.name,'files':[{**item, 'size':15,
                     'sha256':hashlib.sha256(b'verified report').hexdigest()}], 'technical_status':'passed'}
        (stage.output/'delivery-manifest.json').write_text(json.dumps(delivery))
        return {'ok':True,'output_dir':str(stage.logical),'delivery_record':delivery,'handoff':handoff}

    def test_append_only_promotion_preserves_sources_media_and_approved_baseline(self):
        result = self.contract()
        self.assertEqual(list(self.stage.destination.iterdir()), [])
        result = self.stage.publish(result)
        self.assertEqual(json.loads(self.stage.receipt.read_text())['files'], inventory(self.stage.destination))
        self.assertFalse(self.stage.output.exists())
        self.assertEqual((self.stage.destination/'frames/frame.png').read_bytes(), b'required frame')
        self.assertEqual(self.baseline.read_bytes(), b'approved source')
        self.assertEqual(result['output_transaction']['status'], 'published')
        self.stage.quarantine()
        self.assertEqual(json.loads(self.stage.receipt.read_text())['status'], 'published')

    def test_failure_or_cancellation_keeps_partial_files_out_of_project(self):
        (self.stage.output/'temporary.blend').write_bytes(b'half written')
        self.stage.quarantine()
        self.assertFalse(self.stage.destination.exists())
        self.assertTrue((self.stage.output/'temporary.blend').exists())
        self.assertEqual(self.baseline.read_bytes(), b'approved source')
        self.assertEqual(json.loads(self.stage.receipt.read_text())['status'], 'quarantined')

    def test_invalid_contract_and_changed_bytes_never_publish(self):
        result = self.contract()
        (self.stage.output/'report.txt').write_text('changed after verification')
        with self.assertRaisesRegex(ValueError, 'cambiato'): self.stage.publish(result)
        self.assertEqual(list(self.stage.destination.iterdir()), [])
        result = self.contract(); result['output_dir'] = '/mnt/user-data/uploads'
        with self.assertRaises(ValueError): self.stage.publish(result)
        self.assertEqual(self.baseline.read_bytes(), b'approved source')

    def test_symlinks_hard_links_and_special_files_are_rejected(self):
        result = self.contract()
        link = self.stage.output/'link'; link.symlink_to(self.baseline)
        with self.assertRaisesRegex(ValueError, 'Link'):self.stage.publish(result)
        link.unlink(); os.link(self.baseline, link)
        with self.assertRaisesRegex(ValueError, 'Hard link'):self.stage.publish(result)
        link.unlink(); os.mkfifo(link)
        with self.assertRaisesRegex(ValueError, 'speciale'):self.stage.publish(result)

    def test_two_tasks_with_same_filenames_do_not_share_working_files(self):
        second = TaskStaging(self.root/'state', self.project, 'workspace', 'rh-job-abcdef123456'); second.prepare()
        first = self.contract(); other = self.contract(second)
        self.stage.publish(first); second.publish(other)
        self.stage.output.mkdir()
        (self.stage.output/'report.txt').write_text('private later modification')
        self.assertEqual((second.destination/'report.txt').read_text(), 'verified report')
        self.assertEqual((self.stage.destination/'report.txt').read_text(), 'verified report')

    def test_crash_after_rename_is_idempotent_but_existing_revision_is_never_replaced(self):
        result = self.contract(); self.stage.publish(result)
        import shutil
        shutil.copytree(self.stage.destination, self.stage.output)
        self.stage.record('validating')  # Commit renamed, journal write lost on restart.
        self.stage.publish(result)
        (self.stage.destination/'report.txt').write_text('user edit')
        with self.assertRaises(ValueError): self.stage.publish(result)
        self.assertEqual((self.stage.destination/'report.txt').read_text(), 'user edit')

    def test_promotion_copy_failure_leaves_previous_version_untouched(self):
        result = self.contract()
        with patch('righaven.task_staging.shutil.copytree', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.stage.publish(result)
        self.assertFalse(self.stage.destination.with_name('.'+self.stage.destination.name+'-publish').exists())
        self.assertEqual(list(self.stage.destination.iterdir()), [])
        self.assertEqual(self.baseline.read_bytes(), b'approved source')

    def test_mounts_write_only_output_and_current_job_telemetry(self):
        progress = create_job(self.project, self.stage.logical.name, 'workspace', 'codex', 'fixture')
        calls=[]
        self.stage.mounts(lambda path,target,read_only=False:calls.append((Path(path), target, read_only)) or target, progress)
        writable=[path for path,_,ro in calls if not ro]
        self.assertEqual(writable, [self.stage.output, progress.parent])
        self.assertIn((self.project, '/mnt/user-data', True), calls)
        with patch.dict(os.environ, {'RIGHAVEN_ISOLATED_OUTPUT':'1'}):update(progress,'completed')
        self.assertEqual(read_status(progress)['phase'], 'finalizing')

    def test_inspection_is_owned_and_rejects_symlinked_parents_and_path_traversal(self):
        from righaven.task_staging import open_job_file
        create_job(self.project, self.stage.logical.name, 'workspace', 'codex', 'fixture')
        self.contract()
        with open_job_file(self.root/'state', self.project, str(self.stage.logical/'report.txt')) as stream:
            self.assertEqual(stream.read(), b'verified report')
        (self.stage.output/'escape').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            open_job_file(self.root/'state', self.project, str(self.stage.logical/'escape/project/approved.blend'))
        for name in ('/etc/passwd', str(self.stage.logical/'../approved.blend')):
            with self.assertRaises(ValueError):open_job_file(self.root/'state', self.project, name)
        other = self.root/'other';other.mkdir()
        with self.assertRaises(OSError):open_job_file(self.root/'state', other, str(self.stage.logical/'report.txt'))

    def test_explicit_verified_recovery_can_publish_previously_quarantined_staging(self):
        result = self.contract(); self.stage.quarantine()
        self.assertFalse(self.stage.destination.exists())
        self.stage.publish(result)
        self.assertEqual((self.stage.destination/'report.txt').read_text(), 'verified report')
        self.assertEqual(self.baseline.read_bytes(), b'approved source')

    def test_private_worker_journal_does_not_lose_events_when_recent_history_rolls_over(self):
        from righaven.task_staging import forward_worker_events
        from righaven.audit_log import page
        progress=create_job(self.project,self.stage.logical.name,'workspace','codex','fixture')
        with forward_worker_events(self.project,progress), patch.dict(os.environ,{'RIGHAVEN_ISOLATED_OUTPUT':'1'}):
            for number in range(100):update(progress,'running_tool','Operation '+str(number))
        self.assertEqual(len(read_status(progress)['events']),60)
        events=page(self.project,limit=200)['events']
        operations=[e['operation'] for e in events if e['operation'].startswith('Operation ')]
        self.assertEqual(operations,['Operation '+str(n) for n in range(100)])
