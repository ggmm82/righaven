import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from righaven.audit_log import append,page,export_rows
from righaven.progress import create_job,update

class AuditLogTests(unittest.TestCase):
    def test_concurrent_log_is_durable_paged_scoped_and_exportable(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                self.assertTrue(all(pool.map(lambda i:append(root,'Coordinatore','Operazione','completed',identifier=str(i)),range(220))))
            first=page(root);self.assertEqual(len(first['events']),100)
            older=page(root,before=first['next_before']);self.assertEqual(len(older['events']),100)
            self.assertLess(older['events'][-1]['seq'],first['events'][0]['seq'])
            last=first['events'][-1]['seq'];append(root,'Utente','Pausa','completed',identifier='pause')
            append(root,'Utente','Pausa','completed',identifier='pause')
            self.assertEqual(len(page(root,after=last)['events']),1)
            self.assertEqual(page(root/'other')['events'],[])
            self.assertEqual(len(''.join(export_rows(root)).splitlines()),222)
            with self.assertRaises(ValueError):page(root,after=1,before=2)

    def test_worker_events_outlive_the_sixty_event_live_window(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);path=create_job(root,'rh-job-123456abcdef','workspace','codex','fixture')
            for i in range(85):update(path,'creating',f'Operazione {i}')
            self.assertEqual(len(json.loads(path.read_text())['events']),60)
            self.assertEqual(len(page(root,limit=200)['events']),86)
            self.assertTrue(any(e['actor']=='Specialista workspace' for e in page(root)['events']))
