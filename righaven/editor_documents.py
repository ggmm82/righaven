"""Owner workspace drafts, project bundles and immutable explicit publications."""
from contextlib import contextmanager
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import stat
import tempfile
import uuid
import zipfile
from .project_store import locked
from .progress import utcnow
from .state import atomic_json
from .strategy import proof_path
from .source_packages import digest
from .editor_catalog import editor,candidates

MAX_FILE=64*1024*1024
MAX_TOTAL=512*1024*1024
MAX_FILES=2000


def relative(value):
    if not isinstance(value,str) or not value or len(value)>1000 or '\\' in value or ':' in value or any(ord(c)<32 for c in value):raise ValueError('Invalid document path')
    path=PurePosixPath(value)
    if path.is_absolute() or any(p in ('','.','..') or p.startswith('.') for p in value.split('/')):raise ValueError('Use a relative document path without hidden components')
    return str(path)


def confined(root,path):
    if not path.is_relative_to(root) or any(p.is_symlink() for p in [path,*path.parents] if p.is_relative_to(root)):raise ValueError('Symbolic links or paths outside the conversation are not editable')
    return path


def source(workspace,value,large=False):
    root=Path(workspace).resolve();raw=Path(value)
    if not raw.is_relative_to(root) and raw.is_relative_to('/mnt/user-data'):raw=root/raw.relative_to('/mnt/user-data')
    confined(root,raw);path=proof_path(root,str(raw));parts=path.relative_to(root).parts
    if parts[0] not in ('outputs','uploads','workspace') or any(p.startswith('.') for p in parts):raise ValueError('Choose an attachment or project output')
    if not large and path.stat().st_size>(MAX_TOTAL if path.suffix.lower()=='.zip' else MAX_FILE):raise ValueError('Document exceeds the editor size limit')
    return path


def directory(folder,identifier):
    if not isinstance(identifier,str) or len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('Invalid editing session')
    return confined(folder,folder/'editors'/identifier)


def record(folder,identifier,allowed):
    root=directory(folder,identifier);path=root/'session.json'
    if not path.is_file() or path.is_symlink() or path.stat().st_size>1000000:raise ValueError('Editing session not found')
    value=json.loads(path.read_text());editor(value['editor'],allowed)
    return root,value


def file_root(root):
    """Legacy drafts remain private; direct sessions use the public chat subtree."""
    record_path=root/'session.json'
    value=json.loads(record_path.read_text()) if record_path.is_file() else {}
    if value.get('mode')!='project':return root/'files'
    workspace=root.parents[2]
    name=value.get('project_root')
    if name not in ('uploads','outputs','workspace'):raise ValueError('Invalid project folder')
    return confined(workspace,workspace/name)


def file_location(root,name):
    name=relative(name)
    value=json.loads((root/'session.json').read_text())
    if value.get('mode')=='project' and name.startswith('@chat/'):
        parts=name.split('/')
        if len(parts)<3 or parts[1] not in ('uploads','outputs','workspace'):raise ValueError('Invalid document path')
        workspace=root.parents[2]
        return confined(workspace,workspace/parts[1]),'/'.join(parts[2:])
    return file_root(root),name


def virtual_path(value,name=None):
    name=relative(name or value['entry'])
    if name.startswith('@chat/'):
        parts=name.split('/')
        if len(parts)<3 or parts[1] not in ('uploads','outputs','workspace'):raise ValueError('Invalid document path')
        return '/mnt/user-data/'+name[len('@chat/'):]
    return '/mnt/user-data/'+value['project_root']+'/'+name


def asset_slots(value):
    from .source_packages import references
    yield from references(value)
    def sequences(node):
        if isinstance(node,dict):
            if node.get('type')=='Footage' and isinstance(node.get('sequence'),list):
                for index,path in enumerate(node['sequence']):
                    if isinstance(path,str) and path:yield node['sequence'],index,path
            for child in node.values():yield from sequences(child)
        elif isinstance(node,list):
            for child in node:yield from sequences(child)
    yield from sequences(value)


