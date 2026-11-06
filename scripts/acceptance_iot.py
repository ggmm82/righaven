"""Offline fixture of the iot toolkit, with known results.

Simulation must be deterministic; a Modbus TCP device served locally must be read
without writes, refuse a write without consent or without the owner's approval of that
exact command, and accept the approved one once, verified by reading the registers back.
"""
import json,subprocess,sys,time
from pathlib import Path
INSTALL=Path('/opt/righaven')
CONNECTIONS=Path('/run/righaven/connections')

SCENARIO={'start':'2026-03-02T00:00:00+00:00','duration_hours':24,'interval_seconds':3600,'seed':11,
          'devices':[{'group':'bus','count':2,'sensors':[{'name':'passengers','mode':'count','baseline':30,'noise':4,'profile':'commute','unit':'people'}]},
                     {'group':'bin','count':3,'sensors':[{'name':'fill','mode':'accumulate','rate_per_hour':4,'noise':0.1,'profile':'daytime','reset_at':90,'start':5,'max':100,'unit':'%'}]}]}
SERVER='''
import asyncio,sys
from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock,ModbusServerContext
try:from pymodbus.datastore import ModbusDeviceContext as Context
except ImportError:from pymodbus.datastore import ModbusSlaveContext as Context
store=Context(hr=ModbusSequentialDataBlock(1,[i*10 for i in range(100)]))
try:context=ModbusServerContext(devices=store,single=True)
except TypeError:context=ModbusServerContext(slaves=store,single=True)
asyncio.run(StartAsyncTcpServer(context=context,address=("127.0.0.1",int(sys.argv[1]))))
'''


def call(c,operation,allowed=(0,),**args):
    p=subprocess.run(['iot-cli','call',operation,json.dumps(args)],capture_output=True,text=True,timeout=300)
    c.commands.append({'argv':['iot-cli','call',operation,args],'returncode':p.returncode,'stdout':p.stdout[-3000:],'stderr':p.stderr[-2000:]})
    if p.returncode not in allowed:raise RuntimeError('iot.'+operation+': '+(p.stderr or p.stdout)[-2000:])
    return json.loads(p.stdout) if p.returncode==0 else p.stderr


def iot(c):
    scenario=c.root/'scenario.json';scenario.write_text(json.dumps(SCENARIO))
    first=call(c,'simulate',input=str(scenario),output=str(c.root/'Sim1'))
    again=call(c,'simulate',input=str(scenario),output=str(c.root/'Sim2'))
    rows=(c.root/'Sim1/telemetry.jsonl').read_text()
    c.check('Simulation produces one reading per device, sensor and hour',first['readings']==5*24 and first['devices']==5,first)
    c.check('Simulation is deterministic for the same seed',rows==(c.root/'Sim2/telemetry.jsonl').read_text() and again['readings']==first['readings'],'byte-identical telemetry')
    fill=[json.loads(line)['value'] for line in rows.splitlines() if '"fill"' in line]
    c.check('Accumulating sensors stay within their bounds and reset',fill and max(fill)<=100 and min(fill)>=5,{'min':min(fill),'max':max(fill)})
    python=str(INSTALL/'apps/iot/venv/bin/python');port=15502
    server=subprocess.Popen([python,'-c',SERVER,str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    created=not CONNECTIONS.exists()
    try:
        CONNECTIONS.mkdir(parents=True,exist_ok=True)
        base={'kind':'device','transport':'network','protocol':'modbus-tcp','host':'127.0.0.1','port':port,'unit':1,'url':f'modbus+tcp://127.0.0.1:{port}'}
        (CONNECTIONS/'acceptance-read.json').write_text(json.dumps({**base,'write_enabled':False}))
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from iot_job import command_fingerprint
        approved=[{'id':'acceptance','action':'send','fingerprint':command_fingerprint({'address':2,'values':[123,456]})}]
        (CONNECTIONS/'acceptance-consent.json').write_text(json.dumps({**base,'write_enabled':True}))
        (CONNECTIONS/'acceptance-write.json').write_text(json.dumps({**base,'write_enabled':True,'approvals':approved}))
        time.sleep(2)
        read=call(c,'capture',connection='acceptance-read',seconds=2,interval_seconds=0.5,register_address=1,register_count=3,output=str(c.root/'Capture'))
        first_row=json.loads((c.root/'Capture/telemetry.jsonl').read_text().splitlines()[0])
        c.check('Capture reads the device registers without writing',read['records']>=2 and first_row['value']=={'1':10,'2':20,'3':30},first_row)
        refused=call(c,'send',allowed=(1,),connection='acceptance-read',address=2,values=[5],output=str(c.root/'Refused'))
        c.check('A write without the owner consent is refused','not allowed' in refused,refused[-200:])
        unapproved=call(c,'send',allowed=(1,),connection='acceptance-consent',address=2,values=[123,456],output=str(c.root/'Unapproved'))
        c.check('Write consent alone is not enough: the exact command needs the owner approval','harness_device_change' in unapproved,unapproved[-200:])
        different=call(c,'send',allowed=(1,),connection='acceptance-write',address=2,values=[999],output=str(c.root/'Different'))
        c.check('A command different from the approved one is refused','harness_device_change' in different,different[-200:])
        sent=call(c,'send',connection='acceptance-write',address=2,values=[123,456],output=str(c.root/'Send'))
        c.check('A consented write is verified by reading it back',sent['written']['read_back']==[123,456] and sent['written']['read_back_matches'] is True,sent['written'])
    finally:
        server.terminate()
        for name in ('acceptance-read','acceptance-consent','acceptance-write'):(CONNECTIONS/(name+'.json')).unlink(missing_ok=True)
        if created:
            try:CONNECTIONS.rmdir();CONNECTIONS.parent.rmdir()
            except OSError:pass


CASES={'iot':iot}
