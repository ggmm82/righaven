"""Native filesystem access when the app home sits beneath a virtual mount prefix.

Matches production RIGHAVEN_HOME=/mnt/user-data without needing access to /mnt
in the test runner. Both virtual and physical paths must resolve once only.
"""
import os
import errno
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
try:
    from righaven_core.sandbox.local.local_sandbox import LocalSandbox,PathMapping
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    LocalSandbox=None


@unittest.skipIf(LocalSandbox is None,'Requires the native Gateway filesystem')
class NativeFilePaths(unittest.TestCase):
    def build(self,root):
        home=root/'user-data';owned=home/'users/alice/threads/one/user-data'
        for name in ('uploads','outputs','workspace'):(owned/name).mkdir(parents=True)
        mappings=[PathMapping(container_path=str(home),local_path=str(owned)),
                  *[PathMapping(container_path=str(home/name),local_path=str(owned/name),read_only=name=='uploads') for name in ('uploads','outputs','workspace')]]
        return home,owned,LocalSandbox('local:alice:one',path_mappings=mappings)

    def test_native_paths_are_not_resolved_twice_and_uploads_remain_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            home,owned,sandbox=self.build(Path(directory))
            file=owned/'uploads/schema.sql';file.write_text('CREATE TABLE orders(id INTEGER);\n')
            virtual=str(home/'uploads/schema.sql')
            self.assertEqual(sandbox.read_file(virtual),sandbox.read_file(str(file)))
            self.assertEqual(sandbox.read_file(str(file),start_line=1,end_line=1),'CREATE TABLE orders(id INTEGER);')
            self.assertTrue(any('schema.sql' in p for p in sandbox.list_dir(str(owned/'uploads'))))
            matches,_=sandbox.glob(str(owned/'uploads'),'*.sql');self.assertIn(virtual,matches)
            matches,_=sandbox.grep(str(owned/'uploads'),'CREATE TABLE');self.assertEqual(len(matches),1)
            with self.assertRaises(OSError) as blocked:sandbox.write_file(str(file),'must not replace upload')
            self.assertEqual(blocked.exception.errno,errno.EROFS)
            output=owned/'outputs/report.md';sandbox.write_file(str(output),'Report')
            self.assertEqual(sandbox.read_file(str(home/'outputs/report.md')),'Report')
            self.assertEqual(output.read_text(),'Report')

    def test_canonical_path_resolution_does_not_expose_other_users_or_follow_escaping_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);home,owned,sandbox=self.build(root)
            secret=home/'users/bob/threads/two/user-data/uploads/private.sql';secret.parent.mkdir(parents=True);secret.write_text('private')
            with self.assertRaises((FileNotFoundError,PermissionError)):sandbox.read_file(str(secret))
            (owned/'uploads/escape.sql').symlink_to(secret)
            with self.assertRaises(PermissionError):sandbox.read_file(str(owned/'uploads/escape.sql'))
            with self.assertRaises(PermissionError):sandbox.read_file(str(home/'uploads/escape.sql'))
            with self.assertRaises(PermissionError):sandbox.write_file(str(owned/'uploads/escape.sql'),'changed')
            self.assertEqual(secret.read_text(),'private')
            (owned/'uploads/escape-dir').symlink_to(secret.parent,target_is_directory=True)
            with self.assertRaises(PermissionError):sandbox.read_file(str(owned/'uploads/escape-dir/../hidden.sql'))

    def test_real_file_tools_can_read_list_search_and_reopen_a_reuploaded_attachment(self):
        from righaven_core.sandbox import tools
        with tempfile.TemporaryDirectory() as directory:
            home,owned,sandbox=self.build(Path(directory))
            for name in ('schema.sql','schema_1.sql'):(owned/'uploads'/name).write_text('CREATE TABLE orders(id INTEGER);\n')
            runtime=SimpleNamespace(state={'sandbox':{'sandbox_id':sandbox.id},'thread_data':{
                'workspace_path':str(owned/'workspace'),'uploads_path':str(owned/'uploads'),'outputs_path':str(owned/'outputs')}},context={'user_id':'alice'},config={})
            with patch.object(tools,'ensure_sandbox_initialized',return_value=sandbox),patch.object(tools,'ensure_thread_directories_exist'),patch.object(tools,'is_local_sandbox',return_value=True),patch.object(tools,'_is_disabled_skill_path',return_value=False):
                for name in ('schema.sql','schema_1.sql'):
                    text=tools.read_file_tool.func(runtime=runtime,path='/mnt/user-data/uploads/'+name)
                    self.assertIn('CREATE TABLE orders',text)
                    self.assertNotIn('Error:',text)
                listing=tools.ls_tool.func(runtime=runtime,path='/mnt/user-data/uploads')
                self.assertIn('schema_1.sql',str(listing))
                matched=tools.glob_tool.func(runtime=runtime,path='/mnt/user-data/uploads',pattern='*.sql')
                self.assertIn('schema_1.sql',str(matched))
                found=tools.grep_tool.func(runtime=runtime,path='/mnt/user-data/uploads',pattern='CREATE TABLE')
                self.assertIn('orders',str(found))

