import json
from pathlib import Path
import unittest
from righaven import experience,lessons
from righaven.antigravity_cli import result_error
from righaven.work_results import failure_info

class LearningNoteFormatTests(unittest.TestCase):
    def test_worker_notes_in_both_real_legacy_formats_survive_without_autoapproval(self):
        from test_production_observations import ProductionObservationsTests
        fixture=ProductionObservationsTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.report.unlink();work=fixture.output/'work';work.mkdir()
        note={'tool':'soundcraft','category':'tool_operation','finding':'Use the explicit overwrite parameter for repeat exports.','benefit':'Avoid output collisions.'}
        for payload in [{'lessons':[note]}, [{'tool':'soundcraft','lesson':'Use numeric positions for imports.','evidence':'A textual position was rejected.'}]]:
            (work/'tool-lessons.json').write_text(json.dumps(payload))
            self.assertEqual(experience.collect(fixture.workspace,fixture.library,'thread'),1)
            self.assertEqual(experience.collect(fixture.workspace,fixture.library,'thread'),0)
        values=experience.entries(fixture.library)
        self.assertEqual(len(values),2)
        self.assertTrue(all(v['observation']['status']=='needs_generalization' for v in values))
        self.assertEqual(lessons.propose_findings(fixture.library,'thread'),[])
        self.assertEqual(lessons.accepted(fixture.library),set())
        self.assertEqual(len(lessons.pending(fixture.library)),2)

    def test_antigravity_only_reports_quota_when_cli_supplies_that_cause(self):
        self.assertEqual(failure_info(result_error({'status':'INTERRUPTED'}))['code'],'work_error')
        self.assertEqual(failure_info('Antigravity: incarico non completato; verifica modello, login e quota')['code'],'work_error')
        self.assertEqual(failure_info(result_error({'status':'ERROR','error':{'code':'RESOURCE_EXHAUSTED'}}))['code'],'provider_quota')
        self.assertEqual(failure_info(result_error({'status':'ERROR','error':{'message':'Authentication failed'}}))['code'],'provider_auth')
