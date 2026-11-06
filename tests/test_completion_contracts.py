import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from righaven.acceptance import contract
from righaven.context_reader import read_context
from righaven.project_skills import scoped_file
from righaven.handoff import validate_handoff
from righaven.deliveries import prepare_review_handoff, read_review
from righaven.source_packages import digest


class CompletionContractsTests(unittest.TestCase):
    def test_context_is_scoped_hash_verified_and_readable_in_bounded_pages(self):
        with TemporaryDirectory() as temp:
            root=Path(temp); text='actual project state '*1000
            reference=scoped_file(root,'control-results/plan.json',text)
            page=read_context(root,reference['path'],reference['sha256'])
            self.assertLessEqual(len(page['content']),6000)
            chunks=[page['content']]
            while page['next_offset'] is not None:
                page=read_context(root,reference['path'],reference['sha256'],page['next_offset'])
                chunks.append(page['content'])
            self.assertEqual(''.join(chunks),text)
            for path,sha in [(reference['path'],'0'*64),
                             ('/mnt/user-data/.righaven-project/../credentials/auth.json',reference['sha256']),
                             ('/mnt/user-data/uploads/private.txt',reference['sha256'])]:
                with self.assertRaises(ValueError):read_context(root,path,sha)
            other=root/'other-thread';other.mkdir()
            with self.assertRaises(ValueError):read_context(other,reference['path'],reference['sha256'])

    def test_valid_review_survives_missing_envelope_without_approving_failed_checks(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);product=root/'outputs/product.txt';product.parent.mkdir();product.write_text('current product')
            output=root/'outputs/reviewer';output.mkdir()
            report=output/'quality-review.json'
            report.write_text(json.dumps({'product_path':str(product),'product_sha256':digest(product),
                'criteria':[{'requirement_id':'request_fidelity','criterion':'Requested content',
                             'method':'content','status':'failed','evidence':'A required section is missing.'}]}))
            acceptance=contract(['Complete document'])
            original=report.read_bytes()
            self.assertTrue(prepare_review_handoff(output,root,'codex',acceptance))
            handoff=validate_handoff(output,root,require_delivery=True)
            review=read_review(handoff,output,root,'codex',acceptance)
            self.assertEqual(review['status'],'needs_revision')
            self.assertEqual(review['criteria'][0]['status'],'failed')
            self.assertEqual(report.read_bytes(),original)
            self.assertEqual(product.read_text(),'current product')
            self.assertFalse(prepare_review_handoff(output,root,'codex',acceptance))
            # Earlier real failures had a report but an invalid source_status
            # or foreign output metadata. Preserve their assessment and audit.
            broken = {**handoff, 'output_files':[str(product)],
                      'checks':[{'name':'Unresolved defect','status':'failed','evidence':'Observed defect remains.'}]}
            original_manifest=json.dumps(broken).encode()
            (output/'handoff.json').write_bytes(original_manifest)
            self.assertTrue(prepare_review_handoff(output,root,'codex',acceptance))
            repaired=validate_handoff(output,root,require_delivery=True)
            self.assertEqual(repaired['checks'][-1]['status'],'failed')
            self.assertEqual((output/'work/review-handoff-original.json').read_bytes(),original_manifest)
            (output/'handoff.json').unlink();product.write_text('changed after observation')
            with self.assertRaisesRegex(ValueError,'hash osservato'):
                prepare_review_handoff(output,root,'codex',acceptance)
            self.assertFalse((output/'handoff.json').exists())

    def test_invalid_or_foreign_review_is_not_rescued_as_success(self):
        with TemporaryDirectory() as temp:
            root=Path(temp);output=root/'review';output.mkdir();report=output/'quality-review.json'
            for value in [None,{'product_path':'/etc/hosts','criteria':[]},
                          {'product_path':str(report),'criteria':[]}]:
                report.write_text(json.dumps(value))
                with self.assertRaises(ValueError):prepare_review_handoff(output,root,'codex')
                self.assertFalse((output/'handoff.json').exists())
