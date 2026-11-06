"""Adapter of the netscan toolkit.

A role scans only the networks of a connection the owner assigned to the task and the role
declared (/run/righaven/connections/ID.json). Targets outside those networks are refused here
and again in the job; vulnerability scans also need the owner's approval of the exact scope.
"""
import ipaddress,json,os,re,subprocess,tempfile
from pathlib import Path

APPS={'netscan'}
CONNECTIONS=Path('/run/righaven/connections')


def binary(app,cli):
    return str(cli.INSTALL/'apps/netscan/venv/bin/python')


def version_flags(app):
    return ['-c','import subprocess,shutil,defusedxml;print("defusedxml",defusedxml.__version__);print(subprocess.run(["nmap","--version"],capture_output=True,text=True).stdout.splitlines()[0]);print("testssl",bool(shutil.which("testssl") or shutil.which("testssl.sh")))']


def connection(name):
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}',str(name or '')):raise ValueError('Use the ID of a network connection assigned to the task')
    path=CONNECTIONS/(name+'.json')
    if not path.is_file():raise ValueError('Connection '+name+' is not available to this task: the role must declare it and the owner assign it')
    cfg=json.loads(path.read_text())
    if cfg.get('kind')!='network':raise ValueError('Connection '+name+' is not a network to map')
    return path,cfg


def inside(targets,cfg):
    allowed=[ipaddress.ip_network(r) for r in cfg.get('ranges',[])]
    for target in targets:
        try:network=ipaddress.ip_network(str(target),strict=False)
        except ValueError as error:raise ValueError('Not a network or address: '+str(target)[:60]) from error
        if not any(network.version==a.version and network.subnet_of(a) for a in allowed):
            raise ValueError('Target outside the networks authorized by the owner: '+str(target))


def invoke(app,action,args,cli):
    path,cfg=connection(args.get('connection'))
    inside(args.get('targets') or [],cfg)
    if action=='vulnerabilities' and cfg.get('write_enabled') is not True:
        raise ValueError('Vulnerability scans are not allowed: the owner must allow active scans on the connection and for this task')
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    output.mkdir(parents=True);(output/'Sources').mkdir()
    request={'action':action,'args':{k:v for k,v in args.items() if k not in ('output','connection')},'output':str(output),'connection_file':str(path)}
    python=binary(app,cli)
    if not Path(python).is_file():raise RuntimeError('netscan is not installed in this environment: add it to the environment tools')
    with tempfile.TemporaryDirectory(prefix='righaven-netscan-') as private:
        file=Path(private)/'request.json';file.write_text(json.dumps(request));file.chmod(0o600)
        clean={k:v for k,v in os.environ.items() if not re.match(r'(?i).*(PASSWORD|SECRET|TOKEN|CREDENTIALS|API_KEY)',k)}
        done=subprocess.run([python,str(Path(__file__).with_name('netscan_job.py')),str(file)],capture_output=True,text=True,errors='replace',
                            timeout=1400,env={**clean,'HOME':private},cwd=output)
    (output/'netscan-stdout.log').write_text(done.stdout);(output/'netscan-stderr.log').write_text(done.stderr)
    if done.returncode==3:raise ValueError((done.stderr or done.stdout).strip()[-2000:])
    if done.returncode:raise RuntimeError('netscan ended with code '+str(done.returncode)+': '+(done.stderr or done.stdout)[-2500:])
    result=json.loads(done.stdout.strip().splitlines()[-1])
    limits=result.pop('limits',[]);result['connection']=args['connection']
    (output/'receipt.json').write_text(json.dumps({'app':'netscan','operation':action,'inputs_sha256':{},'result':result,'limits':limits},indent=2,ensure_ascii=False))
    return result