def files(root):
    rows=[];total=0;base=file_root(root);direct=base!=root/'files'
    for directory,folders,names in os.walk(base,followlinks=False):
        folders[:]=sorted(folder for folder in folders if not folder.startswith('.') and folder not in ('.ipynb_checkpoints','__pycache__','.git','.venv','venv','node_modules','.cache','.pytest_cache'))
        for folder in list(folders):
            if (Path(directory)/folder).is_symlink():
                if not direct:raise ValueError('Symbolic link in document bundle')
                folders.remove(folder)
        for name in sorted(names):
            if name.startswith('.'):continue
            path=Path(directory)/name
            if path.is_symlink():
                if direct:continue
                raise ValueError('Symbolic link in document bundle')
            try:info=path.stat()
            except (FileNotFoundError,PermissionError):
                if direct:continue
                raise
            if not stat.S_ISREG(info.st_mode):
                if direct:continue
                raise ValueError('Non-regular file in document bundle')
            size=info.st_size;total+=size
            if not direct and (size>MAX_FILE or total>MAX_TOTAL or len(rows)>=MAX_FILES):raise ValueError('Editing bundle exceeds size limits')
            if direct and len(rows)>=MAX_FILES:return sorted(rows,key=lambda row:row['name'])
            rows.append({'name':path.relative_to(base).as_posix(),'bytes':size,'sha256':'' if direct else digest(path),**({'modified_ns':info.st_mtime_ns} if direct else {})})
    return sorted(rows,key=lambda row:row['name'])


def native_extensions(value):
    result=editor(value['editor'],[value['editor']])['native_extensions']
    return [*result,Path(value['entry']).suffix.lower()] if value.get('manual_text') else result


def plain_text(data):
    try:
        if b'\0' in data:raise UnicodeError()
        data.decode('utf-8')
    except UnicodeError:raise ValueError('This text editor requires UTF-8 text; choose an application compatible with the file') from None


def manual_text(path,identifier,manual):
    if manual and identifier in ('text','jupyter') and path.suffix.lower() not in editor(identifier,[identifier])['native_extensions']:
        import codecs
        decoder=codecs.getincrementaldecoder('utf-8')()
        try:
            with path.open('rb') as stream:
                while chunk:=stream.read(65536):
                    if b'\0' in chunk:raise UnicodeError()
                    decoder.decode(chunk)
                decoder.decode(b'',final=True)
        except UnicodeError:raise ValueError('This text editor requires UTF-8 text; choose an application compatible with the file') from None
        return True
    return False


def editing_document(path):
    """A draft is editable before it passes final-delivery acceptance checks."""
    with path.open('rb') as stream:content=stream.read(MAX_FILE+1)
    if len(content)>MAX_FILE:raise ValueError('Project exceeds editing limits')
    value=json.loads(content)
    if not isinstance(value,dict):raise ValueError('Invalid native document')
    return value


