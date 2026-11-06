"""Calibre adapter contracts and runtime verification, independent of project domain."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import calibre_cli as cli
from scripts.install_righaven import install_binaries
from righaven.deliveries import build_delivery
from righaven.source_packages import inspect_ebook, verify_archive


class CalibreTests(unittest.TestCase):
    def test_structural_css_bridge_uses_sdk_rules_and_fails_closed_on_missing_or_bad_node_result(self):
        import sys,types
        from scripts import calibre_job
        module=types.ModuleType('calibre.ebooks.oeb.polish.check.css')
        module.stylelint_js=lambda:[('stylelint-bundle.min.js','trusted bundle'),('stylelint.js','native rules')]
        values=[{'type':'results','results':{'output':'native result'}}]
        with patch.dict(sys.modules,{module.__name__:module}),patch.object(calibre_job.shutil,'which',return_value='/node'),patch.object(calibre_job.subprocess,'run',return_value=subprocess.CompletedProcess([],0,json.dumps(values),'')) as run:
            self.assertEqual(calibre_job.check_css_without_webengine(['p { color: red; }']),values)
            request=json.loads(run.call_args.kwargs['input'])
            self.assertEqual(request['scripts'][1],['stylelint.js','native rules'])
            self.assertEqual(request['sources'],['p { color: red; }'])
            self.assertEqual(run.call_args.kwargs['timeout'],120)
            run.return_value=subprocess.CompletedProcess([],1,'','native failure')
            with self.assertRaisesRegex(RuntimeError,'native failure'):calibre_job.check_css_without_webengine(['p{}'])
            run.return_value=subprocess.CompletedProcess([],0,'[]','')
            with self.assertRaisesRegex(ValueError,'incompleta'):calibre_job.check_css_without_webengine(['p{}'])
        with patch.dict(sys.modules,{module.__name__:module}),patch.object(calibre_job.shutil,'which',return_value=None):
            with self.assertRaisesRegex(RuntimeError,'Node'):calibre_job.check_css_without_webengine(['p{}'])
    def test_missing_link_is_blocking_without_relabelling_native_warnings(self):
        from types import SimpleNamespace
        from scripts.calibre_job import issue_record
        issue=SimpleNamespace(rule_id='DanglingLink',level=1,name='page.xhtml',line=3)
        record=issue_record(issue,1)
        self.assertEqual(record['severity'],'warning')
        self.assertTrue(record['blocking'])
        issue.rule_id='NonLinearItems'
        self.assertFalse(issue_record(issue,1)['blocking'])
        issue.level=2
        self.assertEqual(issue_record(issue,1)['severity'],'error')
        self.assertTrue(issue_record(issue,1)['blocking'])

    def test_structural_checks_need_no_display_and_retain_real_failures(self):
        import os
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ,{}), patch.object(cli.shutil,'which',return_value='/usr/bin/xvfb-run'):
            with patch.object(cli,'supervise',return_value=(subprocess.CompletedProcess([],0,'verified',''),{})) as supervised:
                argv=['calibre-debug','--exec-file',str(Path(cli.__file__).with_name('calibre_job.py')),'--','check','book.epub','result.json']
                self.assertEqual(cli.run(argv,Path(temp),'Structural'),'verified')
                self.assertEqual(supervised.call_args.args[0],argv)
            with patch.object(cli,'supervise',return_value=(subprocess.CompletedProcess([],139,'crashed',''),{})):
                with self.assertRaisesRegex(RuntimeError,'139'):
                    cli.run(argv,Path(temp),'Structural')

    def test_structural_helper_is_identified_through_the_installed_cli_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            link=Path(temp)/'calibre-cli';link.symlink_to(Path(cli.__file__).resolve())
            helper=str(Path(cli.__file__).resolve().with_name('calibre_job.py'))
            argv=['calibre-debug','--exec-file',helper,'--','check','book.epub','result.json']
            with patch.object(cli,'__file__',str(link)),patch.object(cli.shutil,'which',return_value=None),patch.object(cli,'supervise',return_value=(subprocess.CompletedProcess([],0,'checked',''),{})) as run:
                self.assertEqual(cli.run(argv,Path(temp),'Structure'),'checked')
                self.assertEqual(run.call_args.args[0],argv)

    def test_official_multi_binary_distribution_uses_declared_root_launchers(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); destination = root / 'app'; links = root / 'links'; links.mkdir()
            (destination / 'bin').mkdir(parents=True)
            for name in ('ebook-convert', 'ebook-meta'):
                (destination / name).write_text('root launcher')
                (destination / 'bin' / name).write_text('bundled duplicate')
            app = {'executable': 'calibre-cli', 'binary': 'ebook-convert',
                   'binary_paths': {'ebook-convert': 'ebook-convert', 'ebook-meta': 'ebook-meta'}}
            self.assertEqual(install_binaries(app, destination, links), destination / 'ebook-convert')
            self.assertEqual((links / 'ebook-meta').resolve(), destination / 'ebook-meta')
            with self.assertRaisesRegex(RuntimeError, 'sovrascrivo'):
                install_binaries(app, destination, links)
            app['binary_paths'] = {'escape': '../outside'}
            (root / 'outside').write_text('outside')
            with self.assertRaisesRegex(RuntimeError, 'interno'):
                install_binaries(app, destination, links)
            self.assertFalse((links / 'escape').exists())

    def test_scope_inputs_no_overwrite_and_zip_paths(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, 'ROOT', Path(temp)):
            root = Path(temp); source = root / 'input.txt'; source.write_text('original')
            with self.assertRaisesRegex(ValueError, 'workspace'):
                cli.invoke('inspect', {'input': '/etc/passwd'})
            with self.assertRaisesRegex(ValueError, 'sovrascrivo'):
                cli.invoke('convert', {'input': str(source), 'output': str(source)})
            (root / 'link.txt').symlink_to(source)
            with self.assertRaisesRegex(ValueError, 'link'):
                cli.invoke('convert', {'input': str(root / 'link.txt'), 'output': str(root / 'new.epub')})
            bad = root / 'bad.epub'
            with zipfile.ZipFile(bad, 'w') as z:
                z.writestr('../outside', 'unsafe')
            with self.assertRaisesRegex(ValueError, 'sicura'):
                cli.safe_book(bad)
            self.assertEqual(source.read_text(), 'original')

    def test_native_failure_exposes_exit_and_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, 'ROOT', Path(temp)), patch.object(cli, 'environment', return_value=Path(temp)):
            source = Path(temp) / 'source.txt'; source.write_text('original')
            with patch.object(cli.shutil, 'which', return_value='/usr/bin/xvfb-run'), patch.object(cli, 'supervise', return_value=(subprocess.CompletedProcess([], -11, 'crashed', ''), {})):
                with self.assertRaisesRegex(RuntimeError, 'exit -11'):
                    cli.invoke('convert', {'input': str(source), 'output': str(Path(temp) / 'out.pdf')})
            self.assertEqual(source.read_text(), 'original')

    def test_renderer_crash_gets_one_software_attempt_preserving_input_and_attempt_history(self):
        import os
        with tempfile.TemporaryDirectory() as temp,patch.object(cli,'ROOT',Path(temp)),patch.dict(os.environ,{'QT_QUICK_BACKEND':'initial'}):
            root=Path(temp);source=root/'source.epub';source.write_bytes(b'original source');output=root/'out.pdf';output.write_bytes(b'partial')
            first=subprocess.CompletedProcess([],139,'Segmentation fault','')
            def run(argv,folder,key,**kwargs):
                if key.endswith('-software-render'):
                    self.assertFalse(output.exists());self.assertEqual(os.environ['QT_QUICK_BACKEND'],'software')
                    output.write_bytes(b'%PDF-real fixture')
                    return subprocess.CompletedProcess([],0,'native conversion completed',''),{}
                return first,{}
            with patch.object(cli.shutil,'which',return_value='/usr/bin/xvfb-run'),patch.object(cli,'supervise',side_effect=run) as supervise:
                text=cli.run(['ebook-convert',str(source),str(output)],root,'Conversione')
            self.assertEqual(supervise.call_count,2);self.assertEqual(source.read_bytes(),b'original source')
            self.assertIn('Rendering recuperato',text);self.assertEqual(os.environ['QT_QUICK_BACKEND'],'initial')

    def test_memory_failure_and_cli_errors_are_never_hidden_by_renderer_recovery(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(cli,'ROOT',Path(temp)),patch.object(cli.shutil,'which',return_value='/usr/bin/xvfb-run'):
            source=Path(temp)/'source.epub';source.write_text('source')
            for code,stats in [(139,{'oom_kills':1}),(2,{})]:
                with patch.object(cli,'supervise',return_value=(subprocess.CompletedProcess([],code,'error',''),stats)) as invoke:
                    with self.assertRaises(RuntimeError):cli.run(['ebook-convert',str(source),str(Path(temp)/'out.pdf')],Path(temp),'Export')
                    self.assertEqual(invoke.call_count,1)

    def test_headless_backend_uses_software_opengl_inside_a_supervised_virtual_display(self):
        import os
        with tempfile.TemporaryDirectory() as temp, patch.object(cli,'ROOT',Path(temp)), patch.dict(os.environ, {'RIGHAVEN_OUTPUT_DIR':temp,'QT_QUICK_BACKEND':'software'}):
            cli.environment()
            self.assertEqual(os.environ['QT_QPA_PLATFORM'],'xcb')
            self.assertEqual(os.environ['CALIBRE_HEADLESS_PLATFORM'],'xcb')
            self.assertNotIn('QT_QUICK_BACKEND',os.environ)
            self.assertEqual(os.environ['QSG_RHI_BACKEND'],'opengl')
            self.assertEqual(os.environ['LIBGL_ALWAYS_SOFTWARE'],'1')
            with patch.object(cli.shutil,'which',return_value='/usr/bin/xvfb-run'), patch.object(cli,'supervise',return_value=(subprocess.CompletedProcess([],0,'ok',''),{})) as run:
                self.assertEqual(cli.run(['ebook-convert','source.xhtml','output.epub'],Path(temp),'Conversione'),'ok')
                argv=run.call_args.args[0]
                self.assertEqual(argv[0],'/usr/bin/xvfb-run')
                self.assertEqual(argv[-3:],['ebook-convert','source.xhtml','output.epub'])
                self.assertIn('-nolisten tcp',argv[2])
            with patch.object(cli.shutil,'which',return_value=None):
                with self.assertRaisesRegex(RuntimeError,'xvfb-run'):
                    cli.run(['ebook-convert','source.xhtml','output.epub'],Path(temp),'Conversione')

    def test_unpack_marker_prevents_silent_cross_format_repack(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(cli, 'ROOT', Path(temp)), patch.object(cli, 'environment', return_value=Path(temp)):
            root = Path(temp); sources = root / 'Sources'; sources.mkdir()
            (sources / '.righaven-source.json').write_text(json.dumps({'format': '.epub'}))
            with patch.object(cli, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'formato originale'):
                    cli.invoke('pack', {'source': str(sources), 'output': str(root / 'bad.docx')})
                run.assert_not_called()
            with self.assertRaisesRegex(ValueError, 'argomenti'):
                cli.invoke('convert', {'input': 'a', 'output': 'b', 'arbitrary_args': '--unsafe'})

    def test_mcp_discovery_and_error_are_explicit(self):
        requests = [ {'id': 1, 'method': 'initialize'}, {'id': 2, 'method': 'tools/list'},
            {'id': 3, 'method': 'tools/call', 'params': {'name': 'calibre.inspect', 'arguments': {'input': '/outside.epub'}}} ]
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO('\n'.join(map(json.dumps, requests)))), contextlib.redirect_stdout(output):
            cli.mcp()
        replies = list(map(json.loads, output.getvalue().splitlines()))
        self.assertEqual(len(replies[1]['result']['tools']), 8)
        self.assertEqual(replies[1]['result']['tools'][0]['name'], 'calibre.convert')
        self.assertIn('error', replies[2])

    def test_mcp_structural_failure_stops_batch_even_if_process_itself_succeeded(self):
        request = {'id': 1, 'method': 'tools/call', 'params': {'name': 'calibre.check', 'arguments': {'input': 'fixture'}}}
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(json.dumps(request))), contextlib.redirect_stdout(output), patch.object(cli, 'invoke', return_value={'status': 'failed', 'issues': [{'severity': 'error'}]}):
            cli.mcp()
        self.assertTrue(json.loads(output.getvalue())['result']['isError'])

    def test_delivery_ignores_model_reopen_claim_when_native_check_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); book = root / 'book.epub'; book.write_bytes(b'not valid')
            item = {'path': str(book), 'role': 'editable_source', 'reopen': {'status': 'passed'}}
            handoff = {'task': 'Any project', 'checks': [], 'delivery': {'source_status': 'included', 'source_note': '', 'files': [item]}}
            with patch('righaven.source_packages.subprocess.run', return_value=subprocess.CompletedProcess([], 2, '', 'Missing referenced image')):
                result = build_delivery(handoff, root, agent='workspace', tools=['calibre'])
            self.assertEqual(result['technical_status'], 'needs_revision')
            self.assertIn('Missing referenced image', result['issues'][0])
            self.assertEqual(inspect_ebook(book, root, native=False)['status'], 'not_run')

    def test_relocated_archive_checks_native_resources_and_retains_warnings(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = root / 'Sources.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('book.epub', 'fixture; native result mocked explicitly')
            warning = {'severity': 'warning', 'message': 'Unused image'}
            def check(argv, **kwargs):
                relocated = Path(kwargs['cwd'])
                self.assertNotEqual(relocated, root)
                self.assertTrue((relocated / 'book.epub').is_file())
                self.assertEqual(kwargs['env']['RIGHAVEN_OUTPUT_DIR'], str(relocated))
                return subprocess.CompletedProcess(argv, 0, json.dumps({'status': 'passed', 'spine': [{'file': 'chapter.xhtml'}], 'resources': 3, 'issues': [warning]}), '')
            with patch('righaven.source_packages.subprocess.run', side_effect=check):
                result = verify_archive(archive, native=True)
            self.assertEqual(result['status'], 'passed')
            self.assertEqual(result['checks'][0]['warnings'], [warning])
            self.assertEqual(verify_archive(archive, native=False)['status'], 'not_run')
