"""Shared methods: owner choices, verified trials and private reusable drafts."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import collaboration, projects, state


class SharedMethodTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.proof = self.root / 'outputs/sample.md'; self.proof.parent.mkdir(); self.proof.write_text('Verified sample')
        self.strategy = {'method':'Layout from structured content','reason':'Check content and layout separately',
                         'state':'exploring','alternatives':[{'method':'Layout from structured content',
                         'reason':'Reusable typesetting with editable sources','status':'tested','tools':['typst'],
                         'evidence_paths':['/mnt/user-data/outputs/sample.md']}]}
        self.draft = {'title':'Structured publication','summary':'Create a checked publication from structured content',
                      'when':'Publishing a document with a consistent layout','attach_required':[], 'outputs':['PDF and editable sources'],
                      'phases':[{'title':'Representative sample','detail':'Check a sample against the agreed requirements','checkpoint':True},
                                {'title':'Delivery','detail':'Produce and reopen the exports and editable sources','checkpoint':False}],
                      'skills':['skill-typst'],'tools':['typst'],'guidance':'Compare the sample with the requirements before extending it'}
        projects.create_plan(self.root,'Produce a document',[],strategy=self.strategy)
        # A loose file is not proof that the production workflow was exercised.
        path=self.root/'.righaven-project/project.json';project=json.loads(path.read_text())
        project['steps']=[{'id':'sample','agent':'typst','goal':'Produce a representative sample','depends_on':[],
                           'status':'completed','attempts':[{'status':'completed','validated':True,'output_files':[str(self.proof)]}]}]
        state.atomic_json(path,project)


    def choose(self):
        return collaboration.choose(self.root,collaboration.view(self.root)['signature'],1,'Keep editable sources',['typst'])

    def test_stale_or_unavailable_choice_rejected_and_owner_history_survives(self):
        old=collaboration.view(self.root)['signature']; self.choose()
        result=collaboration.view(self.root)
        self.assertEqual(result['decision']['method'],self.strategy['method'])
        self.assertEqual(len(result['history']),1)
        self.choose()
        self.assertEqual(len(collaboration.view(self.root)['history']),1, 'Retrying the saved choice is idempotent')
        self.assertEqual(projects.read_project(self.root)['method_decision']['note'],'Keep editable sources')
        changed=copy.deepcopy(self.strategy);changed['reason']='A new constraint matters'
        projects.create_plan(self.root,'',[],strategy=changed)
        with self.assertRaisesRegex(ValueError,'changed'):
            collaboration.choose(self.root,old,1,'',['typst'])
        with self.assertRaisesRegex(ValueError,'unavailable'):
            collaboration.choose(self.root,collaboration.view(self.root)['signature'],1,'',[])
        self.assertEqual(len(collaboration.view(self.root)['history']),1)

    def test_recipe_needs_owner_choice_and_current_evidence_then_stays_unsaved(self):
        with self.assertRaisesRegex(ValueError,'owner must choose'):
            collaboration.propose(self.root,'alice',self.draft,['skill-typst'],['typst'])
        self.choose()
        with patch.object(state,'STATE',self.root/'state'):
            proposed=collaboration.propose(self.root,'alice',self.draft,['skill-typst'],['typst'])
            self.assertFalse(proposed['saved']);self.assertFalse(proposed['shared'])
            self.assertFalse((state.STATE/'recipes').exists())
            draft=collaboration.recipe_draft(self.root)
            self.assertEqual(draft['phases'],self.draft['phases'])
            self.assertNotIn('/mnt/user-data',json.dumps(draft))
            from righaven.recipes import create
            saved=create('alice',draft,['skill-typst'])
            self.assertEqual(saved['it']['attach_required'],[])
            self.assertFalse(saved['shared'])
        self.proof.write_text('Changed sample')
        with self.assertRaisesRegex(ValueError,'evidence changed'):
            collaboration.recipe_draft(self.root)

    def test_untested_disabled_and_secret_recipe_drafts_are_rejected(self):
        self.choose()
        with self.assertRaisesRegex(ValueError,'fuori catalogo'):
            collaboration.propose(self.root,'alice',self.draft,['skill-typst'],[])
        secret={**self.draft,'guidance':'Use api_key=sk-secret-do-not-save-this-123456789012345'}
        with self.assertRaisesRegex(ValueError,'credentials'):
            collaboration.propose(self.root,'alice',secret,['skill-typst'],['typst'])
        untested=copy.deepcopy(self.strategy);untested['alternatives'][0]['status']='candidate';untested['alternatives'][0]['evidence_paths']=[]
        projects.create_plan(self.root,'',[],strategy=untested)
        with self.assertRaisesRegex(ValueError,'Test the chosen method'):
            collaboration.propose(self.root,'alice',self.draft,['skill-typst'],['typst'])

    def test_modified_method_invalidates_candidate_without_deleting_history(self):
        self.choose();collaboration.propose(self.root,'alice',self.draft,['skill-typst'],['typst'])
        changed=copy.deepcopy(self.strategy);changed['reason']='Reconsider after a new user constraint'
        projects.create_plan(self.root,'',[],strategy=changed)
        view=collaboration.view(self.root)
        self.assertFalse(view['recipe_available']);self.assertTrue(view['recipe_stale'])
        self.assertEqual(len(view['history']),1)
        with self.assertRaisesRegex(ValueError,'No current recipe'):
            collaboration.recipe_draft(self.root)
