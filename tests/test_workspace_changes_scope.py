"""The chat's file-changes list shows products, not assignment process records."""
from pathlib import Path
import tempfile
import unittest

try:
    from righaven_core.workspace_changes.scanner import scan_workspace_roots
    from righaven_core.workspace_changes.types import WorkspaceRoot
except ImportError:
    import os
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS') == '1':
        raise
    scan_workspace_roots = None


@unittest.skipIf(scan_workspace_roots is None, 'Requires the pinned Gateway runtime')
class WorkspaceChangeScopeTests(unittest.TestCase):
    def test_job_records_and_previews_are_left_out_but_user_folders_named_work_stay(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = root / 'workspace' / 'rh-job-dbb3d5fc9bfc'
            for name in ('volume.pdf', 'libro.typ', 'work/commands/abc/status.json', 'work/build_book.py', 'previews/page-01.png'):
                (job / name).parent.mkdir(parents=True, exist_ok=True); (job / name).write_text('x')
            (root / 'work' / 'notes.md').parent.mkdir(parents=True); (root / 'work' / 'notes.md').write_text('mine')
            (root / 'project' / 'previews' / 'cover.png').parent.mkdir(parents=True); (root / 'project' / 'previews' / 'cover.png').write_text('mine')
            fields = WorkspaceRoot.__dataclass_fields__ if hasattr(WorkspaceRoot, '__dataclass_fields__') else WorkspaceRoot.model_fields
            arguments = {'host_path': root, 'virtual_prefix': '/mnt/user-data/outputs'}
            if 'name' in fields:
                arguments['name'] = 'outputs'
            snapshot = scan_workspace_roots([WorkspaceRoot(**arguments)], include_text=False)
            paths = sorted(p.removeprefix('/mnt/user-data/outputs/') for p in snapshot.files)
        self.assertEqual(paths, ['project/previews/cover.png', 'work/notes.md',
                                 'workspace/rh-job-dbb3d5fc9bfc/libro.typ', 'workspace/rh-job-dbb3d5fc9bfc/volume.pdf'])


if __name__ == '__main__':
    unittest.main()