def view(root,value):
    rows=files(root);dependencies=[];missing=[]
    if value.get('mode')=='project' and not any(row['name']==value['entry'] for row in rows):
        base,name=file_location(root,value['entry']);selected=confined(base,base/name)
        if selected.is_file():rows.append({'name':value['entry'],'bytes':selected.stat().st_size,'sha256':''})
    if value.get('mode')=='project' and Path(value['entry']).suffix.lower() in ('.ecproj','.fcproj','.scraft'):
        base,name=file_location(root,value['entry']);selected=base/name;workspace=root.parents[2]
        try:
            # An editable draft may have footage before it has a composition or
            # timeline. Delivery acceptance checks must not hide those assets.
            selected=confined(base,selected)
            for _,_,ref in asset_slots(editing_document(selected)):
                try:
                    raw=Path(ref)
                    if raw.is_relative_to('/mnt/user-data'):raw=workspace/raw.relative_to('/mnt/user-data')
                    target=(raw if raw.is_absolute() else selected.parent/raw).resolve()
                    confined(workspace,target)
                    parts=target.relative_to(workspace).parts
                    if not parts or parts[0] not in ('uploads','outputs','workspace'):raise ValueError('Invalid document path')
                    if target.is_file():
                        name=target.relative_to(file_root(root)).as_posix() if target.is_relative_to(file_root(root)) else '@chat/'+target.relative_to(workspace).as_posix()
                        if name not in dependencies:dependencies.append(name)
                        if not any(row['name']==name for row in rows):rows.append({'name':name,'bytes':target.stat().st_size,'sha256':''})
                    else:missing.append(ref)
                except (ValueError,OSError):missing.append('Unresolved project reference: '+ref[:200])
        except (ValueError,OSError):missing.append('Project references need inspection')
    return {**value,**({'virtual_path':virtual_path(value)} if value.get('mode')=='project' else {}),'native_extensions':native_extensions(value),'files':rows,'dependencies':dependencies,'missing_dependencies':missing,'files_truncated':value.get('mode')=='project' and len(rows)>=MAX_FILES}


@contextmanager
def checked_zip(path):
    try:
        with zipfile.ZipFile(path) as archive:yield archive
    except (zipfile.BadZipFile,zipfile.LargeZipFile,RuntimeError):
        raise ValueError('The source is not a valid native document archive') from None


def validate(path,boundary):
    from .source_packages import NATIVE,document,references,resolved_reference
    suffix=path.suffix.lower()
    if suffix in NATIVE:
        value=document(path)
        for _,_,ref in references(value):resolved_reference(path,ref,boundary,portable=True)
    elif suffix in ('.docx','.xlsx','.pptx','.odt','.ods','.odp','.fcstd'):
        if not zipfile.is_zipfile(path):raise ValueError('The source is not a valid native document archive')
        with checked_zip(path) as archive:
            entries=archive.infolist()
            if len(entries)>12000 or sum(item.file_size for item in entries)>MAX_TOTAL or archive.testzip() is not None:raise ValueError('The source is not a valid native document archive')
            required={'.docx':'word/document.xml','.xlsx':'xl/workbook.xml','.pptx':'ppt/presentation.xml','.fcstd':'Document.xml'}
            if suffix in required and required[suffix] not in archive.namelist():raise ValueError('The source is not a valid native document archive')
    elif suffix=='.ipynb':
        value=json.loads(path.read_text())
        if value.get('nbformat')!=4 or not isinstance(value.get('cells'),list):raise ValueError('Invalid notebook')
    elif suffix=='.excalidraw':
        value=json.loads(path.read_text())
        if value.get('type')!='excalidraw' or not isinstance(value.get('elements'),list):raise ValueError('Invalid drawing')


def copy_dependencies(workspace,original,target):
    from .source_packages import NATIVE,document,references
    if original.suffix.lower() not in NATIVE:return
    value=document(original)
    for owner,key,ref in references(value):
        if '://' in ref or '\\' in ref:raise ValueError('Project contains a non-local dependency')
        raw=Path(ref);dependency=source(workspace,str(raw if raw.is_absolute() else original.parent/raw))
        name='assets/'+digest(dependency)[:16]+'-'+dependency.name;relative(name)
        destination=target.parent/name;destination.parent.mkdir(exist_ok=True)
        if not destination.exists():shutil.copyfile(dependency,destination)
        owner[key]=name
    target.write_text(json.dumps(value,ensure_ascii=False))


def discovery(workspace,path,allowed):
    original=source(workspace,path,large=True)
    if original.suffix.lower()!='.zip':return candidates(original.name,allowed)
    rows=[]
    with checked_zip(original) as archive:
        entries=archive.infolist()
        if len(entries)>MAX_FILES or sum(v.file_size for v in entries)>MAX_TOTAL:raise ValueError('Source archive exceeds editor limits')
        for item in entries:
            if item.is_dir():continue
            name=relative(item.filename)
            rows.extend({**row,'entry':name} for row in candidates(name,allowed))
    return sorted(rows,key=lambda row:(row['relationship']!='source',row['id']=='text',row['entry']))[:200]


