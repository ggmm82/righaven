"""Regressions for unattended score imports and portable native source checks."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from scripts.production_tools import score_preflight
from scripts.production_job import local_reference
from righaven.source_packages import mesh_dependencies
from righaven.source_packages import inspect_production, inspect_tree


class ProductionToolsTests(unittest.TestCase):
    def test_progress_and_command_drilldown_recognize_the_single_tool_catalog(self):
        from righaven.progress import APPS, tool_label
        from righaven.command_details import describe
        catalog=json.loads((Path(__file__).resolve().parents[1]/'versions.lock.json').read_text())
        self.assertEqual(APPS,{a['id'] for a in catalog['applications']}|{'workspace'})
        for app,action in [('musescore','convert'),('ifcopenshell','execute'),('manim','render'),
                           ('opentimelineio','pack'),('pymeshlab','apply')]:
            command=app+'-cli call '+action+' {}'
            self.assertIn(app.capitalize(),tool_label(command))
            self.assertEqual(describe(command)['tool'],app+'-cli')
            self.assertEqual(describe(command)['action'],action)

    def test_malformed_scores_rejected_before_native_gui_can_wait_for_a_dialog(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,content in [('invalid.musicxml',b'not XML'),('invalid.mscx',b'<wrong/>'),('invalid.mid',b'not MIDI')]:
                source=root/name;source.write_bytes(content)
                with self.assertRaises(ValueError):score_preflight(source)
            source=root/'unsafe.mscz'
            with zipfile.ZipFile(source,'w') as archive:archive.writestr('../score.mscx','<museScore/>')
            with self.assertRaises(ValueError):score_preflight(source)
            source=root/'valid.musicxml';source.write_text('<score-partwise version="4.0"/>');score_preflight(source)

    def test_missing_remote_and_external_media_do_not_pass_as_local_bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'clip.mp4').write_bytes(b'fixture')
            with patch.dict(os.environ,{'RIGHAVEN_WORKSPACE_ROOT':temp}):
                self.assertEqual(local_reference(root,'clip.mp4'),root/'clip.mp4')
                for value in ('missing.mp4','https://example.com/clip.mp4','/etc/passwd','file://remote/clip.mp4'):
                    with self.assertRaises(ValueError):local_reference(root,value)

    def test_source_checks_reject_nonportable_timeline_and_mesh_before_native_loading(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);project=root/'timeline.otio'
            for value in ('missing.mp4','/etc/passwd','file:///etc/passwd','https://example.com/clip.mp4'):
                project.write_text(json.dumps({'media_reference':{'target_url':value}}))
                with self.assertRaises(ValueError):inspect_production(project,root,native=False)
            (root/'clip.mp4').write_bytes(b'media')
            project.write_text(json.dumps({'media_reference':{'target_url':'clip.mp4'}}))
            self.assertEqual(inspect_production(project,root,native=False)['status'],'not_run')
            mesh=root/'project.mlp';mesh.write_text('<MeshLabProject><MeshGroup><MLMesh filename="missing.ply"/></MeshGroup></MeshLabProject>')
            with self.assertRaises(ValueError):inspect_production(mesh,root,native=False)
            (root/'missing.ply').write_bytes(b'mesh')
            self.assertEqual(inspect_production(mesh,root,native=False)['status'],'not_run')

    def test_mesh_project_checks_materials_and_textures_not_only_geometry_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'project.mlp').write_text('<MeshLabProject><MeshGroup><MLMesh filename="mesh.obj"/></MeshGroup></MeshLabProject>')
            (root/'mesh.obj').write_text('mtllib material.mtl\nv 0 0 0\n')
            (root/'material.mtl').write_text('newmtl paint\nmap_Kd texture.png\n')
            with self.assertRaises(ValueError):mesh_dependencies(root/'project.mlp',root,portable=True)
            (root/'texture.png').write_bytes(b'texture')
            self.assertEqual(len(mesh_dependencies(root/'project.mlp',root,portable=True)),3)
            (root/'material.mtl').write_text('map_Kd /etc/passwd\n')
            with self.assertRaises(ValueError):mesh_dependencies(root/'project.mlp',root,portable=True)

    def test_final_timeline_and_mesh_sources_require_a_portable_package(self):
        from righaven.deliveries import build_delivery
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for extension in ('.otio','.mlp'):
                project=root/('project'+extension);project.write_text('native fixture')
                handoff={'task':'Delivery','delivery':{'source_status':'included','source_note':'Native source',
                    'files':[{'path':str(project),'role':'editable_source','reopen':{'status':'passed'}}]},'checks':[]}
                with patch('righaven.deliveries.inspect_production',return_value={'status':'passed','dependencies':1}):
                    report=build_delivery(handoff,root,purpose='delivery')
                self.assertTrue(any('pacchetto sorgenti ZIP' in issue for issue in report['issues']))
                self.assertIn('ZIP',report['files'][0]['open_with'])
                archive=root/'readme-only.zip'
                with zipfile.ZipFile(archive,'w') as zipped:zipped.writestr('README.md','This is not the project')
                handoff['delivery']['files'].append({'path':str(archive),'role':'source_archive','reopen':{'status':'passed'}})
                with patch('righaven.deliveries.inspect_production',return_value={'status':'passed','dependencies':1}):
                    report=build_delivery(handoff,root,purpose='delivery')
                self.assertTrue(any('deve contenere il progetto '+extension in issue for issue in report['issues']))


    def test_archive_inspection_never_executes_delivered_python(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);sentinel=root/'executed'
            (root/'scene.py').write_text('from pathlib import Path\nPath('+repr(str(sentinel))+').touch()')
            inspect_tree(root,native=True)
            self.assertFalse(sentinel.exists())


if __name__=='__main__':unittest.main()
