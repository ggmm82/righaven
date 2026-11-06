import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven.project_files import listing


class ProjectFiles(unittest.TestCase):
    def test_working_files_without_final_delivery_and_private_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'chat';(root/'outputs/project').mkdir(parents=True);(root/'uploads').mkdir()
            (root/'outputs/project/source.sql').write_text('SELECT 1;');(root/'uploads/brief.md').write_text('Brief')
            (root/'.secret').write_text('private');(root/'.righaven-project').mkdir();(root/'.righaven-project/private.json').write_text('{}')
            (root/'outputs/escape').symlink_to(Path(directory),target_is_directory=True)
            self.assertEqual([row['path'] for row in listing(root)['entries']],['outputs','uploads'])
            found=listing(root,query='source')['entries'];self.assertEqual([row['path'] for row in found],['outputs/project/source.sql']);self.assertEqual(found[0]['role'],'working_file')
            self.assertEqual(listing(root,'uploads')['entries'][0]['role'],'attachment')
            for path in ['../other','.righaven-project','outputs/escape','outputs/../uploads']:
                with self.assertRaises(ValueError):listing(root,path)
            self.assertEqual(listing(root,query='private')['entries'],[])

    def test_roles_pages_literal_names_and_bounded_search(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'outputs').mkdir();(root/'.righaven-project').mkdir()
            for name in ('a.sql','b.sql','literal%20name.md'):(root/'outputs'/name).write_text(name)
            (root/'.righaven-project/project.json').write_text(json.dumps({'steps':[{'attempts':[{'delivery_record':{'id':'delivery-a','files':[{'path':'/mnt/user-data/outputs/a.sql','role':'editable_source'}]}}]}]}))
            row=listing(root,'outputs',role='editable_source')['entries'][0];self.assertEqual(row['delivery_id'],'delivery-a')
            first=listing(root,'outputs',limit=1);second=listing(root,'outputs',offset=first['next_offset'],limit=1)
            self.assertNotEqual(first['entries'][0]['path'],second['entries'][0]['path'])
            self.assertEqual(listing(root,'outputs',query='%20')['entries'][0]['name'],'literal%20name.md')
            with patch('righaven.project_files.MAX_VISITED',1):self.assertTrue(listing(root,query='sql')['truncated'])
            self.assertEqual(listing(root/'new-chat')['entries'],[])
            (root/'.righaven-project/project.json').write_text('[]')
            self.assertEqual(len(listing(root,'outputs')['entries']),3)

    def test_folder_metadata_uses_visible_files_without_following_links(self):
        import os,time
        from righaven.project_files import folder_summary
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'outputs/nested').mkdir(parents=True)
            (root/'outputs/a.txt').write_bytes(b'123');(root/'outputs/nested/b.txt').write_bytes(b'4567')
            (root/'outputs/.secret').write_bytes(b'should not count')
            (root/'outputs/escape').symlink_to(root,target_is_directory=True)
            os.utime(root/'outputs/a.txt',(1700000000,1700000000))
            folder=listing(root)['entries'][0]
            self.assertEqual((folder['size'],folder['file_count'],folder['size_complete']),(7,2,True))
            file=next(row for row in listing(root,'outputs')['entries'] if row['name']=='a.txt')
            self.assertEqual(file['modified_at'],1700000000);self.assertEqual(file['size'],3)
            incomplete=folder_summary(root,'outputs',{'remaining':0,'deadline':time.monotonic()+1})
            self.assertFalse(incomplete['size_complete']);self.assertEqual(incomplete['size'],0)
            escaped=folder_summary(root,'outputs/escape',{'remaining':100,'deadline':time.monotonic()+1})
            self.assertFalse(escaped['size_complete']);self.assertEqual(escaped['size'],0)
