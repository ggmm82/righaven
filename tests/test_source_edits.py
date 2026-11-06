"""Editable copies keep original deliveries and reject stale, oversized and escaped sources."""
from pathlib import Path
import tempfile
import unittest
from righaven import source_edits
from righaven.source_packages import digest


class SourceEdits(unittest.TestCase):
    def test_saving_a_copy_preserves_original_and_records_pending_integration(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);original=root/'outputs/report.md';original.parent.mkdir();original.write_text('Original')
            result=source_edits.save(root,'/mnt/user-data/outputs/report.md',digest(original),'Edited')
            self.assertEqual(original.read_text(),'Original')
            copy=root/result['path'].removeprefix('/mnt/user-data/')
            self.assertEqual(copy.read_text(),'Edited');self.assertFalse(result['exports_regenerated'])
            self.assertEqual(source_edits.edits(root/'.righaven-project')[0]['path'],result['path'])
            self.assertEqual(oct(copy.stat().st_mode&0o777),'0o600')
            with self.assertRaisesRegex(ValueError,'changed'):
                source_edits.save(root,'/mnt/user-data/outputs/report.md','0'*64,'Do not overwrite')
            self.assertEqual(original.read_text(),'Original')

    def test_hidden_paths_binary_formats_and_symlink_escape_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'outputs').mkdir();hidden=root/'private.txt';hidden.write_text('private')
            with self.assertRaisesRegex(ValueError,'supported text'):
                source_edits.save(root,'/mnt/user-data/private.txt',digest(hidden),'edit')
            link=root/'outputs/link.txt';link.symlink_to(hidden)
            with self.assertRaises(ValueError):source_edits.save(root,'/mnt/user-data/outputs/link.txt',digest(hidden),'edit')
            binary=root/'outputs/file.pdf';binary.write_bytes(b'%PDF')
            with self.assertRaisesRegex(ValueError,'supported text'):
                source_edits.save(root,'/mnt/user-data/outputs/file.pdf',digest(binary),'text')
            bad=root/'outputs/bad.txt';bad.write_bytes(b'\xff')
            with self.assertRaisesRegex(ValueError,'UTF-8'):
                source_edits.save(root,'/mnt/user-data/outputs/bad.txt',digest(bad),'text')
            with self.assertRaisesRegex(ValueError,'1 MiB'):
                source_edits.save(root,'/mnt/user-data/outputs/bad.txt',digest(bad),'è'*(source_edits.MAX_BYTES//2+1))
