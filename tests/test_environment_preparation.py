"""Preparation is a durable user operation, not the incidental image status."""
import importlib,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from righaven import environment_preparation as prep,state,tool_versions as versions


class PreparationTests(unittest.TestCase):
    def setUp(self):
        root=tempfile.TemporaryDirectory();self.addCleanup(root.cleanup)
        self.directory=Path(root.name)
        item=patch.object(state,'STATE',self.directory);item.start();self.addCleanup(item.stop)

    def test_version_check_is_visible_before_final_image_exists_and_survives_reload(self):
        prep.begin('owner','docs',{'wordcraft':'latest'})
        prep.update('owner','docs',phase='checking_versions',tool='wordcraft',version='v0.11.0',index=1,total=1)
        module=importlib.reload(prep)
        value=module.snapshot('owner','docs',{'status':'version_pending'},active=True)
        self.assertEqual(value['phase'],'checking_versions');self.assertEqual(value['tool'],'wordcraft')
        self.assertTrue(value['active']);self.assertEqual(module.read('other','docs'),{})
        stopped=module.snapshot('owner','docs',{'status':'version_pending'},active=False)
        self.assertEqual(stopped['phase'],'interrupted');self.assertFalse(stopped['active'])

    def test_native_failure_names_the_actual_tool_and_preserves_passed_checks(self):
        text='OK deckcraft\nOK epubcheck\nOK pandoc\nOK pdfcraft\nOK typst\nOK wordcraft\nFAIL calibre Comando fallito: conversion\nRendering 2 HTML files\nSegmentation fault (core dumped)\n'
        failure=prep.diagnosis(text,'Preparazione o verifica nativa non riuscita')
        self.assertEqual(failure['tool'],'calibre');self.assertEqual(failure['kind'],'native_crash')
        self.assertEqual(len(failure['passed_tools']),6);self.assertIn('PDF',failure['message'])
        self.assertNotIn('Memoria esaurita',failure['message'])
        prep.begin('owner','docs',{})
        prep.update('owner','docs',phase='failed',error=failure['message'],failure=failure)
        self.assertIn('Segmentation fault',prep.text('owner','docs'))
        self.assertEqual(prep.snapshot('owner','docs',{'status':'failed'},False)['phase'],'failed')

    def test_publication_failure_does_not_blame_last_successful_tool(self):
        from righaven import environment_runtime as factory
        import subprocess
        key='a'*64
        factory.save(key,status='publishing',tools=['pymeshlab'])
        (factory.folder()/(key+'.log')).write_text('Installazione pymeshlab 2025.7.post1\nOK pymeshlab \n{"phase":"verified"}\n{"phase":"publishing"}\n')
        factory.interrupted(key,subprocess.TimeoutExpired(['docker','commit','own-container'],900))
        failure=factory.read(key)['failure']
        self.assertEqual(failure['kind'],'publication');self.assertEqual(failure['tool'],'')
        self.assertEqual(failure['passed_tools'],['pymeshlab']);self.assertEqual(failure['failed_tools'],[])
        self.assertIn('900',failure['details']);self.assertNotIn('pymeshlab:',failure['message'])
        factory.interrupted(key,subprocess.TimeoutExpired(['docker','commit','own-container'],900))
        self.assertEqual(factory.read(key)['failure'],failure)

    def test_retry_does_not_inherit_publication_failure_from_an_old_log(self):
        from righaven import environment_runtime as factory
        key='a'*64
        log=factory.folder()/(key+'.log')
        log.write_text('OK pymeshlab \n{"phase":"publishing"}\n')
        __import__('os').utime(log,(10,10))
        factory.save(key,status='queued',error='',failure={},attempt_started_at=20)
        factory.interrupted(key,RuntimeError('HTTP Error 503: Service Unavailable'))
        self.assertEqual(factory.read(key)['failure']['kind'],'network')
        self.assertEqual(factory.read(key)['failure']['passed_tools'],[])

    def test_dependency_publication_failure_retains_its_cause_in_the_parent(self):
        from righaven import environment_runtime as factory
        key='a'*64
        factory.save(key,status='installing',tools=['filmcraft','ffmpeg'])
        factory.interrupted(key,factory.PreparationPublicationError('Docker commit timed out'))
        self.assertEqual(factory.read(key)['failure']['kind'],'publication')
        self.assertEqual(factory.read(key)['failure']['tool'],'')

    def test_restart_during_publication_preserves_the_phase_and_passed_checks(self):
        from righaven import environment_runtime as factory
        key='a'*64
        factory.save(key,status='publishing',tools=['pymeshlab'],container='old')
        (factory.folder()/(key+'.log')).write_text('OK pymeshlab \n{"phase":"verified"}\n')
        factory.reconcile()
        value=factory.read(key)
        self.assertEqual(value['status'],'failed');self.assertEqual(value['container'],'')
        self.assertEqual(value['failure']['kind'],'publication')
        self.assertEqual(value['failure']['passed_tools'],['pymeshlab'])
        self.assertIn('riavvio',value['failure']['details'])

    def test_connection_failure_is_actionable_without_discarding_ready_versions(self):
        failure=prep.diagnosis('','HTTP Error 503: Service Unavailable')
        self.assertEqual(failure['kind'],'network');self.assertIn('Riprova',failure['action'])
        self.assertNotIn('cancella',failure['action'])

    def test_finished_image_controls_readiness_and_cancellation_is_not_an_active_job(self):
        prep.begin('owner','docs',{})
        prep.update('owner','docs',phase='preparing',environment_id='a'*64)
        self.assertEqual(prep.snapshot('owner','docs',{'id':'a'*64,'status':'checking'},True)['phase'],'checking')
        prep.update('owner','docs',phase='cancelled',error='Annullamento richiesto')
        self.assertFalse(prep.snapshot('owner','docs',{'status':'version_pending'},True)['active'])

    def test_environments_sharing_a_release_share_one_verification_job(self):
        with patch.object(versions.threading,'Thread') as thread:
            first=versions.start('d2','latest');second=versions.start('d2','latest')
            self.assertEqual(first['id'],second['id']);self.assertTrue(second['existing'])
            self.assertEqual(thread.call_count,1)
            other=versions.start('d2','v0.8.0');self.assertNotEqual(first['id'],other['id'])
            self.assertEqual(thread.call_count,2)

    def test_latest_reports_the_real_verification_job_while_waiting(self):
        import copy
        bundle={'app':copy.deepcopy(versions.builtins()['d2']),'files':{}}
        revision=versions.identifier(bundle)
        versions.directory().mkdir(exist_ok=True)
        versions.state.atomic_json(versions.directory()/(revision+'.json'),{'id':revision,'state':'ready','bundle':bundle,'updated_at':'now'})
        job=versions.directory()/'jobs'/('b'*32);job.mkdir(parents=True)
        versions.state.atomic_json(job/'status.json',{'id':job.name,'tool':'d2','version':'latest','resolved_version':bundle['app']['version'],'state':'testing','environment_id':'c'*64})
        def library():
            status=json.loads((job/'status.json').read_text())
            return {'versions':[{'id':revision,'tool':'d2','version':bundle['app']['version'],'state':'ready'}] if status['state']=='ready' else [],'jobs':[status]}
        def complete(_):versions.state.atomic_json(job/'status.json',{'id':job.name,'tool':'d2','version':'latest','state':'ready','revision':revision})
        events=[]
        with patch.object(versions,'latest_version',return_value=bundle['app']['version']),patch.object(versions,'library',side_effect=library),patch.object(versions.time,'sleep',side_effect=complete):
            result=versions.resolved({'d2':'latest'},wait=True,on_progress=lambda **fields:events.append(fields))
        self.assertEqual(result,{'d2':revision})
        self.assertEqual(events[0]['environment_id'],'');self.assertEqual(events[0]['version_job_id'],'')
        self.assertEqual(events[0]['version_operation'],'')
        check=next(e for e in events if e['phase']=='checking_versions' and e.get('version_state')=='testing')
        self.assertEqual(check['environment_id'],'c'*64);self.assertEqual(check['version_job_id'],job.name)
