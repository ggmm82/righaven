"""Blender adapter boundaries, portable sources and native delivery requirements."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from scripts import blender_cli
from scripts.install_righaven import safe_extract
from righaven.deliveries import build_delivery
from righaven.source_packages import inspect_blend, verify_archive


class BlenderTests(unittest.TestCase):
    def test_adapter_rejects_external_files_and_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'scene.blend'; project.write_bytes(b'input')
            output = root / 'result.png'; output.write_bytes(b'existing')
            with patch.object(blender_cli, 'ROOT', root):
                with self.assertRaisesRegex(ValueError, 'workspace'):
                    blender_cli.invoke('inspect', {'project': '/etc/passwd'})
                (root / 'outside.blend').symlink_to('/etc/passwd')
                with self.assertRaisesRegex(ValueError, 'workspace'):
                    blender_cli.invoke('inspect', {'project': str(root / 'outside.blend')})
                with self.assertRaisesRegex(ValueError, 'sovrascrivo'):
                    blender_cli.invoke('render', {'project': str(project), 'output': str(output)})
                self.assertEqual(output.read_bytes(), b'existing')

    def test_python_error_or_missing_envelope_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); script = root / 'create.py';script.write_text('raise RuntimeError()')
            def failure(argv, *args, **kwargs):
                self.assertIn('--disable-autoexec', argv)
                self.assertEqual(argv[argv.index('--python-exit-code') + 1], '1')
                return subprocess.CompletedProcess(argv, 1, '', 'script failed'), {}
            with patch.object(blender_cli, 'ROOT', root), patch.object(blender_cli, 'supervise', side_effect=failure):
                with self.assertRaisesRegex(RuntimeError, 'script failed'):
                    blender_cli.invoke('execute', {'script': str(script)})

    def test_mcp_lists_real_tools_and_surfaces_tool_failures(self):
        requests = '\n'.join(json.dumps(r) for r in [
            {'id': 1, 'method': 'initialize', 'params': {}},
            {'id': 2, 'method': 'tools/list'},
            {'id': 3, 'method': 'tools/call', 'params': {'name': 'blender.inspect', 'arguments': {'project': '/no-file.blend'}}}])
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(requests)), contextlib.redirect_stdout(output):
            blender_cli.mcp()
        replies = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual({t['name'] for t in replies[1]['result']['tools']}, {t['name'] for t in blender_cli.TOOLS})
        self.assertIn('error', replies[2])

    def test_native_reopen_rejects_empty_scene_missing_assets_and_unsupported_caches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source = root / 'scene.blend';source.write_bytes(b'fixture')
            info = {'objects': [{'type': 'MESH'}], 'dependencies': [], 'limitations': []}
            def inspect(*args, **kwargs):
                return subprocess.CompletedProcess(args, 0, json.dumps(info), '')
            with patch('righaven.source_packages.subprocess.run', side_effect=inspect):
                self.assertEqual(inspect_blend(source, root)['status'], 'passed')
                info['dependencies'] = [{'reference': '//missing.png', 'path': str(root / 'missing.png'), 'exists': False}]
                with self.assertRaisesRegex(ValueError, 'risorsa mancante'):
                    inspect_blend(source, root)
                info['dependencies'] = [{'reference': '/mnt/user-data/input.png', 'path': '/mnt/user-data/input.png', 'exists': True}]
                with self.assertRaisesRegex(ValueError, 'non portabile'):
                    inspect_blend(source, root)
                info['dependencies'] = [];info['limitations'] = ['simulation cache']
                with self.assertRaisesRegex(ValueError, 'non collaudate'):
                    inspect_blend(source, root)
                info['limitations'] = [];info['objects'] = [{'type': 'CAMERA'}]
                with self.assertRaisesRegex(ValueError, 'senza geometria'):
                    inspect_blend(source, root)

    def test_blender_delivery_requires_real_native_project_and_never_approves_failed_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); export = root / 'output.glb'; export.write_bytes(b'fixture export')
            def item(path, role):
                return {'path': str(path), 'role': role, 'format': path.suffix, 'open_with': 'Blender',
                        'editability': 'declared fixture', 'reopen': {'status': 'passed', 'evidence': 'claim'}, 'limitations': []}
            handoff = {'task': 'Fixture', 'checks': [], 'delivery': {'source_status': 'included', 'source_note': 'fixture',
                        'files': [item(export, 'export')]}}
            result = build_delivery(handoff, root, purpose='delivery', agent='blender')
            self.assertEqual(result['technical_status'], 'needs_revision')
            result = build_delivery(handoff, root, purpose='delivery', agent='workspace', tools=['blender'])
            self.assertEqual(result['technical_status'], 'needs_revision')
            native = root / 'source.blend';native.write_bytes(b'not a blend')
            handoff['delivery']['files'].append(item(native, 'editable_source'))
            with patch('righaven.deliveries.inspect_blend', side_effect=ValueError('corrupt native file')):
                result = build_delivery(handoff, root, purpose='delivery', agent='blender')
            self.assertEqual(result['technical_status'], 'needs_revision')
            self.assertTrue(any('corrupt' in issue for issue in result['issues']))

    def test_xz_installer_retains_safe_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); archive = root / 'test.tar.xz'
            with tarfile.open(archive, 'w:xz') as tar:
                member = tarfile.TarInfo('../outside');member.size = 3
                tar.addfile(member, io.BytesIO(b'bad'))
            with self.assertRaises(ValueError):
                safe_extract(archive, root / 'runtime')
            self.assertFalse((root / 'outside').exists())


if __name__ == '__main__':
    unittest.main()