def start(workspace,path,identifier,allowed,entry='',manual=False,direct=False):
    original=source(workspace,path,large=direct)
    if direct:
        return start_archive_project(workspace,path,identifier,allowed,entry,manual) if original.suffix.lower()=='.zip' else start_project(workspace,path,identifier,allowed,manual)
    if entry:relative(entry)
    editor(identifier,allowed)
    if not manual and identifier not in {row['id'] for row in candidates(entry or original.name,allowed)}:raise ValueError('This editor does not support the document format')
    with locked(workspace) as folder:
        parent=confined(folder,folder/'editors');previous=list(parent.glob('*/session.json')) if parent.exists() else []
        for item in previous:
            try:root,value=record(folder,item.parent.name,allowed)
            except ValueError:continue
            if value.get('mode')!='project' and value['source']==path and value['editor']==identifier and value.get('archive_entry','')==entry:
                running=active_service(workspace,value['id'])
                return {**value,'native_extensions':native_extensions(value),'files':running.before} if running else view(root,value)
        if len(previous)>=100:raise ValueError('This conversation already has 100 editing drafts')
        from .editor_versions import selection
        version=selection(workspace,original,editor(identifier,allowed))
        sid=uuid.uuid4().hex;root=directory(folder,sid);(root/'files').mkdir(parents=True,mode=0o700)
        try:
            if original.suffix.lower()=='.zip':
                if not entry:raise ValueError('Choose a source document inside the archive')
                from .source_packages import extract
                extract(original,root/'files');target=root/'files'/entry
                if not target.is_file():raise ValueError('Source missing from archive')
            else:
                if entry:raise ValueError('Only archives have an inner source selector')
                target=root/'files'/original.name;shutil.copyfile(original,target);target.chmod(0o600)
                copy_dependencies(workspace,original,target)
            validate(target,root/'files');files(root)
            text_source=manual_text(target,identifier,manual)
        except (zipfile.BadZipFile,zipfile.LargeZipFile,RuntimeError):
            shutil.rmtree(root,ignore_errors=True);raise ValueError('The source is not a valid native document archive') from None
        except BaseException:shutil.rmtree(root,ignore_errors=True);raise
        value={'id':sid,'editor':identifier,'manual_selection':manual,'manual_text':text_source,**version,'source':path,'source_sha256':digest(original),'entry':entry or original.name,'archive_entry':entry,'revision':0,'published_revision':-1,'publications':[],'created_at':utcnow(),'updated_at':utcnow()}
        atomic_json(root/'session.json',value);return view(root,value)



def start_archive_project(workspace,path,identifier,allowed,entry,manual=False):
    relative(entry);original=source(workspace,path,large=True);fingerprint=digest(original)
    with locked(workspace) as folder:
        for item in (folder/'editors').glob('*/session.json'):
            try:root,value=record(folder,item.parent.name,allowed)
            except ValueError:continue
            if value.get('mode')=='project' and value.get('archive_source')==path and value.get('archive_sha256')==fingerprint and value.get('archive_entry')==entry and value['editor']==identifier:return view(root,value)
    public=confined(Path(workspace).resolve(),Path(workspace).resolve()/'workspace');public.mkdir(exist_ok=True)
    destination=Path(tempfile.mkdtemp(prefix='imported-source-',dir=public))
    try:
        from .source_packages import extract
        extract(original,destination)
        selected=confined(destination,destination/entry)
        if not selected.is_file():raise ValueError('Source missing from archive')
        virtual='/mnt/user-data/'+selected.relative_to(Path(workspace).resolve()).as_posix()
        result=start_project(workspace,virtual,identifier,allowed,manual)
        with locked(workspace) as folder:
            root,value=record(folder,result['id'],allowed)
            value.update(archive_source=path,archive_sha256=fingerprint,archive_entry=entry)
            atomic_json(root/'session.json',value)
        return {**result,'archive_source':path,'archive_entry':entry}
    except BaseException:shutil.rmtree(destination,ignore_errors=True);raise


