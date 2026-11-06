"""A local export cannot satisfy an owner-selected external destination."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import connection_outcomes as outcomes,projects,journeys,state
from righaven.progress import utcnow


class ConnectionOutcomes(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'outputs';self.output.mkdir()
        self.proof=self.output/'connection-verification.json'
        self.record={'id':'warehouse','database':'requested','host':'db.example','write_schema':'dbo'}
        self.binding={'owner':'alice','ids':['warehouse'],'uses':{'warehouse':'destination'},'write':['warehouse']}
        self.value={'connections':self.binding,'acceptance':{'hash':'current'},'steps':[]}
        self.role={'connections':['warehouse']}
        self.proof_data={'connection_id':'warehouse','host':'db.example','database':'requested','schema':'dbo','operation':'write','status':'passed',
                         'objects':['dbo.orders'],'read_back':{'status':'passed','rows_checked':12,'checked_at':utcnow()}}
        self.mock=patch('righaven.connections._read',return_value=self.record);self.mock.start();self.addCleanup(self.mock.stop)

    def evidence(self):
        self.proof.write_text(json.dumps(self.proof_data))
        return outcomes.receipts(self.root,self.value,self.role,{'connection_receipts':[{'id':'warehouse','verification_path':str(self.proof)}]},[str(self.proof)])

    def test_unused_destination_cannot_be_hidden_by_local_database_or_approval(self):
        (self.output/'local.duckdb').write_text('local only')
        self.assertEqual(outcomes.status(self.root,self.value)[0]['status'],'pending')
        with self.assertRaisesRegex(ValueError,'Requested destinations'):outcomes.require_complete(self.root,self.value)
        with self.assertRaisesRegex(ValueError,'requested destinations'):journeys._require_sources({},self.value)
        # Permission alone does not mandate execution for an unspecified resource.
        ordinary=copy.deepcopy(self.value);ordinary['connections']['uses']={}
        self.assertEqual(outcomes.status(self.root,ordinary),[])
        outcomes.require_complete(self.root,ordinary)

    def test_verified_readback_is_bound_to_role_grant_current_contract_and_saved_hash(self):
        receipt=self.evidence()
        self.value['steps']=[{'attempts':[{'status':'completed','validated':True,'connection_receipts':receipt}]}]
        self.assertEqual(outcomes.status(self.root,self.value)[0]['status'],'passed')
        outcomes.require_complete(self.root,self.value)
        self.record['database']='different destination'
        self.assertEqual(outcomes.status(self.root,self.value)[0]['status'],'pending')
        self.record['database']='requested'
        self.value['acceptance']['hash']='new goal'
        self.assertEqual(outcomes.status(self.root,self.value)[0]['status'],'pending')
        self.value['acceptance']['hash']='current';self.proof.write_text('{}')
        self.assertEqual(outcomes.status(self.root,self.value)[0]['status'],'pending')

    def test_wrong_destination_missing_readback_and_undeclared_role_are_rejected(self):
        for field,value in [('database','local'),('schema','elsewhere'),('host','local')]:
            original=self.proof_data[field];self.proof_data[field]=value
            with self.assertRaisesRegex(ValueError,'selected destination'):self.evidence()
            self.proof_data[field]=original
        self.proof_data['read_back']['status']='not_tested'
        with self.assertRaisesRegex(ValueError,'reading back'):self.evidence()
        self.proof_data['read_back']['status']='passed';self.role['connections']=[]
        with self.assertRaisesRegex(ValueError,'authorized role'):self.evidence()

    def test_deferral_is_explicit_and_does_not_invent_a_database_operation(self):
        self.binding['deferred']=['warehouse']
        self.assertEqual(outcomes.status(self.root,self.value),[{'id':'warehouse','status':'deferred','evidence_path':None}])
        outcomes.require_complete(self.root,self.value)
        self.assertEqual(self.value['steps'],[])

    def test_intake_goal_survives_compaction_and_generated_resume(self):
        goal='Create data in my selected database, transform it and deliver a business report'
        journeys.start(self.root,'data-pipeline',{'goal':goal},mode='first_result')
        projects.create_plan(self.root,'A local example',[])
        projects.sync_acceptance(self.root,[])
        project=projects.read_project(self.root)
        self.assertIn(goal,project['acceptance']['user_requests'])
        old=project['acceptance']['hash']
        projects.sync_acceptance(self.root,['Continue the saved guided project with harness_journey. Read attachments and my choices first; present the next useful result. Do not ask me to write technical configuration. Connections are optional.'])
        self.assertEqual(projects.read_project(self.root)['acceptance']['hash'],old)
