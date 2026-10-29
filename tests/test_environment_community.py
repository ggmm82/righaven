"""Real persistent lifecycle contracts: review integrity, privacy and portable sharing."""
import concurrent.futures
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from righaven import state, gallery, gallery_feedback as feedback, environment_history as history, environment_sharing


class EnvironmentCommunityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.override = patch.object(state, 'STATE', self.root); self.override.start(); self.addCleanup(self.override.stop)

    def pack(self, version='1.0.0'):
        manifest = dict(gallery.get_pack('skill-d2'))
        manifest.update(id='community-test', author='publisher', version=version)
        return gallery.publish_pack(manifest)['pack']

    def test_ratings_are_per_user_and_version_and_not_favorites(self):
        self.pack()
        first = feedback.write('community-test', '1.0.0', 'alice@example.test', 'Useful for diagrams', 4)
        feedback.write('community-test', '1.0.0', 'bob', 'Needs clearer instructions', 2)
        second = feedback.write('community-test', '1.0.0', 'alice@example.test', 'Improved after using the guide', 5)
        self.assertEqual(first['id'], second['id'])
        result = feedback.list_feedback('community-test', 'bob')
        self.assertEqual(result['ratings'][0]['count'], 2)
        self.assertEqual(result['ratings'][0]['average'], 3.5)
        self.assertNotIn('alice@example.test', json.dumps(result))
        self.assertTrue(next(item for item in result['items'] if item['body'].startswith('Needs'))['mine'])
        self.assertEqual(gallery.get_pack('community-test')['stars'], 0)
        self.pack('2.0.0')
        feedback.write('community-test', '2.0.0', 'alice@example.test', 'New release', 3)
        self.assertEqual(len(feedback.list_feedback('community-test', 'alice')['ratings']), 2)
        self.assertEqual(feedback.list_feedback('community-test', 'alice', '1.0.0')['total'], 2)
        with self.assertRaises(ValueError): feedback.write('community-test', 'unknown', 'alice', 'Wrong version', 4)

    def test_discussion_author_reply_report_and_moderation(self):
        self.pack()
        review = feedback.write('community-test', '1.0.0', 'reader', 'Instructions missing', 2)
        reply = feedback.write('community-test', '1.0.0', 'publisher', 'Thanks, fixed in next release', parent=review['id'])
        self.assertTrue(reply['author_reply'])
        with self.assertRaises(ValueError): feedback.write('community-test', '1.0.0', 'publisher', 'Self review', 5)
        with self.assertRaises(ValueError): feedback.write('community-test', '1.0.0', 'reader', 'Deep reply', parent=reply['id'])
        feedback.report(review['id'], 'publisher', 'Please investigate')
        self.assertEqual(feedback.reports()[0]['reports'], 1)
        self.assertEqual(feedback.list_feedback('community-test', 'reader')['total'], 2)
        feedback.remove(review['id'], 'different-user')
        self.assertEqual(feedback.list_feedback('community-test', 'reader')['total'], 2)
        feedback.moderate(review['id'], 'Spam confirmed')
        result = feedback.list_feedback('community-test', 'reader')
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['ratings'], [])
        with self.assertRaises(ValueError):feedback.write('community-test', '1.0.0', 'reader', 'Evade moderation', 4)

    def test_concurrent_writes_keep_one_rating_and_pagination(self):
        self.pack()
        # Cold schema creation is itself concurrent, as on multiple Gateway workers.
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda n: feedback.write('community-test', '1.0.0', 'same-user', f'Attempt {n}', 4), range(12)))
        self.assertEqual(feedback.list_feedback('community-test', 'viewer')['total'], 1)
        for n in range(25): feedback.write('community-test', '1.0.0', 'user'+str(n), f'Comment {n}')
        first = feedback.list_feedback('community-test', 'viewer', limit=20)
        second = feedback.list_feedback('community-test', 'viewer', offset=20, limit=20)
        self.assertEqual(len(first['items']), 20); self.assertEqual(len(second['items']), 6)
        self.assertFalse({r['id'] for r in first['items']} & {r['id'] for r in second['items']})

    def test_separate_gateway_processes_share_rating_transaction(self):
        import os,subprocess,sys
        self.pack()
        code="from righaven import gallery_feedback as f;f.write('community-test','1.0.0','same-user','Concurrent Gateway process',4)"
        children=[subprocess.Popen([sys.executable,'-c',code],env={**os.environ,'RIGHAVEN_STATE':str(self.root)},stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(6)]
        try:
            for child in children:
                output,error=child.communicate(timeout=30)
                self.assertEqual(child.returncode,0,error.decode())
        finally:
            for child in children:
                if child.poll() is None:child.kill();child.wait()
        self.assertEqual(feedback.list_feedback('community-test','viewer')['ratings'][0]['count'],1)

    def profile(self):
        return {'name':'diagrams','display_name':'Diagrams','purpose':'Editable diagrams',
                'instructions':'Keep layout readable', 'skills':['skill-workspace','skill-d2','skill-quality-review'],
                'tools':['d2'],'disabled':[], 'deployment':{'mode':'on_demand','tool_versions':{'d2':'builtin'}}}

    def test_sharing_preserves_methods_and_versions_without_private_files(self):
        manifest = environment_sharing.manifest(self.profile(), 'owner', 'my-diagrams', '1.0.0',
                    'Diagrams', 'Editable diagrams', 'Diagrammi', 'Diagrammi modificabili')
        result = gallery.publish_pack(manifest)['pack']
        self.assertIn('skill-quality-review', result['skills'])
        self.assertEqual(result['environment']['tool_versions'], {'d2':'builtin'})
        self.assertEqual(result['skill_prompt_template'], 'Keep layout readable')
        self.assertFalse(result['verified'])
        profile = self.profile(); profile['skills'].append('private-method')
        with self.assertRaisesRegex(ValueError, 'Custom skill'):environment_sharing.manifest(profile, 'owner', 'my-diagrams', '2.0.0', 'D', 'D', 'D', 'D')
        profile = self.profile(); profile['deployment']['tool_versions']['d2'] = 'a'*64
        with self.assertRaisesRegex(ValueError, 'portable'):environment_sharing.manifest(profile, 'owner', 'my-diagrams', '2.0.0', 'D', 'D', 'D', 'D')

    def test_history_is_owner_scoped_and_deduplicated(self):
        from righaven import environments
        def owner_path(user):return self.root/user/'righaven-environments.json'
        with patch.object(environments, 'preferences_path', side_effect=owner_path):
            profile = self.profile()
            history.record('alice', profile); history.record('alice', profile)
            self.assertEqual(len(history.read('alice', 'diagrams')), 1)
            self.assertEqual(history.read('bob', 'diagrams'), [])
            profile['instructions'] = 'Improve contrast'
            history.record('alice', profile)
            self.assertEqual(len(history.read('alice', 'diagrams')), 2)
            self.assertEqual(history.read('alice', 'diagrams')[0]['definition']['instructions'], 'Keep layout readable')
            with self.assertRaises(ValueError):history.read('alice','../bob')

    def test_search_matches_all_terms_across_capabilities(self):
        pack = self.pack()
        pack['version'] = '3.0.0'
        pack['i18n']['en']['description'] = 'Editable diagrams'
        gallery.publish_pack(pack)
        result = gallery.list_packs(query='d2 diagrams',locale='en')
        self.assertGreater(result['total'],0)
        self.assertTrue(all('d2' in json.dumps(item).lower() for item in result['packs']))