def start_project(workspace,path,identifier,allowed,manual=False):
    original=source(workspace,path,large=True);definition=editor(identifier,allowed)
    if not manual and identifier not in {row['id'] for row in candidates(original.name,allowed)}:raise ValueError('This editor does not support the document format')
    public_root=original.relative_to(Path(workspace).resolve()).parts[0]
    with locked(workspace) as folder:
        for item in (folder/'editors').glob('*/session.json'):
            try:root,value=record(folder,item.parent.name,allowed)
            except ValueError:continue
            if value.get('mode')=='project' and value['source']==path and value['editor']==identifier:return view(root,value)
        from .editor_versions import selection
        sid=uuid.uuid4().hex;root=directory(folder,sid);root.mkdir(parents=True,mode=0o700)
        now=utcnow()
        value={'id':sid,'mode':'project','project_root':public_root,'editor':identifier,'manual_selection':manual,
               'manual_text':manual_text(original,identifier,manual),**selection(workspace,original,definition),
               'source':path,'source_sha256':digest(original),'entry':original.relative_to(Path(workspace).resolve()/public_root).as_posix(),
               'revision':0,'published_revision':-1,'publications':[],'created_at':now,'updated_at':now}
        # Snapshot the entry before opening; native applications subsequently write
        # directly. This is not a promise to intercept every arbitrary kernel write.
        shutil.copyfile(original,root/'original-source')
        atomic_json(root/'session.json',value);return view(root,value)


def active_service(workspace,sid):
    # Never acquire the runtime registry lock under the project file lock:
    # runtime creation acquires these in the opposite order. The immutable
    # registry snapshot only reads fully initialised service objects.
    from .editor_runtime import SESSIONS
    return next((service for service in list(SESSIONS.values()) if service.workspace==Path(workspace) and service.sid==sid and not service.closed),None)


def open_with(workspace,sid,identifier,allowed,manual=False):
    definition=editor(identifier,allowed)
    with locked(workspace) as folder:
        source_root,value=record(folder,sid,allowed)
        if value.get('mode')=='project':
            raise ValueError('Open the project file directly with the selected editor')
        require_quiet(workspace,sid)
        if not manual and identifier not in {row['id'] for row in candidates(value['entry'],allowed)}:
            raise ValueError('This editor does not support the document format')
        if len(list((folder/'editors').glob('*/session.json')))>=100:raise ValueError('This conversation already has 100 editing drafts')
        from .editor_versions import selection
        version={**{k:value[k] for k in ('tool_versions','editor_version','cli_version','source_environment_id') if k in value},'version_origin':'source_draft'} if identifier==value['editor'] else selection(workspace,source(workspace,value['source']),definition)
        new_id=uuid.uuid4().hex;target=directory(folder,new_id);(target/'files').mkdir(parents=True,mode=0o700)
        try:
            for row in files(source_root):
                original=confined(source_root,source_root/'files'/row['name']);destination=confined(target,target/'files'/row['name'])
                destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copyfile(original,destination);destination.chmod(0o600)
            now=utcnow();changed={**{k:v for k,v in value.items() if k not in ('source_environment_id','environment_profile','runtime_environment_id','runtime_interface_id')},**version,'id':new_id,'editor':identifier,'manual_selection':manual,'manual_text':manual_text(target/'files'/value['entry'],identifier,manual),
                'derived_from_session':sid,'derived_from_revision':value['revision'],
                'revision':0,'published_revision':-1,'publications':[],'created_at':now,'updated_at':now}
            atomic_json(target/'session.json',changed);return view(target,changed)
        except BaseException:shutil.rmtree(target,ignore_errors=True);raise


