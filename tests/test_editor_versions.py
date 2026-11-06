"""Editor provenance must not silently replace an environment's pinned CLI release."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import state,editor_catalog,editor_versions as versions,editor_documents as docs
from righaven.assignment_environments import snapshot_path


class EditorVersions(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name)
        changed=patch.object(state,'STATE',self.root/'state');changed.start();self.addCleanup(changed.stop)
        self.job='rh-job-123456abcdef';self.file=self.root/'outputs/workspace'/self.job/'drawing.svg';self.file.parent.mkdir(parents=True);self.file.write_text('<svg/>')
        self.definition=editor_catalog.editor('vectorcraft',['vectorcraft']);self.env='e'*64;self.pin='a'*64

    def snapshot(self,pin):
        path=snapshot_path(self.root,self.job);path.parent.mkdir(parents=True);path.write_text(json.dumps({'tools':['vectorcraft'],'versions':{'vectorcraft':pin},'environment_id':self.env}))

    def test_assignment_pin_wins_over_current_default(self):
        self.snapshot(self.pin);app={'id':'vectorcraft','version':'0.12.0'}
        with patch('righaven.tool_versions.read',return_value={'state':'ready','bundle':{'app':app}}),patch('righaven.tool_versions.packages',return_value={'vectorcraft':{'app':app}}),patch('righaven.environment_runtime.read',return_value={'id':self.env,'tools':['vectorcraft'],'installed_versions':{'vectorcraft':'0.12.0'}}),patch('righaven.tool_versions.software_selections') as default:
            value=versions.selection(self.root,self.file,self.definition)
        default.assert_not_called();self.assertEqual(value['editor_version'],'0.12.0');self.assertEqual(value['tool_versions'],{'vectorcraft':self.pin});self.assertEqual(value['version_origin'],'source_assignment')

    def test_old_builtin_release_is_not_replaced_by_a_new_catalog(self):
        self.snapshot('builtin')
        with patch('righaven.environment_runtime.read',return_value={'id':self.env,'tools':['vectorcraft'],'installed_versions':{'vectorcraft':'0.10.0'}}):value=versions.selection(self.root,self.file,self.definition)
        self.assertEqual(value['editor_version'],'0.10.0');self.assertEqual(value['source_environment_id'],self.env)

    def test_published_source_retains_the_creating_draft_version(self):
        snapshot={'tool_versions':{},'editor_version':'0.10.0','cli_version':'0.10.0','version_origin':'source_assignment','source_environment_id':self.env}
        with patch.object(versions,'selection',return_value=snapshot):session=docs.start(self.root,'/mnt/user-data/'+self.file.relative_to(self.root).as_posix(),'vectorcraft',['vectorcraft'])
        result=docs.publish(self.root,session['id'],0,['vectorcraft']);source=self.root/result['path'].removeprefix('/mnt/user-data/')
        selected=versions.selection(self.root,source,self.definition);self.assertEqual(selected['editor_version'],'0.10.0');self.assertEqual(selected['version_origin'],'source_revision')

    def test_prepared_source_image_is_reused_and_missing_versions_never_silently_upgrade(self):
        document={'source_environment_id':self.env,'editor_version':'0.10.0','cli_version':'0.10.0','tool_versions':{}}
        image={'id':self.env,'tools':['vectorcraft'],'image_id':'sha256:source','status':'ready'}
        with patch('righaven.environment_runtime.read',return_value=image),patch('righaven.environment_runtime.image_exists',return_value=True),patch('righaven.environment_runtime.claim_environment',side_effect=lambda record,owner:record),patch('righaven.environment_runtime.ensure') as build:
            self.assertEqual(versions.software(document,'vectorcraft','owner',None),image);build.assert_not_called()
        with patch('righaven.environment_runtime.read',return_value=None),patch('righaven.tool_versions.builtins',return_value={'vectorcraft':{'version':'0.20.0'}}),patch('righaven.tool_versions.software_selections',return_value={}),patch('righaven.tool_versions.resolved',return_value={}):
            with self.assertRaisesRegex(ValueError,'recorded editor version'):versions.software(document,'vectorcraft','owner',None)

    def test_switching_to_the_same_application_retains_the_drafts_frozen_release(self):
        snapshot={'tool_versions':{self.definition['tool']:self.pin},'editor_version':'0.10.0','cli_version':'0.10.0','source_environment_id':self.env}
        with patch.object(versions,'selection',return_value=snapshot):session=docs.start(self.root,'/mnt/user-data/'+self.file.relative_to(self.root).as_posix(),'vectorcraft',['vectorcraft'])
        with patch.object(versions,'selection') as choose_default:changed=docs.open_with(self.root,session['id'],'vectorcraft',['vectorcraft'])
        choose_default.assert_not_called();self.assertEqual(changed['editor_version'],'0.10.0');self.assertEqual(changed['tool_versions'],snapshot['tool_versions']);self.assertEqual(changed['version_origin'],'source_draft')

    def test_changing_application_does_not_inherit_an_unrelated_software_image(self):
        snapshot={'tool_versions':{},'editor_version':'0.10.0','cli_version':'0.10.0','source_environment_id':self.env}
        with patch.object(versions,'selection',return_value=snapshot):session=docs.start(self.root,'/mnt/user-data/'+self.file.relative_to(self.root).as_posix(),'vectorcraft',['vectorcraft'])
        changed=docs.open_with(self.root,session['id'],'text',['vectorcraft'])
        self.assertNotIn('source_environment_id',changed);self.assertEqual(changed['editor_version'],'builtin')
