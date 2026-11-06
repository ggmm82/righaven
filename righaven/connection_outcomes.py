"""Destination execution evidence is distinct from connection permission.

Only destinations explicitly selected by the owner create an obligation. Other
connections remain optional resources. Only an owner API can defer an obligation.
"""
import json
from .acceptance import fingerprint
from .project_store import artifact_path
from .source_packages import digest
from .progress import clean_summary


def target_signature(record):
    return fingerprint({key:record.get(key) for key in ('kind','host','port','database','write_schema')})


def destinations(value):
    binding=value.get('connections') or {}
    return sorted(c for c in binding.get('ids',[]) if c in binding.get('write',[])
                  and (binding.get('uses') or {}).get(c)=='destination')


def receipts(workspace,value,role,handoff,output_files):
    """Bind a declared connection operation to its saved read-back evidence.

    This records evidence from execution, not a Gateway live database probe and
    not a certificate inferred from a local file or the connection test button.
    """
    from .connections import _read
    result=[];allowed=set((role or {}).get('connections',[]))
    binding=value.get('connections') or {}
    for item in handoff.get('connection_receipts',[]):
        identifier=item.get('id') if isinstance(item,dict) else None
        if identifier not in allowed or identifier not in binding.get('write',[]):
            raise ValueError('Connection execution evidence requires the authorized role and write grant')
        path=artifact_path(workspace,item.get('verification_path',''))
        if not path or path not in [artifact_path(workspace,p) for p in output_files] or path.stat().st_size>50000:
            raise ValueError('Connection execution evidence must be a saved assignment output')
        proof=json.loads(path.read_text())
        if not isinstance(proof,dict) or proof.get('connection_id')!=identifier:
            raise ValueError('Connection execution evidence does not match the selected destination')
        record=_read(binding['owner'],identifier)
        if proof.get('host')!=record.get('host') or proof.get('database')!=record.get('database') or proof.get('schema')!=record.get('write_schema'):
            raise ValueError('Connection execution evidence does not match the selected destination')
        readback=proof.get('read_back') or {}
        if (proof.get('operation')!='write' or proof.get('status')!='passed'
                or not isinstance(proof.get('objects'),list) or not proof['objects']
                or any(not isinstance(name,str) or not name.startswith(record['write_schema']+'.') or len(name)>200 for name in proof['objects'])
                or not isinstance(readback,dict) or readback.get('status')!='passed' or type(readback.get('rows_checked')) is not int or readback['rows_checked']<0
                or not readback.get('checked_at')):
            raise ValueError('Verify the destination by reading back the written objects before claiming completion')
        result.append({'id':identifier,'status':'passed','verification_path':str(path),
                       'sha256':digest(path),'contract_hash':(value.get('acceptance') or {}).get('hash'),
                       'target_hash':target_signature(record),
                       'objects':[clean_summary(name,200) for name in proof['objects'][:100]]})
    return result


def status(workspace,value):
    binding=value.get('connections') or {};result=[]
    for identifier in destinations(value):
        state='deferred' if identifier in binding.get('deferred',[]) else 'pending'
        evidence=None
        from .connections import _read
        try:target_hash=target_signature(_read(binding['owner'],identifier))
        except (ValueError,OSError,KeyError):target_hash=None
        if state!='deferred':
            for step in value.get('steps',[]):
                for attempt in step.get('attempts',[]):
                    if not attempt.get('validated') or attempt.get('status')!='completed' or attempt.get('stale_request'):continue
                    for receipt in attempt.get('connection_receipts',[]):
                        if receipt.get('id')!=identifier or receipt.get('contract_hash')!=(value.get('acceptance') or {}).get('hash'):continue
                        if not target_hash or receipt.get('target_hash')!=target_hash:continue
                        path=artifact_path(workspace,receipt.get('verification_path',''))
                        try:valid=path and digest(path)==receipt.get('sha256')
                        except OSError:valid=False
                        if valid:state='passed';evidence=receipt['verification_path']
        result.append({'id':identifier,'status':state,'evidence_path':evidence})
    return result


def require_complete(workspace,value):
    pending=[item['id'] for item in status(workspace,value) if item['status']=='pending']
    if pending:
        raise ValueError('Requested destinations are not verified: '+', '.join(pending)+'. Assign a role with these connections, perform the requested writes and save read-back evidence. Report any access or tool error. A local database is only a partial result; only the owner may defer the destination in Connections.')


INSTRUCTIONS=('A destination selected by the owner is part of the result, not merely an optional connection. '
    'If this role writes to one, use the delivered connection credentials, then read back the actual remote objects. '
    'Use dlt.load where supported: it emits connection-verification.json after read-back; include that file among the assignment outputs as technical report evidence, not the primary product. '
    'For another supported writer, save a JSON output with connection_id, host, database, schema, operation=write, status=passed, objects (nonempty schema-qualified list), '
    'read_back={status:passed, rows_checked:integer, checked_at:ISO timestamp}. '
    'Reference it in handoff.connection_receipts=[{id:connection ID, verification_path:saved output path}]. '
    'Do not infer success from a DuckDB/local file or a connection probe. If access or execution fails, report the exact redacted cause '
    'and keep the result partial; never substitute a local destination or change the owner goal without their explicit decision. ')
