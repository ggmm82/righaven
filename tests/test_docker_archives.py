import gzip,hashlib,io,json,tarfile,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from righaven import docker_archives as archives


def add(archive,name,data):
    info=tarfile.TarInfo(name);info.size=len(data);archive.addfile(info,io.BytesIO(data))


class DockerArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        filesystem=io.BytesIO()
        with tarfile.open(fileobj=filesystem,mode='w') as tf:add(tf,'usr/bin/example',b'locked native program')
        self.layer=filesystem.getvalue();self.diff='sha256:'+hashlib.sha256(self.layer).hexdigest()
        self.config=json.dumps({'os':'linux','architecture':'amd64','rootfs':{'type':'layers','diff_ids':[self.diff]}}).encode()
        self.config_digest='sha256:'+hashlib.sha256(self.config).hexdigest()

    def oci(self,path,*,missing_config=False,missing_layer=False,corrupt_layer=False):
        compressed=gzip.compress(self.layer);digest=hashlib.sha256(compressed).hexdigest()
        name='blobs/sha256/'+digest;config_name='blobs/sha256/'+self.config_digest.removeprefix('sha256:')
        manifest=json.dumps({'schemaVersion':2,'config':{'digest':self.config_digest},'layers':[{'digest':'sha256:'+digest}]}).encode()
        with tarfile.open(path,'w') as tf:
            add(tf,'blobs/sha256/'+hashlib.sha256(manifest).hexdigest(),manifest)
            add(tf,'index.json',b'{"schemaVersion":2,"manifests":[]}')
            add(tf,'manifest.json',json.dumps([{'Config':config_name,'RepoTags':['local-source:private'],'Layers':[name]}]).encode())
            if not missing_config:add(tf,config_name,self.config)
            if not missing_layer:add(tf,name,gzip.compress(b'corrupt') if corrupt_layer else compressed)
        return 'sha256:'+hashlib.sha256(manifest).hexdigest()

    def test_oci_manifest_identity_is_distinct_from_portable_config_identity_and_layers_are_included(self):
        source=self.root/'oci.tar';source_id=self.oci(source);target=self.root/'portable.tar'
        self.assertNotEqual(source_id,self.config_digest)
        info=archives.normalize(source,target,expected_layers=[self.diff])
        self.assertEqual(info['config_digest'],self.config_digest)
        verified=archives.validate(target,expected_config=self.config_digest)
        self.assertEqual(verified['diff_ids'],[self.diff])
        with tarfile.open(target) as tf:
            rows=json.load(tf.extractfile('manifest.json'))
            self.assertIsNone(rows[0]['RepoTags']);self.assertEqual(tf.extractfile(rows[0]['Layers'][0]).read(),self.layer)
            self.assertNotIn('index.json',tf.getnames())

    def test_descriptor_only_export_like_production_is_rejected_even_when_docker_save_succeeds(self):
        for missing in ('config','layer'):
            source=self.root/(missing+'.tar');target=self.root/'portable.tar'
            self.oci(source,missing_config=missing=='config',missing_layer=missing=='layer')
            with self.assertRaisesRegex(ValueError,'incompleta'):archives.normalize(source,target)
            self.assertFalse(target.exists())

    def test_corrupt_native_layer_cannot_be_marked_complete(self):
        source=self.root/'corrupt.tar';self.oci(source,corrupt_layer=True)
        with self.assertRaisesRegex(ValueError,'Checksum'):archives.normalize(source,self.root/'out.tar')

    def test_export_uses_tag_and_explicit_platform_instead_of_a_manifest_digest(self):
        source=self.root/'complete.tar';self.oci(source);calls=[]
        details={'Id':'sha256:oci-manifest','Os':'linux','Architecture':'amd64','RootFS':{'Layers':[self.diff]}}
        def run(argv,**kwargs):
            calls.append(argv)
            if 'save' in argv:__import__('shutil').copyfile(source,argv[argv.index('--output')+1])
            return __import__('types').SimpleNamespace(returncode=0,stderr='')
        with patch.object(archives.subprocess,'run',side_effect=run):
            info=archives.save_image('skill-environment:prepared',details,self.root/'image.tar')
        save=next(argv for argv in calls if 'save' in argv)
        self.assertIn('--platform',save);self.assertIn('linux/amd64',save)
        self.assertTrue(save[-1].startswith('skill-export:'))
        self.assertEqual(info['config_digest'],self.config_digest)
        self.assertFalse((self.root/'image.tar.raw').exists())


    def test_platform_selection_failure_retries_once_and_still_verifies_all_layers(self):
        source=self.root/'complete.tar';self.oci(source);calls=[];phases=[]
        details={'Id':'sha256:index','Os':'linux','Architecture':'amd64','RootFS':{'Layers':[self.diff]}}
        def run(argv,**kwargs):
            calls.append(argv)
            if 'save' in argv:
                if '--platform' in argv:return __import__('types').SimpleNamespace(returncode=1,stderr='requested platform not found in image store')
                __import__('shutil').copyfile(source,argv[argv.index('--output')+1])
            return __import__('types').SimpleNamespace(returncode=0,stderr='')
        with patch.object(archives.subprocess,'run',side_effect=run):
            result=archives.save_image('prepared:tag',details,self.root/'image.tar',on_progress=lambda phase,message:phases.append(phase))
        self.assertEqual(len([v for v in calls if 'save' in v]),2)
        self.assertEqual(result['diff_ids'],[self.diff]);self.assertIn('verifying_image',phases)
        with patch.object(archives.subprocess,'run',return_value=__import__('types').SimpleNamespace(returncode=1,stderr='daemon failed')):
            with self.assertRaises(archives.ImageExportError) as error:archives.save_image('prepared:tag',details,self.root/'failed.tar')
        self.assertIn('daemon failed',error.exception.detail)


if __name__=='__main__':unittest.main()
