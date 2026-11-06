"""Adapter of the iot toolkit.

A role reaches a device only through a connection the owner assigned to the task and the
role declared: the Gateway mounts /run/righaven/connections/ID.json and, for devices attached
to the machine, passes that single device node to this container (read-only without write
consent). Every operation writes into a fresh output folder and leaves receipt.json.
"""
import json,os,re,subprocess,tempfile
from pathlib import Path

APPS={'iot'}
CONNECTIONS=Path('/run/righaven/connections')
WRITES=('send','inspect','flash')
ANDROID_WRITES=('install','uninstall','disable','enable','reboot','sideload')


def writes(action,args):
    return action in WRITES or (action=='android' and args.get('command') in ANDROID_WRITES) or (action=='obd' and args.get('command')=='clear_codes') or (action=='tuya' and args.get('command')=='set') or (action=='matter' and args.get('command')=='command')


def binary(app,cli):
    return str(cli.INSTALL/'apps/iot/venv/bin/python')


def version_flags(app):
    return ['-c','import serial,paho.mqtt,pymodbus,esptool,obd,tinytuya,websockets,shutil;print("pyserial",serial.__version__,"paho-mqtt",paho.mqtt.__version__,"pymodbus",pymodbus.__version__,"esptool",esptool.__version__,"obd",obd.__version__,"tinytuya",tinytuya.__version__,"websockets",websockets.__version__,"adb",bool(shutil.which("adb")))']


def connection(name,action,args=None):
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}',str(name or '')):raise ValueError('Use the ID of a device connection assigned to the task')
    path=CONNECTIONS/(name+'.json')
    if not path.is_file():raise ValueError('Connection '+name+' is not available to this task: the role must declare it and the owner assign it')
    cfg=json.loads(path.read_text())
    if cfg.get('kind')!='device':raise ValueError('Connection '+name+' is not a device: use the database tools for databases')
    if writes(action,args or {}) and cfg.get('write_enabled') is not True:
        raise ValueError('Writing to this device is not allowed: the owner must enable writing on the connection and allow it for this task')
    if action in ('inspect','flash') and cfg.get('transport') not in ('serial','local'):
        raise ValueError('esptool needs a serial connection (local port or RFC 2217)')
    if action=='android' and cfg.get('protocol')!='adb':
        raise ValueError('Connection '+name+' is not an Android device (ADB)')
    if action=='matter' and cfg.get('protocol')!='matter':
        raise ValueError('Connection '+name+' is not a Matter device: create it from the Matter devices list in Connections')
    if action=='tuya' and cfg.get('protocol')!='tuya':
        raise ValueError('Connection '+name+' is not a Tuya / Smart Life device (protocol tuya with device ID and local key)')
    if action=='obd' and not (cfg.get('transport') in ('serial','local') or cfg.get('protocol')=='tcp'):
        raise ValueError('An OBD adapter is a serial port (Bluetooth, USB, RFC 2217) or a TCP connection (Wi-Fi adapters)')
    return path,cfg


def invoke(app,action,args,cli):
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    output.mkdir(parents=True);(output/'Sources').mkdir()
    request={'action':action,'args':{k:v for k,v in args.items() if k not in ('output','input','connection')},'output':str(output)}
    inputs={}
    if action!='simulate':
        path,cfg=connection(args.get('connection'),action,args)
        request.update(connection_file=str(path),connection=args['connection'])
    if 'input' in args:
        source=cli.scoped(args['input'])
        inputs[source.name]=cli.digest(source)
        request['input']=str(source)
    python=binary(app,cli)
    if not Path(python).is_file():raise RuntimeError('iot is not installed in this environment: add it to the environment tools')
    with tempfile.TemporaryDirectory(prefix='righaven-iot-') as private:
        file=Path(private)/'request.json';file.write_text(json.dumps(request));file.chmod(0o600)
        clean={k:v for k,v in os.environ.items() if not re.match(r'(?i).*(PASSWORD|SECRET|TOKEN|CREDENTIALS|API_KEY)',k)}
        done=subprocess.run([python,str(Path(__file__).with_name('iot_job.py')),str(file)],capture_output=True,text=True,errors='replace',
                            timeout=900,env={**clean,'HOME':str(output)},cwd=output)
    (output/'iot-stdout.log').write_text(done.stdout);(output/'iot-stderr.log').write_text(done.stderr)
    if done.returncode==3:raise ValueError((done.stderr or done.stdout).strip()[-2000:])
    if done.returncode:raise RuntimeError('iot ended with code '+str(done.returncode)+': '+(done.stderr or done.stdout)[-2500:])
    result=json.loads(done.stdout.strip().splitlines()[-1])
    limits=result.pop('limits',[])
    if action!='simulate':result['connection']=args['connection']
    (output/'receipt.json').write_text(json.dumps({'app':'iot','operation':action,'inputs_sha256':inputs,'result':result,'limits':limits},indent=2,ensure_ascii=False))
    return result
