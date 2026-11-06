"""Native regression in isolated Compose CI; no model accounts or production calls."""
import os
import uuid
from unittest.mock import patch


def main():
    if os.getenv('RIGHAVEN_CI_SOFTWARE_REUSE')!='1':raise RuntimeError('This check runs only in the isolated CI runtime')
    from righaven import environment_runtime as environments,docker_runtime as runtime,provider_bundle as providers
    baseline=environments.ensure(['d2'])
    # Adding a tool must reuse the application layer, not download D2 again.
    expanded=environments.ensure(['d2','qpdf'])
    assert expanded['base_environment_id']==baseline['id'],expanded
    assert expanded['reused_tools']==['d2'],expanded
    assert expanded['install_tools']==['qpdf'],expanded
    for engine in ('codex','gemini'):
        bundle=providers.prepare(engine)
        result=runtime.docker('run','--rm','--network=none','--cap-drop=ALL','--security-opt=no-new-privileges',
            '--memory=512m','--cpus=1',*providers.arguments(bundle),expanded['image_id'],bundle[1]['binary'],'--version')
        assert bundle[1]['version'].lstrip('v') in result,(engine,result)
        assert environments.available(['d2','qpdf'])['image_id']==expanded['image_id']
    # A catalog/code-only image revision must not invalidate compatible native software.
    name='rh-ci-base-'+uuid.uuid4().hex[:8];tag='righaven/ci-metadata:'+uuid.uuid4().hex[:8]
    runtime.docker('create','--name',name,runtime.IMAGE,'true')
    try:
        changed=runtime.docker('commit','--change','LABEL org.righaven.ci.metadata=changed',name,tag)
        with patch.object(runtime,'IMAGE',tag):
            reused=environments.ensure(['d2','qpdf'])
            assert reused['image_id']==expanded['image_id'],reused
    finally:
        runtime.docker('rm','-f',name)
        runtime.docker('image','rm',tag)
    print('Software reuse OK: native additive install, isolated Codex/Antigravity overlays, metadata-only release reuses the same prepared image.')


if __name__=='__main__':main()
