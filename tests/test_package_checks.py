"""The coordinator's package verifier accepts only the managed runtime and actual host-owned evidence."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from righaven import package_checks,journeys
from righaven.progress import create_job,update
from righaven.source_packages import digest


class PackageChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.workspace=Path(self.temp.name);self.package=self.workspace/'outputs/package';self.package.mkdir(parents=True)
        template,sources=package_checks.templates()
        files={'package-spec.json':json.dumps({'name':'sample','target':'postgres','source_dialect':'postgres'}),
               'Dockerfile':template.dockerfile('postgres','postgres'),'ops/entrypoint.sh':template.ENTRYPOINT_SH,
               'ops/orchestrate.py':(sources/'pipeline_runtime.py').read_text(),
               'ingestion/pipeline.py':template.PIPELINE.replace('{name}','sample'),
               'ingestion/requirements.lock':(sources.parent/'config/toolkit/pipeline/ingest.lock').read_text(),
               'transform/requirements.lock':(sources.parent/'config/toolkit/pipeline/transform.lock').read_text()}
        for name,text in files.items():
            path=self.package/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)

    def test_unknown_docker_instructions_cannot_run_inside_the_application(self):
        self.assertTrue(package_checks.validate(self.package))
        docker=self.package/'Dockerfile';docker.write_text(docker.read_text()+'\nRUN echo unexpected\n')
        with self.assertRaisesRegex(ValueError,'Regenerate'):package_checks.validate(self.package)

    def test_no_private_files_or_symlinks_enter_the_build_context(self):
        private=self.package/'.env';private.write_text('DO_NOT_EXPORT=example')
        with self.assertRaisesRegex(ValueError,'credential'):package_checks.validate(self.package)
        private.unlink();(self.package/'external').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError,'symlink'):package_checks.validate(self.package)

    def test_each_replacement_reacquires_capacity_and_cancellation_cleans_the_builder(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from righaven import docker_runtime,state
        for cancel_build in (False,True):
            leases={};kinds=[];stopped=[False];commands=[]
            class Budget:
                def acquire(self,owner,kind,**kwargs):
                    leases[owner]=kind;kinds.append(kind)
                    return {'cpus':1,'memory_mib':1024,'tmp_mib':128,'threads':1}
                def release(self,owner):leases.pop(owner,None)
                def observe_progress(self,*args):pass
                def quarantine(self,reason):raise AssertionError(reason)
            def process(argv,**kwargs):
                commands.append(argv)
                if argv[1]=='run':self.assertIn(argv[argv.index('--name')+1],leases)
                if cancel_build and argv[1:3]==['buildx','build']:stopped[0]=True
                return SimpleNamespace(poll=lambda:0,returncode=0)
            def docker(*args,**kwargs):
                return json.dumps({'status':'passed'}) if args[0]=='exec' else ''
            with patch.object(state,'STATE',self.workspace/'state'),patch.object(package_checks,'BUDGET',Budget()),patch.object(package_checks,'requested',side_effect=lambda:stopped[0]),patch.object(docker_runtime,'internal_daemon',return_value=True),patch.object(docker_runtime,'base_arguments',side_effect=lambda name,limits:['run','--name',name,'--network=bridge']),patch.object(docker_runtime,'remove',side_effect=lambda name:leases.pop(name,None)),patch.object(docker_runtime,'docker',side_effect=docker),patch.object(package_checks.subprocess,'Popen',side_effect=process),patch.object(package_checks.subprocess,'run',return_value=SimpleNamespace(returncode=0)):
                result=package_checks.check(self.workspace,str(self.package))
            self.assertEqual(result['status'],'failed' if cancel_build else 'passed')
            self.assertEqual(kinds,['build'] if cancel_build else ['build','worker','worker'])
            self.assertEqual(leases,{})

    def test_claimed_report_is_not_execution_evidence_and_changed_sources_invalidate_it(self):
        path=self.workspace/'outputs/workspace/rh-job-123456abcdef/package-check.json';path.parent.mkdir(parents=True)
        report={'status':'passed','package':str(self.package),'files':package_checks.validate(self.package)}
        path.write_text(json.dumps(report));evidence=[{'path':str(path),'sha256':digest(path)}]
        self.assertFalse(journeys.verified_package(self.workspace,evidence))
        progress=create_job(self.workspace,'rh-job-123456abcdef','workspace','verification','exported-package')
        update(progress,'completed','Native verifier fixture completed')
        self.assertTrue(journeys.verified_package(self.workspace,evidence))
        (self.package/'ingestion/pipeline.py').write_text('changed after testing')
        self.assertFalse(journeys.verified_package(self.workspace,evidence))


if __name__=='__main__':unittest.main()
