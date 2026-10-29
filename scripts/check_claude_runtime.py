#!/usr/bin/env python3
"""Prepare the optional official Claude executable; never log in or generate."""
import json,sys,tempfile,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from righaven import state,tool_versions,environment_runtime as factory,docker_runtime as runtime


def main():
    with tempfile.TemporaryDirectory(prefix='righaven-claude-check-') as folder:
        root=Path(folder);(root/'installation-id').write_text(uuid.uuid4().hex)
        ready=None
        with patch.object(state,'STATE',root),patch.object(runtime,'host_path',side_effect=str),patch.object(factory,'pinned',return_value=set()):
            try:
                pins=tool_versions.resolved(tool_versions.selections(engine='claude'),refresh=False)
                ready=factory.ensure([],versions=pins)
                assert ready['tools']==[] and ready['status']=='ready'
                result=factory.docker('run','--rm','--network=none',ready['image_id'],'claude','--help')
                for flag in ('--print','--json-schema','--output-format','--no-session-persistence','--strict-mcp-config','--setting-sources','--allowedTools'):
                    assert flag in result,flag
                version=factory.docker('run','--rm','--network=none',ready['image_id'],'claude','--version')
                assert tool_versions.builtins()['provider-claude']['version'] in version
                assert factory.ensure([],versions=pins)['image_id']==ready['image_id']
                print('Optional Claude executable verified, reused unchanged; no account, project or provider request')
            except Exception:
                for log in (root/'environments').glob('*.log'):print(log.read_text()[-16000:],file=sys.stderr)
                raise
            finally:
                if ready:factory.evict(ready['id'])


if __name__=='__main__':main()
