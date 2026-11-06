"""User design revisions cannot be lost, escape scope or silently rewrite the project."""
import json
from pathlib import Path
import tempfile
import unittest
from righaven.projects import create_plan,read_project
from righaven.project_design import register,save,read
from righaven.control_memory import project_view


class ProjectDesignTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        create_plan(self.root,'Organizzare un progetto',[{'id':'idea','agent':'workspace','goal':'Definire il risultato','depends_on':[]}])
        self.source=self.root/'outputs/model.mmd';self.source.parent.mkdir();self.source.write_text('flowchart LR\n a[Idea] --> b[Result]')
        self.item={'id':'overview','title':'Idea e risultato','tool':'mermaid','source_path':str(self.source),'bindings':[{'element_id':'a','step_id':'idea'}]}
    def tearDown(self):self.temp.cleanup()
    def test_user_revision_survives_reopening_and_reaches_coordinator_without_changing_goal(self):
        original=read_project(self.root);register(self.root,[self.item],{'mermaid'})
        first=read(self.root,'overview');self.assertEqual(first['revision'],1)
        changed=save(self.root,identifier='overview',title=first['title'],tool='mermaid',text='flowchart LR\n a --> c[New idea]',expected_revision=1,actor='user')
        self.assertEqual(changed['state'],'changed');self.assertEqual(read(self.root,'overview')['revision'],2)
        self.assertEqual((self.root/'.righaven-project/designs/overview/1/model.mmd').read_text(),self.source.read_text())
        project=read_project(self.root);self.assertEqual(project['brief'],original['brief']);self.assertEqual(project['steps'],original['steps'])
        view=project_view(project);self.assertEqual(view['designs'][0]['revision'],2);self.assertNotIn('source',view['designs'][0])
        from righaven.context_reader import read_context
        reference=view['designs'][0]
        self.assertEqual(reference['sha256'],changed['sha256'])
        self.assertIn('New idea',read_context(self.root,reference['source_path'],reference['sha256'])['content'])
        self.assertIn('Result',read_context(self.root,first['source_path'],first['sha256'])['content'])

    def test_stale_team_update_and_invalid_bindings_cannot_overwrite_user_work(self):
        register(self.root,[self.item],{'mermaid'})
        save(self.root,identifier='overview',title='Idea',tool='mermaid',text='flowchart LR\n a --> c',expected_revision=1,actor='user')
        with self.assertRaisesRegex(ValueError,'ricarica'):register(self.root,[{**self.item,'expected_revision':1}],{'mermaid'})
        self.assertEqual(read(self.root,'overview')['revision'],2)
        with self.assertRaisesRegex(ValueError,'inesistente'):register(self.root,[{**self.item,'id':'bad','bindings':[{'element_id':'a','step_id':'missing'}]}],{'mermaid'})
    def test_disabled_tool_external_file_and_batch_failure_leave_no_partial_tavole(self):
        with self.assertRaisesRegex(ValueError,'disabilitata'):register(self.root,[self.item],set())
        with self.assertRaises(ValueError):register(self.root,[{**self.item,'source_path':'/etc/passwd'}],{'mermaid'})
        with self.assertRaises(ValueError):register(self.root,[self.item,{**self.item,'id':'../escape'}],{'mermaid'})
        self.assertEqual(read_project(self.root).get('designs',[]),[])
        register(self.root,[self.item],{'mermaid'});self.assertEqual(read(self.root,'overview')['revision'],1)
    def test_invalid_json_or_xml_is_rejected_without_poisoning_the_next_revision(self):
        for tool,text in [('excalidraw','[]'),('excalidraw','{"type":"excalidraw","elements":[{}],"files":[]}'),('bpmn','<invalid')]:
            with self.subTest(tool=tool):
                with self.assertRaises(ValueError):save(self.root,identifier='new',title='Idea',tool=tool,text=text)
        self.assertFalse(read_project(self.root).get('designs',[]))

class DesignInputTests(unittest.TestCase):
    def test_embedded_d2_icons_are_allowed_and_external_includes_are_not(self):
        from righaven.design_models import preflight
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/'source.d2'
            source.write_text('a: {\n icon: data:image/png;base64,ZmFrZQ==\n}')
            preflight('d2',source)
            source.write_text('a: {\n icon: https://example.com/image.png\n}')
            with self.assertRaises(ValueError):preflight('d2',source)
            source.write_text('map: @outside.d2')
            with self.assertRaises(ValueError):preflight('d2',source)
