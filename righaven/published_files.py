"""Read published conversation files without acquiring a second sandbox or sharing staging."""
import fnmatch
import hashlib
from pathlib import Path
from .project_store import workspace_path


def reference(path, state):
    for item in (state or {}).get('tool_artifacts', []):
        if isinstance(item, dict) and item.get('handle') == str(path).strip('`'):
            return item.get('real_ref', path)
    return path


def read(workspace, path, *, offset=0, limit=12000, start_line=None, end_line=None):
    root = Path(workspace).resolve() / 'outputs'
    local = workspace_path(workspace, path)
    if not local or not local.resolve().is_relative_to(root) or local.is_symlink() or not local.is_file():
        raise ValueError('Select an existing published file in this conversation outputs')
    if local.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('File exceeds the text reader limit; use a specialist for binary or large files')
    data = local.read_bytes()
    if b'\x00' in data:
        raise ValueError('This is a binary artifact; use its viewer or a specialist')
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        raise ValueError('This is a binary artifact; use its viewer or a specialist') from None
    if start_line is not None or end_line is not None:
        first = start_line or 1
        if first < 1 or (end_line is not None and end_line < first):
            raise ValueError('Invalid line range')
        text = ''.join(text.splitlines(keepends=True)[first-1:end_line])
    if type(offset) is not int or not 0 <= offset <= len(text):
        raise ValueError('Invalid file offset')
    end = min(len(text), offset + min(max(limit, 1), 16000))
    return {'path': '/mnt/user-data/' + local.relative_to(Path(workspace).resolve()).as_posix(),
            'sha256': hashlib.sha256(data).hexdigest(), 'content': text[offset:end],
            'offset': offset, 'next_offset': end if end < len(text) else None, 'total_characters': len(text)}


def inventory(workspace, path='/mnt/user-data/outputs', pattern='*'):
    root = Path(workspace).resolve() / 'outputs'
    local = workspace_path(workspace, path)
    if not local or not local.resolve().is_relative_to(root) or local.is_symlink() or not local.is_dir():
        raise ValueError('Select this conversation published outputs directory')
    if '..' in Path(pattern).parts or Path(pattern).is_absolute():
        raise ValueError('Invalid published file pattern')
    files = []
    for p in local.rglob('*'):
        if p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(root) and fnmatch.fnmatch(p.relative_to(local).as_posix(), pattern):
            files.append('/mnt/user-data/' + p.relative_to(Path(workspace).resolve()).as_posix())
            if len(files) >= 200:
                return {'files': sorted(files), 'truncated': True}
    return {'files': sorted(files), 'truncated': False}
