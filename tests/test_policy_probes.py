"""Policy sheets can require executable probes on the exact finished product."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import patch

from righaven import policy_book, policy_probes, policy_workflow, projects
from righaven.source_packages import digest

REQUIRE = os.getenv('RIGHAVEN_REQUIRE_TOOLS') == '1'


def sheet(*checks):
    value = policy_book.validate_sheet({'id': 'archive', 'title': 'Archiviazione', 'final_checks': list(checks)})
    return {**value, 'revision': policy_book.revision(value)}


def pdf(path, text='Hello probe'):
    """A minimal valid PDF with one line of text and a correct xref table."""
    stream = f'BT /F1 18 Tf 72 720 Td ({text}) Tj ET'.encode()
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    body, offsets = b'%PDF-1.4\n', []
    for number, content in enumerate(objects, 1):
        offsets.append(len(body))
        body += b'%d 0 obj\n' % number + content + b'\nendobj\n'
    xref = len(body)
    body += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objects) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offsets)
    body += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objects) + 1, xref)
    path.write_bytes(body)
    return path


def local(probe, path):
    """Run the probe's own command directly on the host (same argv and verdict as in the container)."""
    argv = [str(path) if item == 'FILE' else item for item in policy_probes.PROBES[probe]['argv']]
    completed = subprocess.run(argv, capture_output=True, text=True, timeout=120)
    passed, evidence = policy_probes.verdict(probe, completed.returncode, completed.stdout, completed.stderr)
    return {'status': 'passed' if passed else 'failed', 'evidence': evidence, 'tool': policy_probes.PROBES[probe]['tool']}


class SheetTests(unittest.TestCase):
    def test_probes_come_from_a_closed_catalog_and_leave_the_reviewer_contract(self):
        value = sheet({'id': 'structure', 'requirement': 'PDF integro', 'method': 'structural', 'probe': 'pdf_structure'},
                      {'id': 'tone', 'requirement': 'Tono adatto', 'method': 'content'})
        self.assertEqual([c['id'] for c in policy_book.contract(value, None)['criteria']], ['tone'])
        with self.assertRaisesRegex(ValueError, 'probe tra'):
            sheet({'id': 'shell', 'requirement': 'x', 'method': 'structural', 'probe': 'rm -rf /'})
        self.assertEqual({p['id'] for p in policy_probes.catalog()}, set(policy_probes.PROBES))


class RealFileTests(unittest.TestCase):
    def require(self, program):
        if shutil.which(program) is None:
            if REQUIRE:
                self.fail(program + ' is required (RIGHAVEN_REQUIRE_TOOLS=1)')
            self.skipTest(program + ' not installed')

    def test_pdf_text_passes_on_text_and_fails_on_a_blank_page(self):
        self.require('pdftotext')
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(local('pdf_text', pdf(Path(directory) / 'a.pdf'))['status'], 'passed')
            self.assertEqual(local('pdf_text', pdf(Path(directory) / 'b.pdf', text=''))['status'], 'failed')
            broken = Path(directory) / 'c.pdf'; broken.write_bytes(b'not a pdf')
            self.assertEqual(local('pdf_text', broken)['status'], 'failed')

    def test_pdf_structure_detects_a_damaged_file(self):
        self.require('qpdf')
        with tempfile.TemporaryDirectory() as directory:
            good = pdf(Path(directory) / 'a.pdf')
            self.assertEqual(local('pdf_structure', good)['status'], 'passed')
            broken = Path(directory) / 'b.pdf'; broken.write_bytes(good.read_bytes()[:200])
            self.assertEqual(local('pdf_structure', broken)['status'], 'failed')

    def test_media_streams_reads_real_audio_and_rejects_other_bytes(self):
        self.require('ffprobe')
        with tempfile.TemporaryDirectory() as directory:
            sound = Path(directory) / 'tone.wav'
            with wave.open(str(sound), 'wb') as stream:
                stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(8000); stream.writeframes(b'\0\1' * 8000)
            result = local('media_streams', sound)
            self.assertEqual(result['status'], 'passed')
            self.assertIn('audio:pcm_s16le', result['evidence'])
            fake = Path(directory) / 'fake.mp4'; fake.write_bytes(b'\0' * 1024)
            self.assertEqual(local('media_streams', fake)['status'], 'failed')

    def test_no_secrets_flags_a_private_key(self):
        # Not required in CI: the worker image pins gitleaks 8.30; distribution packages may predate `gitleaks dir`.
        if shutil.which('gitleaks') is None:
            self.skipTest('gitleaks not installed')
        with tempfile.TemporaryDirectory() as directory:
            clean = Path(directory) / 'clean'; clean.mkdir(); (clean / 'notes.txt').write_text('Nothing to hide here.')
            self.assertEqual(local('no_secrets', clean / 'notes.txt')['status'], 'passed')
            leaked = Path(directory) / 'leak'; leaked.mkdir()
            (leaked / 'config.py').write_text('aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEYZ"\nAWS_ACCESS_KEY_ID = "AKIAZ7Q4Y3XW2V5U6T8R"\n')
            self.assertEqual(local('no_secrets', leaked / 'config.py')['status'], 'failed')

    def test_wrong_file_type_fails_without_running_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            text = Path(directory) / 'a.txt'; text.write_text('x')
            result = policy_probes.run('pdf_structure', text, image='never-used')
            self.assertEqual(result['status'], 'failed')
            self.assertIn('.pdf', result['evidence'])


class VerdictTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.product = Path(temp.name) / 'report.pdf'; self.product.write_bytes(b'%PDF-1.4 fixture')
        self.sheet = sheet({'id': 'structure', 'requirement': 'PDF integro', 'method': 'structural', 'probe': 'pdf_structure'},
                           {'id': 'text', 'requirement': 'Testo ricercabile', 'method': 'structural', 'probe': 'pdf_text', 'critical': False})
        self.value = {'product_path': 'outputs/report.pdf', 'policy_plan': {'sheets': [self.sheet]}}
        self.saved = {}
        patches = [patch.object(projects, 'artifact_path', return_value=self.product),
                   patch.object(projects, 'save_probe_results', side_effect=lambda w, r: self.saved.update(r))]
        for item in patches:
            item.start(); self.addCleanup(item.stop)

    def run_probes(self, outcomes):
        calls = []

        def runner(probe, path):
            calls.append((probe, Path(path)))
            return {'status': outcomes[probe], 'evidence': probe + ' evidence', 'tool': 'fixture', 'at': 'now'}
        policy_workflow.run_probes(Path('/workspace'), self.value, runner)
        self.value['policy_probes'] = dict(self.saved)
        return calls

    def test_probe_only_sheet_passes_without_a_reviewer_once_probes_pass(self):
        target = digest(self.product)
        self.assertEqual(policy_workflow.sheet_verdict(None, self.value, self.sheet, target),
                         {'status': 'pending', 'probes_pending': ['structure', 'text']})
        calls = self.run_probes({'pdf_structure': 'passed', 'pdf_text': 'failed'})
        self.assertEqual(calls, [('pdf_structure', self.product), ('pdf_text', self.product)])
        # A non-critical probe failure is evidence, not a block.
        self.assertEqual(policy_workflow.sheet_verdict(None, self.value, self.sheet, target)['status'], 'passed')
        self.assertEqual(self.run_probes({}), [])  # results are reused for the same file

    def test_a_critical_probe_failure_fails_the_sheet_and_a_new_version_is_probed_again(self):
        self.run_probes({'pdf_structure': 'failed', 'pdf_text': 'passed'})
        verdict = policy_workflow.sheet_verdict(None, self.value, self.sheet, digest(self.product))
        self.assertEqual(verdict['status'], 'failed')
        self.assertEqual(verdict['findings'][0]['method'], 'probe:pdf_structure')
        self.product.write_bytes(b'%PDF-1.4 corrected')
        self.assertEqual(policy_workflow.sheet_verdict(None, self.value, self.sheet, digest(self.product))['status'], 'pending')
        self.assertEqual(len(self.run_probes({'pdf_structure': 'passed', 'pdf_text': 'passed'})), 2)


if __name__ == '__main__':
    unittest.main()
