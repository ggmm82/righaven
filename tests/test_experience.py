import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from righaven import experience, projects, lessons
from righaven.project_skills import load_compiled
from righaven.source_packages import digest
from test_project_skills import role


class ExperienceTests(unittest.TestCase):
    def test_automatic_curation_does_not_turn_every_success_into_a_lesson(self):
        experience.collect(self.workspace,self.library,'thread-a')
        all_sources=lessons.pending(self.library,source_thread='thread-a')
        meaningful=lessons.pending(self.library,source_thread='thread-a',meaningful_only=True)
        self.assertTrue(any(s['status']=='passed' for s in all_sources))
        self.assertTrue(meaningful)
        self.assertTrue(all(s['status']=='failed' or s['corrections'] for s in meaningful))
        self.assertLess(len(meaningful),len(all_sources))
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.workspace = self.root / 'user-a/project'
        self.library = self.root / 'user-a/library'
        projects.create_plan(self.workspace, 'Un progetto qualsiasi', [
            {'id':'produce','agent':'workspace','goal':'Produrre'},
            {'id':'review','agent':'workspace','goal':'Verificare'}])
        projects.sync_acceptance(self.workspace, ['Richiesta reale'])
        spec = role(); spec['tools'] = ['vectorcraft']
        projects.sync_project_context(self.workspace, [spec])
        self.spec = spec
        out = self.workspace / 'outputs/workspace/rh-job-123456abcdef'; out.mkdir(parents=True)
        self.product = out / 'product.svg'; self.product.write_text('<svg/>')
        review = self.workspace / 'outputs/reviewer'; review.mkdir()
        self.report = review / 'quality-review.json'; self.report.write_text('{"fixture":"actual report"}')
        path = self.workspace / '.righaven-project/project.json'
        data = json.loads(path.read_text()); self.contract = data['acceptance']['hash']
        data['steps'][0].update(status='completed', attempts=[{
            'status':'completed','validated':True,'role_id':'design','output_dir':str(out),
            'context':{'role':data['roles'][0]['version']},'role_scope':data['roles'][0]['scope'],'output_files':[str(self.product)]}])
        criteria = [{'requirement_id':'a','criterion':'Leggibilità delle etichette nella consegna','method':'structural','status':'passed','evidence':'Etichette lette nel prodotto'},
                    {'requirement_id':'b','criterion':'Risorse collegate portabili','method':'functional','status':'failed','evidence':'Risorsa collegata mancante'},
                    {'requirement_id':'c','criterion':'Qualità estetica','method':'visual','status':'not_run','evidence':'Visione assente'}]
        data['steps'][1].update(status='completed', attempts=[{'status':'completed','validated':True,'finished_at':'2026-10-20T01:00:00Z',
            'quality_review':{'product_path':str(self.product),'sha256':digest(self.product),'report_path':str(self.report),
             'contract_hash':self.contract,'criteria':criteria,'revision_actions':[{'requirement_id':'b','action':'Includere le risorse e riaprire il pacchetto estratto'}]}}])
        path.write_text(json.dumps(data));self.state = path

    def propose(self, sources=None):
        sources = sources or [r['id'] for r in experience.entries(self.library)]
        return lessons.learn(self.library, sources, {
            'title': 'Riaprire il pacchetto completo',
            'applies_when': 'Quando una consegna modificabile dipende da risorse collegate',
            'procedure': ['Includere le dipendenze nel pacchetto', 'Estrarre in una cartella nuova e riaprire il progetto'],
            'verification': ['Controllare che tutte le risorse siano risolte senza percorsi esterni'],
            'limits': 'Una verifica strutturale non prova la qualità estetica', 'tools': ['vectorcraft']})

    def test_capture_preserves_observed_failures_and_successes_but_not_missing_checks(self):
        self.assertEqual(experience.collect(self.workspace, self.library, 'thread-a'), 2)
        self.assertEqual(experience.collect(self.workspace, self.library, 'thread-a'), 0)
        records = experience.entries(self.library)
        self.assertEqual({r['observation']['status'] for r in records}, {'passed','failed'})
        self.assertTrue(any(r['observation']['corrections'] for r in records))
        self.assertEqual(records[0]['observation']['source_thread'],'thread-a')
        self.assertEqual(experience.entries(self.root/'user-b/library'), [])
        self.assertEqual((self.library/(records[0]['id']+'.json')).stat().st_mode & 0o777, 0o600)

    def test_next_project_compiles_relevant_experience_with_provenance_and_exclusions(self):
        experience.collect(self.workspace,self.library)
        proposal = self.propose()
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()), [])
        lessons.accept(self.library, proposal)
        other=self.root/'user-a/other'
        projects.create_plan(other,'Altro dominio',[]);projects.sync_acceptance(other,['Altro progetto'])
        projects.sync_project_context(other,[self.spec],experience_root=self.library)
        compiled=projects.read_project(other)['roles'][0]; text=load_compiled(other,compiled)
        self.assertIn('Riaprire il pacchetto completo',text)
        self.assertNotIn('Risorsa collegata mancante',text);self.assertNotIn('product_sha256',text)
        self.assertNotIn('Etichette lette nel prodotto',text)
        self.assertEqual(compiled['experience']['count'],1)
        first=compiled['version']
        for record in experience.entries(self.library):experience.exclude(self.library,record['id'])
        projects.sync_project_context(other,experience_root=self.library)
        compiled=projects.read_project(other)['roles'][0]
        self.assertEqual(compiled['experience']['count'],0);self.assertNotEqual(compiled['version'],first)
        self.assertEqual(len(experience.entries(self.library)),2)

    def test_explicit_preference_preserves_method_without_marking_checks_or_project_ready(self):
        before=json.loads(self.state.read_text())
        identifier=experience.prefer(self.workspace,self.library,'rh-job-123456abcdef',
            'Cambiare metodo dopo il campione e verificare due casi diversi','thread-a')
        self.assertEqual(json.loads(self.state.read_text()).get('status'),before.get('status'))
        record=experience.entries(self.library)[0]
        self.assertEqual(record['id'],identifier)
        self.assertEqual(record['observation']['status'],'preferred_by_user')
        self.assertEqual(record['observation']['files'][0]['sha256'],digest(self.product))
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()),[])
        proposal = self.propose([identifier])
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()),[])
        lessons.accept(self.library, proposal)
        selected = experience.select(self.library,[self.spec],projects.applications())[0]
        self.assertEqual(selected['source_statuses'], ['preferred_by_user'])
        self.assertEqual(selected['id'], proposal)
        self.assertEqual(experience.prefer(self.workspace,self.library,'rh-job-123456abcdef',
            'Cambiare metodo dopo il campione e verificare due casi diversi','thread-a'),identifier)
        self.assertEqual(len(experience.entries(self.library)),1)
        with self.assertRaises(ValueError):
            experience.prefer(self.workspace,self.library,'missing','Un metodo non verificato')

    def test_old_review_is_retained_after_the_user_changes_the_current_brief(self):
        projects.sync_acceptance(self.workspace,['Richiesta reale','Nuova modifica del brief'])
        self.assertEqual(experience.collect(self.workspace,self.library),2)
        self.assertTrue(all(r['observation']['contract_hash']==self.contract for r in experience.entries(self.library)))

    def test_version_relevance_tampering_and_changed_product(self):
        experience.collect(self.workspace,self.library)
        proposal = self.propose(); lessons.accept(self.library, proposal)
        apps=copy.deepcopy(projects.applications())
        next(a for a in apps if a['id']=='vectorcraft')['version']='future'
        selected=experience.select(self.library,[self.spec],apps)
        self.assertEqual([r['id'] for r in selected],[proposal])
        self.assertEqual(selected[0]['current_tool_versions']['vectorcraft'],'future')
        self.assertIn('vectorcraft',selected[0]['version_changes'])
        self.assertIn('verifica comandi e API',selected[0]['notice'])
        self.assertEqual(experience.select(self.library,[self.spec],[a for a in apps if a['id']!='vectorcraft']),[])
        unrelated=role();unrelated['tools']=['soundcraft']
        self.assertEqual(experience.select(self.library,[unrelated],projects.applications()),[])
        self.product.write_text('changed after review')
        self.assertEqual(experience.collect(self.workspace,self.root/'changed-library'),0)
        record=experience.entries(self.library)[0];path=self.library/(record['id']+'.json')
        record['observation']['status']='invented';path.write_text(json.dumps(record))
        self.assertEqual(len(experience.entries(self.library)),1)

    def test_technical_instructions_remain_bound_to_the_verified_tool_version(self):
        experience.collect(self.workspace,self.library)
        proposed=self.propose()
        method=copy.deepcopy(next(r for r in lessons.entries(self.library) if r['id']==proposed)['basis']['lesson'])
        method['category']='tool_operation'
        technical=lessons.learn(self.library,[r['id'] for r in experience.entries(self.library)],method)
        lessons.accept(self.library,technical)
        self.assertEqual([r['id'] for r in experience.select(self.library,[self.spec],projects.applications())],[technical])
        apps=copy.deepcopy(projects.applications())
        next(a for a in apps if a['id']=='vectorcraft')['version']='future'
        self.assertEqual(experience.select(self.library,[self.spec],apps),[])
        self.assertTrue(next(r for r in experience.summary(self.library)['lessons'] if r['id']==technical)['accepted'])

    def test_report_changes_and_unknown_producer_scope_do_not_become_reusable_experience(self):
        data=json.loads(self.state.read_text())
        data['steps'][1]['attempts'][0]['quality_review']['report_sha256']=digest(self.report)
        self.state.write_text(json.dumps(data));self.report.write_text('modified report')
        self.assertEqual(experience.collect(self.workspace,self.library),0)
        data['steps'][1]['attempts'][0]['quality_review'].pop('report_sha256')
        data['steps'][0]['attempts'][0].pop('role_scope')
        data['steps'][0]['attempts'][0]['context']['role']='unknown-version'
        self.state.write_text(json.dumps(data))
        self.assertEqual(experience.collect(self.workspace,self.library),2)
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()),[])

    def test_no_experience_is_inferred_from_successful_command_or_unvalidated_review(self):
        data=json.loads(self.state.read_text());data['steps'][1]['attempts'][0]['validated']=False
        self.state.write_text(json.dumps(data))
        self.assertEqual(experience.collect(self.workspace,self.library),0)
        self.assertEqual(experience.summary(self.library)['total'],0)

    def test_actual_method_record_keeps_script_identity_but_remains_a_declared_recipe(self):
        out=self.product.parent; (out/'work').mkdir()
        script=out/'work/compose.py';script.write_text('print("fixture")')
        (out/'work/method.json').write_text(json.dumps({'approach':'Composizione con asset e lettering separato',
            'steps':['Preparare gli asset','Comporre e riaprire'],'scripts':[str(script)],'limits':['Creazione immagini non registrata']}))
        identifier=experience.prefer(self.workspace,self.library,out.name,'Conserva questo approccio')
        record=next(r for r in experience.entries(self.library) if r['id']==identifier)
        method=record['observation']['producer_method']
        self.assertEqual(method['status'],'reported');self.assertEqual(method['scripts'][0]['sha256'],digest(script))
        self.assertIn('non rieseguito',method['notice'])

    def test_a_pre_update_success_is_recovered_after_roles_have_been_recompiled(self):
        data=json.loads(self.state.read_text());data['steps'][0]['attempts'][0].pop('role_scope')
        self.state.write_text(json.dumps(data))
        projects.sync_project_context(self.workspace,memory={'later':'Subsequent project stage'})
        identifier=experience.prefer(self.workspace,self.library,'rh-job-123456abcdef','Metodo preferito della prima lavorazione')
        record=next(r for r in experience.entries(self.library) if r['id']==identifier)
        self.assertTrue(record['observation']['scope_known'])
        self.assertIn('vectorcraft',record['observation']['tools'])
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()), [])
        proposal = self.propose([identifier]); lessons.accept(self.library, proposal)
        self.assertTrue(experience.select(self.library,[self.spec],projects.applications()))

    def test_acceptance_is_individual_revocable_and_bound_to_the_exact_proposal(self):
        experience.collect(self.workspace, self.library)
        ids = [r['id'] for r in experience.entries(self.library)]
        first = self.propose([ids[0]])
        second = self.propose([ids[1]])
        self.assertEqual(experience.select(self.library, [self.spec], projects.applications()), [])
        lessons.accept(self.library, first)
        self.assertEqual([r['id'] for r in experience.select(self.library,[self.spec],projects.applications())], [first])
        self.assertFalse(next(r for r in experience.summary(self.library)['lessons'] if r['id']==second)['accepted'])
        lessons.accept(self.library, first, False)
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()), [])
        with self.assertRaises(ValueError): lessons.accept(self.library, ids[0])
        with self.assertRaises(ValueError): lessons.accept(self.root/'user-b/library', first)
        self.assertEqual(len(experience.entries(self.library)), 2)

    def test_structural_guards_and_dismissal_keep_unhelpful_sources_out_of_skills(self):
        experience.collect(self.workspace,self.library)
        proposal = self.propose()
        lesson = lessons.entries(self.library)[0]['basis']['lesson']
        source = experience.entries(self.library)[0]['id']
        for text in ['/mnt/user-data/outputs/project.svg', 'project '+source, 'token sk-'+'a'*35]:
            bad = {**lesson, 'title': text}
            with self.subTest(text=text[:20]), self.assertRaises(ValueError): lessons.learn(self.library,[source],bad)
        with self.assertRaises(ValueError): lessons.learn(self.library,['f'*64],lesson)
        self.assertEqual(lessons.pending(self.library), [])
        record = self.library/'lessons'/(proposal+'.json')
        data=json.loads(record.read_text());data['basis']['lesson']['title']='Altered';record.write_text(json.dumps(data))
        self.assertEqual(lessons.entries(self.library), [])
        lessons.dismiss(self.library,[source],'Osservazione specifica senza lezione trasferibile')
        self.assertNotIn(source, [r['id'] for r in lessons.pending(self.library)])
        self.assertEqual(len(experience.entries(self.library)),2)
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()), [])

    def sandbox_note(self, impact=None, measurement=None):
        data=json.loads(self.state.read_text())
        data['steps'][1]['attempts'][0]['validated']=False
        # A partial delivery may still contain a useful CLI finding.
        data['steps'][0]['status']='paused'
        data['steps'][0]['attempts'][0].update(status='paused',validated=False)
        self.state.write_text(json.dumps(data))
        work=self.product.parent/'work';work.mkdir(exist_ok=True)
        note={'lesson':{'title':'Riaprire le dipendenze prima dell’esportazione',
            'applies_when':'Quando il documento contiene risorse esterne da distribuire',
            'procedure':['Risolvere i collegamenti prima di esportare'],
            'verification':['Riaprire il progetto da una cartella diversa'],
            'limits':'Non prova la qualità visiva del prodotto', 'tools':['vectorcraft']},
            'evidence':'Il file esportato è stato riaperto dopo aver risolto i collegamenti',
            'evidence_paths':[str(self.product)], 'impact':impact or {'level':'major','basis':'observed','reason':'Evita una consegna con risorse mancanti'}}
        if measurement:note['measurement']=measurement
        path=work/'tool-lessons.json';path.write_text(json.dumps({'lessons':[note]}))
        return path,note

    def test_sandbox_tool_use_is_retained_without_a_finished_product_but_requires_acceptance(self):
        path,note=self.sandbox_note()
        self.assertEqual(experience.collect(self.workspace,self.library,'thread-a'),1)
        with patch('righaven.sandbox_lessons.digest', wraps=digest) as hashing:
            self.assertEqual(experience.collect(self.workspace,self.library,'thread-a'),0)
            self.assertFalse(any(call.args[0] == self.product for call in hashing.call_args_list))
        record=experience.entries(self.library)[0]
        self.assertEqual(record['observation']['status'],'sandbox_observation')
        self.assertEqual(record['observation']['evidence_files'][0]['sha256'],digest(self.product))
        pending=lessons.pending(self.library)[0]
        self.assertEqual(pending['suggested_lesson']['tools'],['vectorcraft'])
        proposal=lessons.learn(self.library,[record['id']],note['lesson'],note['impact'])
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()),[])
        lessons.accept(self.library,proposal)
        selected=experience.select(self.library,[self.spec],projects.applications())[0]
        self.assertEqual(selected['source_statuses'],['sandbox_observation'])
        self.assertNotIn('evidence_files',selected)
        self.assertNotIn('impact',selected) # Project measurements are not procedural knowledge.

    def verified_note(self, category='tool_operation'):
        path, note = self.sandbox_note()
        note['lesson']['category'] = category
        operation = self.product.parent / 'work/operations' / ('d' * 24) / 'status.json'
        operation.parent.mkdir(parents=True, exist_ok=True)
        operation.write_text(json.dumps({'state': 'completed', 'returncode': 0, 'oom_kills': 0}))
        result = self.product.parent / 'work/reopen-result.json'
        result.write_text(json.dumps({'resources': [{'reopened': True}]}))
        note['validation'] = {'operation_path': str(operation), 'result_path': str(result),
                              'assertions': [{'pointer': '/resources/0/reopened', 'equals': True}]}
        path.write_text(json.dumps({'lessons': [note]}))
        return path, note, operation, result

    def test_technical_knowledge_activates_without_user_approval_and_can_be_revoked(self):
        self.verified_note()
        experience.collect(self.workspace, self.library, 'thread-a')
        proposal, = lessons.propose_findings(self.library, 'thread-a')
        item, = experience.summary(self.library)['lessons']
        self.assertEqual((item['category'], item['approval'], item['accepted']), ('tool_operation', 'automatic', True))
        self.assertEqual(len(experience.select(self.library, [self.spec], projects.applications())), 1)
        self.assertFalse((self.library / 'accepted-lessons.json').exists())
        lessons.accept(self.library, proposal, False)
        self.assertEqual(experience.select(self.library, [self.spec], projects.applications()), [])
        self.assertNotIn(proposal, lessons.automatic(self.library))

    def test_compiled_role_receives_verified_note_but_not_a_different_tool_version(self):
        self.verified_note()
        experience.collect(self.workspace,self.library,'thread-a')
        identifier,=lessons.propose_findings(self.library,'thread-a')
        projects.sync_project_context(self.workspace,experience_root=self.library)
        compiled=projects.read_project(self.workspace)['roles'][0]
        self.assertEqual(compiled['experience']['ids'],[identifier])
        self.assertIn('Riaprire le dipendenze',load_compiled(self.workspace,compiled))
        apps=[{**a,'version':a['version']+'-changed'} if a['id']=='vectorcraft' else a for a in projects.applications()]
        with patch('righaven.projects.applications',return_value=apps):
            projects.sync_project_context(self.workspace,experience_root=self.library)
        self.assertEqual(projects.read_project(self.workspace)['roles'][0]['experience']['count'],0)
        self.assertIn(identifier,lessons.automatic(self.library))

    def test_verified_operational_knowledge_is_retained_without_inventing_impact(self):
        self.verified_note()
        path=self.product.parent/'work/tool-lessons.json'
        value=json.loads(path.read_text());value['lessons'][0]['impact']={
            'level':'unknown','basis':'hypothesis','reason':'Operation tested; improvement size not measured'}
        path.write_text(json.dumps(value))
        experience.collect(self.workspace,self.library,'thread-a')
        proposal,=lessons.propose_findings(self.library,'thread-a')
        self.assertIn(proposal,lessons.automatic(self.library))
        item,=experience.summary(self.library)['lessons']
        self.assertEqual(item['basis']['impact']['level'],'unknown')
        self.assertEqual(lessons.propose_findings(self.library,'thread-a'),[])

    def test_production_method_never_auto_activates_even_with_a_technical_test(self):
        self.verified_note('production_method')
        experience.collect(self.workspace, self.library, 'thread-a')
        proposal, = lessons.propose_findings(self.library, 'thread-a')
        self.assertEqual(lessons.accepted(self.library), set())
        item, = experience.summary(self.library)['lessons']
        self.assertEqual(item['category'], 'production_method')
        lessons.accept(self.library, proposal)
        self.assertIn(proposal, lessons.accepted(self.library))
        lessons.accept(self.library, proposal, False)
        item, = experience.summary(self.library)['lessons']
        self.assertFalse(item['accepted'])
        self.assertFalse(item['excluded'])  # Remains available for re-acceptance.
        lessons.accept(self.library, proposal)
        self.assertIn(proposal, lessons.accepted(self.library))

    def test_failed_unscoped_and_missing_proofs_do_not_activate_technical_notes(self):
        for fault in ('failed', 'wrong_value', 'wrong_type', 'outside', 'missing'):
            with self.subTest(fault=fault):
                path, note, operation, result = self.verified_note()
                if fault == 'failed':
                    operation.write_text('{"state":"failed","returncode":1}')
                elif fault == 'wrong_value':
                    note['validation']['assertions'][0]['equals'] = False
                elif fault == 'wrong_type':
                    note['validation']['assertions'][0]['equals'] = 1
                elif fault == 'outside':
                    outside = self.root / 'outside.json'; outside.write_text('{"reopened":true}')
                    note['validation']['result_path'] = str(outside)
                else:
                    note.pop('validation')
                path.write_text(json.dumps({'lessons': [note]}))
                library = self.root / ('library-' + fault)
                experience.collect(self.workspace, library, 'thread-a')
                lessons.propose_findings(library, 'thread-a')
                self.assertEqual(lessons.accepted(library), set())
                self.assertEqual(experience.summary(library)['lessons'][0]['category'], 'tool_operation')

    def test_legacy_notes_are_classified_without_fabricating_validation(self):
        self.sandbox_note()
        experience.collect(self.workspace, self.library, 'thread-a')
        lessons.propose_findings(self.library, 'thread-a')
        item, = experience.summary(self.library)['lessons']
        self.assertEqual((item['category'], item['accepted']), ('tool_operation', False))

    def test_new_technical_test_can_upgrade_an_unverified_note_without_repeated_proposals(self):
        path, note = self.sandbox_note()
        note['lesson']['category'] = 'tool_operation'
        path.write_text(json.dumps({'lessons': [note]}))
        experience.collect(self.workspace, self.library, 'thread-a')
        old, = lessons.propose_findings(self.library, 'thread-a')
        self.assertNotIn(old, lessons.accepted(self.library))
        self.verified_note()
        experience.collect(self.workspace, self.library, 'thread-a')
        new, = lessons.propose_findings(self.library, 'thread-a')
        self.assertIn(new, lessons.automatic(self.library))
        self.assertEqual(lessons.propose_findings(self.library, 'thread-a'), [])

    def test_measured_impact_requires_real_distinct_supervisor_records(self):
        before=self.product.parent/'work/operations'/('a'*24)/'status.json'
        after=self.product.parent/'work/operations'/('b'*24)/'status.json'
        for path,seconds in [(before,20),(after,5)]:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({'state':'completed','returncode':0,'elapsed_seconds':seconds}))
        impact={'level':'major','basis':'measured','reason':'Esportazione più rapida sul campione di prova; qualità da verificare'}
        path,note=self.sandbox_note(impact,{'before':str(before),'after':str(after)})
        self.assertEqual(experience.collect(self.workspace,self.library),1)
        record=experience.entries(self.library)[0]
        self.assertEqual(record['observation']['measurement']['before']['seconds'],20)
        lessons.learn(self.library,[record['id']],note['lesson'],impact)
        path.write_text(json.dumps({'lessons':[{**note,'measurement':{'before':str(before),'after':str(before)}}]}))
        self.assertEqual(experience.collect(self.workspace,self.root/'bad-measurement'),0)

    def test_significance_is_ordered_and_unmeasured_gains_cannot_claim_measurement(self):
        experience.collect(self.workspace,self.library)
        source=experience.entries(self.library)[0]['id']
        lesson={'title':'Controllare le risorse collegate','applies_when':'Per documenti con dipendenze esterne',
                'procedure':['Verificare i collegamenti'],'verification':['Riaprire il pacchetto'],
                'limits':'Non verifica qualità estetica','tools':['vectorcraft']}
        minor=lessons.learn(self.library,[source],lesson,{'level':'minor','basis':'observed','reason':'Riduce un piccolo passaggio manuale'})
        major=lessons.learn(self.library,[source],{**lesson,'title':'Evitare sorgenti incompleti'},
                            {'level':'major','basis':'observed','reason':'Evita una consegna inutilizzabile'})
        self.assertEqual([r['id'] for r in experience.summary(self.library)['lessons']],[major,minor])
        with self.assertRaises(ValueError):lessons.learn(self.library,[source],lesson,{'level':'major','basis':'measured','reason':'Presunto miglioramento non misurato'})

    def test_invalid_or_unscoped_worker_notes_never_break_delivery_or_become_lessons(self):
        path,note=self.sandbox_note()
        outside=self.root/'other-project.txt';outside.write_text('Other project')
        path.write_text(json.dumps({'lessons':[{**note,'evidence_paths':[str(outside)]}]}))
        self.assertEqual(experience.collect(self.workspace,self.library),0)
        path.write_text('invalid')
        self.assertEqual(experience.collect(self.workspace,self.library),0)
        self.assertEqual(experience.summary(self.library)['lessons'],[])

    def test_auxiliary_cli_learning_uses_the_job_environment_not_the_current_catalog(self):
        from righaven.project_skills import scoped_file
        path,note=self.sandbox_note()
        data=json.loads(self.state.read_text())
        data['steps'][0]['attempts'][0]['tool_environment']=scoped_file(self.workspace,'tool-environments/fixture.json',json.dumps({'vectorcraft':'saved-vector','pdfcraft':'saved-pdf'}))
        self.state.write_text(json.dumps(data))
        note['lesson']['tools']=['pdfcraft']
        path.write_text(json.dumps({'lessons':[note]}))
        self.assertEqual(experience.collect(self.workspace,self.library),1)
        record=experience.entries(self.library)[0]
        self.assertEqual(record['observation']['tools'],{'pdfcraft':'saved-pdf'})
        proposal=lessons.learn(self.library,[record['id']],note['lesson'],note['impact'])
        lessons.accept(self.library,proposal)
        spec={**self.spec,'tools':['pdfcraft']}
        self.assertEqual(experience.select(self.library,[spec],projects.applications()),[]) # Version mismatch is not silently promoted.

    def test_documented_worker_lesson_becomes_inactive_proposal_without_an_extra_model_call(self):
        path,note=self.sandbox_note()
        experience.collect(self.workspace,self.library,'thread-a')
        self.assertEqual(lessons.propose_findings(self.library,'another-thread'),[])
        proposed=lessons.propose_findings(self.library,'thread-a')
        self.assertEqual(len(proposed),1)
        self.assertEqual(lessons.accepted(self.library),set())
        self.assertEqual(experience.select(self.library,[self.spec],projects.applications()),[])
        self.assertEqual(lessons.propose_findings(self.library,'thread-a'),[])
        note['evidence']='Il controllo è ripetuto su una seconda variante con dipendenze trasferite'
        path.write_text(json.dumps({'lessons':[note]}))
        self.assertEqual(experience.collect(self.workspace,self.library,'thread-a'),1)
        self.assertEqual(lessons.propose_findings(self.library,'thread-a'),[])
        lessons.accept(self.library,proposed[0])
        self.assertEqual(len(experience.select(self.library,[self.spec],projects.applications())),1)

    def test_raw_project_facts_and_hypothetical_benefits_are_not_automatically_generalized(self):
        experience.collect(self.workspace,self.library,'thread-a')
        self.assertEqual(lessons.propose_findings(self.library,'thread-a'),[])
        self.sandbox_note({'level':'major','basis':'hypothesis','reason':'Potrebbe forse accelerare la lavorazione'})
        experience.collect(self.workspace,self.library,'thread-a')
        self.assertEqual(lessons.propose_findings(self.library,'thread-a'),[])
        self.assertEqual(lessons.entries(self.library),[])