def require_quiet(workspace,sid):
    if active_service(workspace,sid):raise ValueError('Close and save the interactive environment before replacing or publishing draft files')


def get(workspace,sid,allowed):
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed)
        running=active_service(workspace,sid)
        if running and value.get('mode')!='project':return {**value,'native_extensions':native_extensions(value),'files':running.before}
        return view(root,value)


def listing(workspace,allowed):
    with locked(workspace) as folder:
        parent=confined(folder,folder/'editors');rows=[]
        for item in parent.glob('*/session.json') if parent.exists() else []:
            try:
                _,value=record(folder,item.parent.name,allowed)
                rows.append({**{key:value[key] for key in ('id','editor','source','entry','revision','published_revision','updated_at')},'mode':value.get('mode','draft')})
            except ValueError:continue
        return sorted(rows,key=lambda r:r['updated_at'],reverse=True)


def file(workspace,sid,name,allowed):
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed);base,name=file_location(root,name)
        if value.get('mode')!='project':require_quiet(workspace,sid)
        path=confined(base,base/name)
        if not path.is_file():raise ValueError('Document file not found')
        return path


def save(workspace,sid,name,data,expected_revision,allowed,entry=False):
    name=relative(name)
    if isinstance(data,bytes) and metadata(workspace,sid,allowed).get('mode')=='project':
        with tempfile.NamedTemporaryFile(prefix='righaven-editor-save-') as staged:
            staged.write(data);staged.flush()
            return save_project_file(workspace,sid,name,staged.name,expected_revision,allowed,entry)
    if not isinstance(data,bytes) or len(data)>MAX_FILE:raise ValueError('Document exceeds 64 MiB')
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed);base=file_root(root)
        if value.get('mode')!='project':require_quiet(workspace,sid)
        if value['revision']!=expected_revision:raise ValueError('Draft changed in another window; reload before saving')
        definition=editor(value['editor'],allowed)
        if entry and value.get('mode')!='project' and Path(name).suffix.lower() not in native_extensions(value):raise ValueError('Save the source in a native format; exports remain companion files')
        if value.get('manual_text') and name==value['entry']:plain_text(data)
        rows=files(root);old=next((r['bytes'] for r in rows if r['name']==name),0)
        if value.get('mode')!='project' and (sum(r['bytes'] for r in rows)-old+len(data)>MAX_TOTAL or len(rows)>=MAX_FILES and not old):raise ValueError('Editing bundle exceeds size limits')
        path=confined(base,base/name);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if value.get('mode')=='project' and path.is_file():
            backup=root/'history'/str(expected_revision)/name;backup.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copyfile(path,backup)
        fd,temporary=tempfile.mkstemp(dir=path.parent)
        try:
            with os.fdopen(fd,'wb') as stream:stream.write(data)
            os.replace(temporary,path)
        finally:Path(temporary).unlink(missing_ok=True)
        if entry:value['entry']=name
        value.update(revision=expected_revision+1,updated_at=utcnow());atomic_json(root/'session.json',value)
        return view(root,value)


