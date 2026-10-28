"""Version identity must outlive reviews, retries and pruned attempt histories."""
from pathlib import Path
import unittest
from righaven.revisions import annotate, number_attempts


class RevisionTests(unittest.TestCase):
    def test_identical_exports_are_labeled_as_source_or_metadata_updates(self):
        attempts=[]
        for index,source in enumerate(('source-a','source-b','source-b'),1):
            attempts.append({'context':{'purpose':'delivery'},'version_number':index,'started_at':str(index),
                'output_files':['/data/'+str(index)],'delivery_record':{'id':str(index),'files':[
                    {'role':'export','sha256':'same-product'},{'role':'source_archive','sha256':source}]}})
        project={'steps':[{'id':'deliver','attempts':attempts}]}
        deliveries=annotate([{'id':str(i)} for i in (1,2,3)],project,None,lambda root,path:Path(path) if path else None)
        self.assertEqual(deliveries[1]['change_kind'],'sources')
        self.assertEqual(deliveries[2]['change_kind'],'metadata')
        self.assertEqual(deliveries[2]['content_version'],1)
        self.assertTrue(deliveries[2]['unchanged_content'])

    def test_version_numbers_are_stable_and_reviews_point_to_their_own_target(self):
        def attempt(identifier, purpose, at, **extra):
            return {'started_at': at, 'finished_at': at, 'context': {'purpose': purpose},
                    'delivery_record': {'id': identifier}, 'output_files': ['/data/'+identifier], **extra}
        first=attempt('first','delivery','1')
        sample=attempt('sample','preview','2')
        check=attempt('check','review','3',validated=True,quality_review={
            'product_path':'/data/first','status':'needs_revision','contract_hash':'old','revision_actions':[{'action':'Correct'}]})
        second=attempt('second','delivery','4',status='running')
        project={'steps':[{'id':'step','attempts':[first,sample,check,second]}],
                 'product_path':'/data/first','acceptance':{'hash':'new'}}
        self.assertTrue(number_attempts(project))
        self.assertFalse(number_attempts(project))
        deliveries=[{'id':name,'title':name} for name in ('first','sample','check','second')]
        by_id={d['id']:d for d in annotate(deliveries,project,None,lambda _, p: Path(p) if p else None)}
        self.assertEqual(by_id['first']['version'],1)
        self.assertEqual(by_id['second']['version'],2)
        self.assertEqual(by_id['second']['execution_status'],'running')
        self.assertEqual(by_id['sample']['category'],'sample')
        self.assertEqual(by_id['check']['category'],'review')
        self.assertEqual(by_id['check']['review']['target_version'],1)
        self.assertFalse(by_id['check']['review']['matches_current_brief'])
        self.assertEqual(by_id['check']['review']['correction_count'],1)
        project['steps'][0]['attempts']=[second]  # Old histories may be pruned.
        third=attempt('third','delivery','5')
        project['steps'][0]['attempts'].append(third)
        number_attempts(project)
        self.assertEqual(second['version_number'],2)
        self.assertEqual(third['version_number'],3)

    def test_selected_preview_is_a_sample_even_with_a_legacy_version_number(self):
        attempt={'context':{'purpose':'preview'},'version_number':1,'output_files':['/data/two-pages.pdf'],
                 'delivery_record':{'id':'sample'},'status':'completed'}
        project={'product_path':'/data/two-pages.pdf','steps':[{'id':'sample','attempts':[attempt]}]}
        number_attempts(project)
        result=annotate([{'id':'sample','title':'Two-page proof','current':True}],project,None,lambda _,p:Path(p) if p else None)[0]
        self.assertEqual(result['category'],'sample')
        self.assertIsNone(result['version'])

class VersionStateTests(unittest.TestCase):
    def test_candidates_and_partial_files_do_not_inherit_old_approval(self):
        import tempfile
        from righaven.source_packages import digest
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);attempts=[];deliveries=[]
            for i in range(1,4):
                path=root/f'v{i}.txt';path.write_text(str(i))
                attempts.append({'started_at':str(i),'finished_at':str(i),'status':'completed' if i<3 else 'paused',
                    'validated':i<3,'context':{'purpose':'delivery'},'output_files':[str(path)],
                    'delivery_record':{'id':str(i),'technical_status':'passed' if i<3 else 'not_verified',
                        'files':[{'path':str(path),'role':'export','sha256':digest(path)}]}})
                deliveries.append({'id':str(i),'title':str(i)})
            review={'product_path':str(root/'v1.txt'),'sha256':digest(root/'v1.txt'),'status':'passed','contract_hash':'current'}
            attempts.append({'validated':True,'quality_review':review,'finished_at':'4','context':{'purpose':'review'},'output_files':[]})
            project={'acceptance':{'hash':'current'},'steps':[{'id':'step','attempts':attempts}]}
            artifact=lambda _,p: Path(p) if p and Path(p).is_file() else None
            result=annotate(deliveries,project,root,artifact)
            self.assertEqual([d['version_state'] for d in result],['approved','candidate','partial'])
            project['acceptance']['hash']='changed'
            annotate(deliveries,project,root,artifact)
            self.assertEqual(deliveries[0]['version_state'],'candidate')
            (root/'v1.txt').write_text('changed after review')
            project['acceptance']['hash']='current';annotate(deliveries,project,root,artifact)
            self.assertEqual(deliveries[0]['version_state'],'candidate')
