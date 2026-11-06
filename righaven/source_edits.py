"""Web text edits create new source copies; original deliveries never change."""
import json
from pathlib import Path
import uuid
from .project_store import locked
from .progress import utcnow
from .state import atomic_json
from .strategy import proof_path
from .source_packages import digest

EXTENSIONS = {'.md','.markdown','.txt','.csv','.tsv','.json','.yaml','.yml','.html','.css','.js','.ts','.py','.sql','.xml','.svg'}
MAX_BYTES = 1024 * 1024


def edits(folder):
    path=Path(folder)/'source-edits.json'
    if not path.exists(): return []
    if path.is_symlink() or path.stat().st_size>100000: raise ValueError('Invalid source edit history')
    return json.loads(path.read_text())


def save(workspace, source, expected_sha256, content):
    if not isinstance(content,str) or len(content.encode('utf-8'))>MAX_BYTES:
        raise ValueError('Web source edits are limited to 1 MiB of UTF-8 text')
    with locked(workspace) as folder:
        original=proof_path(workspace,source)
        outputs=Path(workspace).resolve()/'outputs'
        if not original.is_relative_to(outputs) or original.suffix.lower() not in EXTENSIONS:
            raise ValueError('Only supported text sources in conversation outputs can be edited')
        if original.stat().st_size>MAX_BYTES:
            raise ValueError('Web source edits are limited to 1 MiB of UTF-8 text')
        try: original.read_text(encoding='utf-8')
        except UnicodeDecodeError: raise ValueError('The source must contain UTF-8 text') from None
        if digest(original)!=expected_sha256:
            raise ValueError('The source changed; reload before saving your copy')
        target=outputs/'source-revisions'/uuid.uuid4().hex/original.name
        if not target.parent.resolve().is_relative_to(outputs.resolve()):
            raise ValueError('Invalid source revision path')
        target.parent.mkdir(parents=True,mode=0o700)
        with target.open('x',encoding='utf-8') as stream:stream.write(content)
        target.chmod(0o600)
        result={'path':'/mnt/user-data/'+target.relative_to(Path(workspace).resolve()).as_posix(),
                'source':source,'source_sha256':expected_sha256,'sha256':digest(target),'at':utcnow(),
                'status':'source_copy','exports_regenerated':False}
        atomic_json(folder/'source-edits.json',[*edits(folder),result][-50:])
    from .audit_log import append
    append(workspace,'User','Source revision saved','completed','Original file retained; exports unchanged',context={'source':source,'path':result['path']})
    return result