@contextmanager
def project_parent(base,name):
    """Hold each directory FD so live native writes cannot redirect an HTTP save."""
    parts=relative(name).split('/');parent=None
    try:
        parent=os.open(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        for part in parts[:-1]:
            try:os.mkdir(part,mode=0o700,dir_fd=parent)
            except FileExistsError:pass
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
            os.close(parent);parent=child
        yield parent,parts[-1]
    except OSError as error:raise ValueError('Invalid document path') from error
    finally:
        if parent is not None:os.close(parent)


def save_project_file(workspace,sid,name,temporary,expected_revision,allowed,entry=False):
    """Promote a streamed upload; snapshots protect HTTP overwrites, not kernel IO."""
    name=relative(name)
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed)
        if value.get('mode')!='project':raise ValueError('Not a direct project session')
        if value['revision']!=expected_revision:raise ValueError('File changed in another window; reload before saving')
        base,local_name=file_location(root,name)
        with project_parent(base,local_name) as (parent,leaf):
            try:old=os.open(leaf,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            except FileNotFoundError:old=None
            if old is not None:
                with os.fdopen(old,'rb') as original:
                    if not stat.S_ISREG(os.fstat(original.fileno()).st_mode):raise ValueError('Invalid document path')
                    backup=root/'history'/str(expected_revision)/name
                    backup.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    with backup.open('wb') as previous:shutil.copyfileobj(original,previous)
            staged='righaven-save-'+uuid.uuid4().hex
            fd=os.open(staged,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            try:
                with os.fdopen(fd,'wb') as stream,open(temporary,'rb') as incoming:shutil.copyfileobj(incoming,stream)
                os.replace(staged,leaf,src_dir_fd=parent,dst_dir_fd=parent)
            finally:
                try:os.unlink(staged,dir_fd=parent)
                except FileNotFoundError:pass
        if entry:value['entry']=name
        value.update(revision=expected_revision+1,updated_at=utcnow());atomic_json(root/'session.json',value)
        result=view(root,value)
    from .audit_log import append
    append(workspace,'User','Project file saved','completed',name,context={'path':virtual_path(value,name),'editor':value['editor']})
    return result


def publish(workspace,sid,expected_revision,allowed):
    from .source_edits import edits
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed);require_quiet(workspace,sid)
        if value['revision']!=expected_revision:raise ValueError('Draft changed; reload before publishing')
        if value['published_revision']==expected_revision:return value['publications'][-1]
        if digest(source(workspace,value['source']))!=value['source_sha256']:raise ValueError('Original source changed; compare the new delivery before publishing')
        rows=files(root)
        if Path(value['entry']).suffix.lower() not in native_extensions(value):raise ValueError('Save the source in a native format; exports remain companion files')
        validate(root/'files'/value['entry'],root/'files')
        if value.get('manual_text'):plain_text((root/'files'/value['entry']).read_bytes())
        outputs=Path(workspace).resolve()/'outputs';target=confined(Path(workspace).resolve(),outputs/'source-revisions'/sid/str(expected_revision))
        virtual=lambda p:'/mnt/user-data/'+p.relative_to(Path(workspace).resolve()).as_posix()
        result=None
        if target.exists():
            for candidate in target.glob('righaven-revision-*.json'):
                if candidate.is_symlink() or candidate.stat().st_size>1000000:continue
                try:manifest=json.loads(candidate.read_text())
                except (ValueError,OSError):continue
                if manifest.get('editing_session')==sid and manifest.get('revision')==expected_revision and manifest.get('source_sha256')==value['source_sha256'] and manifest.get('files')==rows:
                    if all(confined(target,target/row['name']).is_file() and digest(target/row['name'])==row['sha256'] for row in rows):result=manifest['publication'];break
            if result is None:raise ValueError('Revision already exists; inspect it before retrying')
        else:
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            staged=Path(tempfile.mkdtemp(prefix='publish-',dir=root))
            try:
                for row in rows:
                    destination=staged/row['name'];destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700);shutil.copyfile(root/'files'/row['name'],destination);destination.chmod(0o600)
                    if digest(destination)!=row['sha256']:raise ValueError('Draft changed; reload before publishing')
                manifest='righaven-revision-'+uuid.uuid4().hex+'.json'
                result={'path':virtual(target/value['entry']),'manifest_path':virtual(target/manifest),'source':value['source'],'source_sha256':value['source_sha256'],'sha256':digest(staged/value['entry']),'editor':value['editor'],'revision':expected_revision,'files_count':len(rows),'at':utcnow(),'status':'source_copy','exports_regenerated':False}
                atomic_json(staged/manifest,{'schema_version':1,'editing_session':sid,'revision':expected_revision,'source_sha256':value['source_sha256'],'entry':value['entry'],'editor':value['editor'],'version':value['editor_version'],'files':rows,'publication':result})
                staged.rename(target)
            finally:
                if staged.exists():shutil.rmtree(staged,ignore_errors=True)
        history=[*edits(folder),result][-50:]
        while len(history)>1 and len(json.dumps(history).encode())>90000:history=history[1:]
        atomic_json(folder/'source-edits.json',history)
        value.update(published_revision=expected_revision,publications=[*value['publications'],result][-20:],updated_at=utcnow());atomic_json(root/'session.json',value)
    from .audit_log import append
    append(workspace,'User','Editor revision published','completed','Source and assets handed to the team; exports require regeneration',context={'path':result['path'],'editor':value['editor']})
    return result


