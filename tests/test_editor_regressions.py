"""Editor regressions from live sessions, without provider credentials or user files."""
import unittest
from unittest.mock import patch
from righaven import tool_versions,editor_presence
from scripts.release_pipeline import release_tag


class EditorRegressions(unittest.TestCase):
    def test_builtin_is_catalog_selection_not_a_record_identifier(self):
        with patch.object(tool_versions,'read',side_effect=AssertionError('builtin must never be read')):
            self.assertEqual(tool_versions.resolved({'jupyter':'builtin'},wait=True),{})
            self.assertEqual(tool_versions.packages({'jupyter':'builtin'}),{})
        pin='a'*64
        self.assertEqual(tool_versions.resolved({'jupyter':'builtin','duckdb':pin}),{'duckdb':pin})
        with self.assertRaisesRegex(ValueError,'non valida'):tool_versions.packages({'jupyter':'invalid'})

    def test_presence_is_owner_scoped_per_tab_and_expires(self):
        with patch.dict(editor_presence._SESSIONS,{},clear=True),patch.object(editor_presence.time,'monotonic',return_value=10):
            editor_presence.update('alice','chat','session','graphics','effectcraft','tab1')
            editor_presence.update('alice','chat','session','graphics','effectcraft','tab2')
            self.assertEqual(editor_presence.activity('bob'),[])
            editor_presence.update('alice','chat','session','graphics','effectcraft','tab1',False)
            self.assertEqual(len(editor_presence.activity('alice')),1)
            with patch.object(editor_presence.time,'monotonic',return_value=101):self.assertEqual(editor_presence.activity('alice'),[])

    def test_semantic_release_retries_reuse_tag_and_main_advances_patch(self):
        floor=patch('scripts.release_pipeline.Path.read_text',return_value='0.7.5\n')  # VERSION, independent of the checkout
        floor.start();self.addCleanup(floor.stop)
        with patch('scripts.release_pipeline.api',return_value=[{'tag_name':'v0.7.5','target_commitish':'old'}]):
            self.assertEqual(release_tag('repo','new',True,{}),'v0.7.6')
            self.assertEqual(release_tag('repo','old',True,{}),'v0.7.5')
        with patch('scripts.release_pipeline.api',return_value=[]):
            self.assertEqual(release_tag('repo','new',False,{'pull_request':19,'run_id':2,'run_attempt':1}),'v0.7.5-rc.pr.19.2.1')
        with patch('scripts.release_pipeline.api',return_value=[{'tag_name':'v0.7.5','target_commitish':'old'}]):
            self.assertEqual(release_tag('repo','new',False,{'pull_request':19,'run_id':2,'run_attempt':1}),'v0.7.6-rc.pr.19.2.1')
        floor.stop()
        with patch('scripts.release_pipeline.Path.read_text',return_value='0.8.0\n'),patch('scripts.release_pipeline.api',return_value=[{'tag_name':'v0.7.5','target_commitish':'old'}]):
            self.assertEqual(release_tag('repo','new',True,{}),'v0.8.0','raising VERSION starts the next minor release')
            self.assertEqual(release_tag('repo','new',False,{'pull_request':20,'run_id':3,'run_attempt':1}),'v0.8.0-rc.pr.20.3.1')
        floor.start()
