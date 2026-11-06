import re
from pathlib import Path
import unittest

from righaven.worker_context import build_prompt


class WorkerContextTests(unittest.TestCase):
    def test_real_skill_bundle_has_accessible_protocols_without_eager_expansion(self):
        root = Path(__file__).resolve().parents[1]
        # Gateway tests mount only /review; this check runs in the repository suite.
        if not (root / 'skills/custom').exists():
            self.skipTest('Repository skill sources required')
        workspace = root / 'skills/custom/skill-workspace'
        text = (workspace / 'SKILL.md').read_text()
        self.assertLess(len(text), 6000)
        for reference in re.findall(r'\]\((references/[^)]+)\)', text):
            self.assertTrue((workspace / reference).is_file(), reference)
        selected = [text, (root / 'skills/custom/skill-vectorcraft/SKILL.md').read_text(),
                    (root / 'skills/custom/skill-designcraft/SKILL.md').read_text()]
        prompt = build_prompt({'agent':'workspace','task':'Make an editable illustrated sample',
            'purpose':'preview','capability_policy':{'allowed':['vectorcraft','designcraft'],'blocked':['blender']}}, selected, '/mnt/user-data/outputs/sample')
        self.assertLess(len(prompt), 23000)
        self.assertIn('blender', prompt)
        self.assertIn('DELIVERY.md', prompt)
        self.assertIn('LEARNING.md', prompt)
        self.assertIn('Make an editable illustrated sample', prompt)
        # Large JSON protocols remain available for the actual handoff phase.
        self.assertGreater(len((workspace / 'references/DELIVERY.md').read_text()), 5000)
        self.assertNotIn('"source_files":', prompt)