def associations(workspace,path,allowed):
    """Prefer hashed editable sources from the same delivery, never guess by stem."""
    original=source(workspace,path,large=True);related=[]
    with locked(workspace) as folder:
        project=folder/'project.json'
        if project.is_file() and not project.is_symlink() and project.stat().st_size<=1000000:
            try:value=json.loads(project.read_text())
            except ValueError:value={}
            for step in value.get('steps',[]):
                for attempt in step.get('attempts',[]):
                    record=attempt.get('delivery_record') or {};entries=record.get('files',[])
                    def checked(item):
                        try:
                            candidate=source(workspace,item.get('path',''))
                            return candidate if item.get('sha256') and digest(candidate)==item['sha256'] else None
                        except (ValueError,OSError):return None
                    if not any(checked(item)==original for item in entries):continue
                    native=[item for item in entries if item.get('role')=='editable_source' and checked(item) not in (None,original)]
                    selected=native or [item for item in entries if item.get('role')=='source_archive' and checked(item) not in (None,original)]
                    for item in selected:
                        try:related.extend({**row,'source_path':item['path'],'source_role':item['role']} for row in discovery(workspace,item['path'],allowed))
                        except (ValueError,OSError):continue
    rows=[*related,*[{**row,'source_path':path,'source_role':'selected'} for row in discovery(workspace,path,allowed)]]
    seen=set();result=[]
    for row in rows:
        key=(row['id'],row.get('entry',''),row['source_path'])
        if key in seen:continue
        seen.add(key);result.append(row)
    return result[:200]


def open_file(workspace,sid,name,allowed):
    """Open beneath an owned directory FD; no path is followed during streaming."""
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed)
        if value.get('mode')!='project':require_quiet(workspace,sid)
        base,local_name=file_location(root,name)
        parts=local_name.split('/');parent=descriptor=None
        try:
            parent=os.open(base,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            for part in parts[:-1]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent);os.close(parent);parent=child
            descriptor=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            info=os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or (value.get('mode')!='project' and info.st_size>MAX_FILE):raise ValueError('Invalid document path')
            stream=os.fdopen(descriptor,'rb');descriptor=None;return stream
        except OSError:raise ValueError('Document file not found') from None
        finally:
            if parent is not None:os.close(parent)
            if descriptor is not None:os.close(descriptor)


def choose_entry(workspace,sid,name,expected_revision,allowed):
    name=relative(name)
    with locked(workspace) as folder:
        root,value=record(folder,sid,allowed);base=file_root(root)
        if value.get('mode')!='project':require_quiet(workspace,sid)
        if value['revision']!=expected_revision:raise ValueError('Draft changed; reload before publishing')
        if Path(name).suffix.lower() not in editor(value['editor'],allowed)['native_extensions']:raise ValueError('Save the source in a native format; exports remain companion files')
        path=confined(base,base/name)
        if not path.is_file():raise ValueError('Document file not found')
        if value.get('mode')=='project' and path.suffix.lower() in ('.ecproj','.fcproj','.scraft'):editing_document(path)
        else:validate(path,base)
        if value['entry']!=name:value.update(entry=name,revision=value['revision']+1,updated_at=utcnow());atomic_json(root/'session.json',value)
        return view(root,value)


def metadata(workspace,sid,allowed):
    with locked(workspace) as folder:
        _,value=record(folder,sid,allowed);return value
