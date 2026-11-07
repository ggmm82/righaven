#!/usr/bin/env python3
"""iot toolkit job, run in the iot environment (pyserial, paho-mqtt, pymodbus, esptool, obd, tinytuya).

Input: a private request file written by iot_tools.py. Output: files in the output folder
and one JSON line on stdout. Exit code 3 is a user error (bad input, refused write).

Reading never needs the owner. Every write needs both the owner's write consent for the task
and the owner's approval of that exact change (harness_device_change), delivered once in the
connection file: the command fingerprint, the file digest, the package or the reboot mode.
"""
import csv,datetime,hashlib,json,math,os,random,re,select,shutil,socket,subprocess,sys,threading,time
import urllib.request
from pathlib import Path

MAX_PAYLOAD=64*1024


class UserError(ValueError):pass


COMMAND_FIELDS=('payload','encoding','topic','retain','method','address','values','coil')
COMMAND_DEFAULTS={'encoding':'text','retain':False,'coil':False,'method':'POST'}


def command_fingerprint(command):
    """Same function as righaven.device_changes.command_fingerprint."""
    value={k:command[k] for k in COMMAND_FIELDS if k in command and command[k] is not None and COMMAND_DEFAULTS.get(k,object())!=command[k]}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def approved(cfg,action,**match):
    """The owner's approval of this exact change, used once."""
    for approval in cfg.get('approvals') or []:
        if approval.get('action')==action and not approval.get('used') and all(approval.get(k)==v for k,v in match.items()):
            approval['used']=True
            return approval['id']
    raise UserError('This write needs the owner approval of this exact change: ask with harness_device_change ('+action+'), '
                    'then run it in the next assignment exactly as approved')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')


def text(data):
    try:return data.decode('utf-8')
    except UnicodeDecodeError:return data.hex()


def number(value):
    try:
        number=float(value)
        return number if math.isfinite(number) else None
    except (TypeError,ValueError):return None


def flatten(value,prefix=''):
    """Numeric fields of a JSON payload, for the summary (a.b.c -> value)."""
    if isinstance(value,dict):
        out={}
        for key,item in value.items():out.update(flatten(item,f'{prefix}{key}.'))
        return out
    if isinstance(value,bool):return {}
    found=number(value) if isinstance(value,(int,float,str)) else None
    return {prefix.rstrip('.') or 'value':found} if found is not None else {}


class Recorder:
    """Writes telemetry rows and keeps the statistics for summary.json."""
    def __init__(self,output,limit):
        self.output,self.limit=output,limit
        self.rows=0;self.fields={};self.first=self.last=None;self.gaps=[];self.previous=None;self.keys=[]
        self.jsonl=(output/'telemetry.jsonl').open('w')

    def add(self,row):
        if self.rows>=self.limit:return False
        row={'t':now(),**row}
        self.jsonl.write(json.dumps(row,ensure_ascii=False)+'\n')
        moment=time.monotonic()
        if self.previous is not None and moment-self.previous>5:self.gaps.append({'at':row['t'],'seconds':round(moment-self.previous,2)})
        self.previous=moment;self.first=self.first or row['t'];self.last=row['t'];self.rows+=1
        for key in row:
            if key not in self.keys:self.keys.append(key)
        values=row.get('value')
        parsed=values if isinstance(values,(dict,list)) else None
        if parsed is None and isinstance(values,str):
            try:parsed=json.loads(values)
            except ValueError:
                # Serial and TCP lines such as "T=21.5 H:40" or "21.5".
                pairs=re.findall(r'([A-Za-z_][\w.]{0,40})\s*[=:]\s*(-?\d+(?:\.\d+)?)',values)
                parsed={k:float(v) for k,v in pairs} if pairs else values
        for name,value in (flatten(parsed) if parsed is not None else {}).items():
            stats=self.fields.setdefault(name,{'count':0,'min':value,'max':value,'sum':0.0})
            stats['count']+=1;stats['min']=min(stats['min'],value);stats['max']=max(stats['max'],value);stats['sum']+=value
        return True

    def close(self,seconds,extra=None):
        self.jsonl.close()
        with (self.output/'telemetry.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=self.keys or ['t'],extrasaction='ignore')
            writer.writeheader()
            with (self.output/'telemetry.jsonl').open() as rows:
                for line in rows:
                    writer.writerow({k:(json.dumps(v) if isinstance(v,(dict,list)) else v) for k,v in json.loads(line).items()})
        fields={k:{'count':v['count'],'min':v['min'],'max':v['max'],'mean':round(v['sum']/v['count'],6)} for k,v in sorted(self.fields.items())}
        summary={'records':self.rows,'first':self.first,'last':self.last,'seconds':seconds,
                 'rate_per_second':round(self.rows/seconds,3) if seconds else None,'gaps_over_5s':self.gaps[:50],'numeric_fields':fields,**(extra or {})}
        (self.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False))
        return summary


# --- Transports -----------------------------------------------------------------------------

def open_serial(cfg,write):
    url=cfg['url'];baud=cfg.get('baud',115200)
    if cfg['transport']=='local' and not write:
        return ReadOnlyTTY(url,baud)
    import serial
    try:return serial.serial_for_url(url,baudrate=baud,timeout=0.5,do_not_open=False)
    except (serial.SerialException,OSError) as error:raise UserError('Cannot open '+url+': '+str(error)) from error


class ReadOnlyTTY:
    """Reads a local serial device opened read-only: without write consent the container has no write access to it."""
    SPEEDS={1200:'B1200',2400:'B2400',4800:'B4800',9600:'B9600',19200:'B19200',38400:'B38400',57600:'B57600',115200:'B115200',
            230400:'B230400',460800:'B460800',921600:'B921600'}

    def __init__(self,path,baud):
        import termios,tty
        try:self.fd=os.open(path,os.O_RDONLY|os.O_NOCTTY|os.O_NONBLOCK)
        except OSError as error:raise UserError('Cannot open '+path+' for reading: '+str(error)) from error
        try:
            attributes=termios.tcgetattr(self.fd);tty.setraw(self.fd)
            attributes=termios.tcgetattr(self.fd)
            speed=getattr(termios,self.SPEEDS[baud]);attributes[4]=attributes[5]=speed
            termios.tcsetattr(self.fd,termios.TCSANOW,attributes)
        except (termios.error,OSError):pass  # not a terminal (for example a USB character device): read bytes as they are

    def read(self,size):
        ready,_,_=select.select([self.fd],[],[],0.5)
        if not ready:return b''
        try:return os.read(self.fd,size)
        except BlockingIOError:return b''

    def write(self,data):raise UserError('Writing to this device is not allowed in this task')

    def close(self):os.close(self.fd)


def lines(source,deadline,record,origin,until=b''):
    """Lines read until the deadline; with until (a prompt such as b'>' or b'OK'), the reply ends there."""
    buffer=b''
    while time.monotonic()<deadline:
        chunk=source.read(4096)
        if not chunk:continue
        buffer+=chunk
        while b'\n' in buffer:
            line,buffer=buffer.split(b'\n',1)
            if not record.add({'source':origin,'value':text(line.rstrip(b'\r'))}):return
            if until and until in line:return
        if until and until in buffer:
            # Prompt protocols (ELM327, AT modems) end lines with a bare carriage return.
            for line in re.split(rb'[\r\n]+',buffer):
                if line and not record.add({'source':origin,'value':text(line)}):return
            return
        if len(buffer)>MAX_PAYLOAD:
            if not record.add({'source':origin,'value':text(buffer)}):return
            buffer=b''
    if buffer:record.add({'source':origin,'value':text(buffer)})


def reply_until(args):
    """The end of a reply (a prompt such as > or OK): text, or hex bytes with encoding hex."""
    value=args.get('reply_until')
    if value is None or value=='':return b''
    if not isinstance(value,str) or len(value)>16:raise UserError('reply_until: at most 16 characters')
    if args.get('encoding')=='hex':
        try:return bytes.fromhex(value)
        except ValueError as error:raise UserError('reply_until must be hexadecimal bytes with encoding hex') from error
    return value.encode()


def valid_filter(value):
    levels=value.split('/')
    return all(level in ('+','#') or ('+' not in level and '#' not in level) for level in levels) and '#' not in levels[:-1]


def topic_matches(subscription,topic):
    """MQTT topic filter matching (+ one level, # the rest)."""
    wanted,levels=subscription.split('/'),topic.split('/')
    for i,part in enumerate(wanted):
        if part=='#':return not topic.startswith('$') or i>0
        if i>=len(levels) or (part!='+' and part!=levels[i]):return False
        if part=='+' and i==0 and levels[0].startswith('$'):return False
    return len(levels)==len(wanted)


def mqtt_client(cfg):
    import paho.mqtt.client as mqtt
    client=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id='righaven-'+os.urandom(4).hex())
    if cfg.get('username'):client.username_pw_set(cfg['username'],cfg.get('password') or None)
    if cfg.get('tls'):client.tls_set()
    return client


def capture(cfg,args,output):
    seconds=args.get('seconds',30);limit=args.get('max_records',10000);interval=args.get('interval_seconds',1.0)
    record=Recorder(output,limit);deadline=time.monotonic()+seconds;started=time.monotonic();extra={}
    transport,protocol=cfg['transport'],cfg.get('protocol')
    if transport in ('serial','local'):
        port=open_serial(cfg,False)
        try:lines(port,deadline,record,cfg['url'])
        finally:port.close()
    elif protocol=='mqtt':
        client=mqtt_client(cfg);errors=[]
        def on_connect(client,userdata,flags,reason,properties=None):
            if getattr(reason,'is_failure',False):errors.append(str(reason))
            else:client.subscribe(cfg.get('topic','#'),qos=0)
        def on_message(client,userdata,message):
            if not record.add({'source':message.topic,'topic':message.topic,'value':text(message.payload[:MAX_PAYLOAD]),'retained':bool(message.retain)}):client.disconnect()
        client.on_connect,client.on_message=on_connect,on_message
        try:client.connect(cfg['host'],cfg['port'],keepalive=30)
        except OSError as error:raise UserError('MQTT broker not reachable: '+str(error)) from error
        while time.monotonic()<deadline and record.rows<limit and not errors:client.loop(timeout=0.5)
        client.disconnect()
        if errors:raise UserError('MQTT broker refused the connection: '+errors[0])
        extra['topic']=cfg.get('topic','#')
    elif protocol=='modbus-tcp':
        kind,address,count=args.get('register_kind','holding'),args.get('register_address',0),args.get('register_count',10)
        client=modbus(cfg)
        reader={'holding':client.read_holding_registers,'input':client.read_input_registers,'coil':client.read_coils,'discrete':client.read_discrete_inputs}[kind]
        try:
            while time.monotonic()<deadline and record.rows<limit:
                response=unit_call(reader,cfg,address,count=count)
                if response.isError():raise UserError('Modbus error: '+str(response))
                values=list(response.registers if kind in ('holding','input') else response.bits[:count])
                record.add({'source':f'{kind}:{address}','value':{str(address+i):int(v) for i,v in enumerate(values)}})
                time.sleep(interval)
        finally:client.close()
        extra['registers']={'kind':kind,'address':address,'count':count}
    elif protocol=='http':
        while time.monotonic()<deadline and record.rows<limit:
            try:
                with urllib.request.urlopen(request(cfg),timeout=10) as response:
                    body=response.read(MAX_PAYLOAD);status=response.status
            except OSError as error:raise UserError('HTTP device not reachable: '+str(error)) from error
            record.add({'source':cfg['url'],'status':status,'value':text(body)})
            time.sleep(interval)
    else:
        with socket.create_connection((cfg['host'],cfg['port']),timeout=10) as stream:
            stream.setblocking(False)
            lines(SocketReader(stream),deadline,record,cfg['url'])
    elapsed=round(time.monotonic()-started,2)
    summary=record.close(elapsed,extra)
    return {'status':'passed' if summary['records'] else 'no_data','records':summary['records'],'seconds':elapsed,
            'files':['telemetry.jsonl','telemetry.csv','summary.json'],'numeric_fields':list(summary['numeric_fields'])[:40],
            'limits':['Capture only reads: nothing was written to the device.','The window is a sample: behaviour outside it is not observed.']}


class SocketReader:
    def __init__(self,stream):self.stream=stream
    def read(self,size):
        ready,_,_=select.select([self.stream],[],[],0.5)
        if not ready:return b''
        data=self.stream.recv(size)
        if not data:raise UserError('The device closed the connection')
        return data


def request(cfg,data=None,method='GET'):
    headers={'Content-Type':'application/json'} if data is not None else {}
    item=urllib.request.Request(cfg['url'],data=data,method=method,headers=headers)
    if cfg.get('username'):
        import base64
        token=base64.b64encode((cfg['username']+':'+cfg.get('password','')).encode()).decode()
        item.add_header('Authorization','Basic '+token)
    return item


def modbus(cfg):
    from pymodbus.client import ModbusTcpClient
    client=ModbusTcpClient(cfg['host'],port=cfg['port'],timeout=5)
    if not client.connect():raise UserError('Modbus device not reachable: '+cfg['host']+':'+str(cfg['port']))
    return client


def unit_call(function,cfg,*args,**kwargs):
    # pymodbus renamed the unit parameter over time (slave -> device_id).
    for name in ('device_id','slave'):
        try:return function(*args,**kwargs,**{name:cfg.get('unit',1)})
        except TypeError:continue
    return function(*args,**kwargs)


def payload(args):
    raw=args.get('payload','')
    encoding=args.get('encoding','text')
    if encoding=='hex':
        if not re.fullmatch(r'([0-9a-fA-F]{2})*',raw):raise UserError('payload is not hexadecimal')
        data=bytes.fromhex(raw)
    elif encoding=='json':
        try:data=json.dumps(json.loads(raw)).encode()
        except ValueError as error:raise UserError('payload is not valid JSON') from error
    else:data=raw.encode()
    if len(data)>MAX_PAYLOAD:raise UserError('payload larger than 64 KiB')
    return data


def send(cfg,args,output):
    approval=approved(cfg,'send',fingerprint=command_fingerprint(args))
    transport,protocol=cfg['transport'],cfg.get('protocol')
    reply_seconds=args.get('reply_seconds',2);written={};reply=Recorder(output,1000)
    until=reply_until(args)
    if transport in ('serial','local'):
        data=payload(args);port=open_serial(cfg,True)
        try:
            port.write(data);written={'bytes':len(data)}
            lines(port,time.monotonic()+reply_seconds,reply,cfg['url'],until)
        finally:port.close()
    elif protocol=='mqtt':
        topic=args.get('topic')
        if not topic or not re.fullmatch(r'[^\x00-\x20#+]{1,200}',topic):raise UserError('send to MQTT needs a topic without wildcards')
        data=payload(args);client=mqtt_client(cfg)
        listen=args.get('reply_topic')
        if listen is not None and (not re.fullmatch(r'[^\x00-\x1f]{1,200}',listen) or not valid_filter(listen)):
            raise UserError('reply_topic must be an MQTT topic or filter (+ and # only as whole levels)')
        subscribed,heard=threading.Event(),threading.Event()
        if listen:
            # Subscribed before publishing, in the same connection: a device that answers at once is not missed.
            allowed=cfg.get('topic','#')
            def on_message(client,userdata,message):
                if topic_matches(allowed,message.topic) and not message.retain:
                    reply.add({'source':message.topic,'topic':message.topic,'value':text(message.payload[:MAX_PAYLOAD])})
                    if until and until in message.payload:heard.set()
            client.on_message=on_message
            client.on_subscribe=lambda *_:subscribed.set()
        try:client.connect(cfg['host'],cfg['port'],keepalive=30)
        except OSError as error:raise UserError('MQTT broker not reachable: '+str(error)) from error
        client.loop_start()
        if listen:
            client.subscribe(listen,qos=0)
            if not subscribed.wait(10):
                client.loop_stop();client.disconnect()
                raise UserError('The broker did not confirm the subscription to reply_topic')
        info=client.publish(topic,data,qos=1,retain=args.get('retain',False))
        info.wait_for_publish(timeout=10)
        if listen and info.is_published():
            heard.wait(reply_seconds)  # the whole reply_seconds, or until a message contains reply_until
        client.loop_stop();client.disconnect()
        if not info.is_published():raise UserError('The broker did not confirm the message')
        written={'topic':topic,'bytes':len(data),'qos':1,'retain':args.get('retain',False),**({'reply_topic':listen} if listen else {})}
    elif protocol=='modbus-tcp':
        if 'address' not in args or not args.get('values'):raise UserError('send to Modbus needs address and values')
        client=modbus(cfg)
        try:
            address,values=args['address'],args['values']
            if args.get('coil'):response=unit_call(client.write_coils,cfg,address,[bool(v) for v in values])
            else:response=unit_call(client.write_registers,cfg,address,values)
            if response.isError():raise UserError('Modbus error: '+str(response))
            check=unit_call(client.read_coils if args.get('coil') else client.read_holding_registers,cfg,address,count=len(values))
            read=None if check.isError() else [int(v) for v in (check.bits[:len(values)] if args.get('coil') else check.registers)]
            written={'address':address,'values':values,'coil':bool(args.get('coil')),'read_back':read,
                     'read_back_matches':read==[int(bool(v)) if args.get('coil') else v for v in values] if read is not None else None}
        finally:client.close()
    elif protocol=='http':
        data=payload(args);method=args.get('method','POST')
        try:
            with urllib.request.urlopen(request(cfg,data,method),timeout=15) as response:
                body=response.read(MAX_PAYLOAD);status=response.status
        except OSError as error:raise UserError('HTTP device refused or not reachable: '+str(error)) from error
        written={'method':method,'bytes':len(data),'status':status}
        reply.add({'source':cfg['url'],'status':status,'value':text(body)})
    else:
        data=payload(args)
        with socket.create_connection((cfg['host'],cfg['port']),timeout=10) as stream:
            stream.sendall(data);stream.setblocking(False);written={'bytes':len(data)}
            lines(SocketReader(stream),time.monotonic()+reply_seconds,reply,cfg['url'],until)
    summary=reply.close(reply_seconds)
    (output/'written.json').write_text(json.dumps({'at':now(),'approval':approval,**written},indent=2))
    return {'status':'passed','approval':approval,'written':written,'reply_records':summary['records'],'files':['written.json','telemetry.jsonl','summary.json'],
            'limits':['The device accepted the write; its effect on the physical process must be checked by the owner.']}


# --- esptool --------------------------------------------------------------------------------

def esptool(cfg,args,output,*command):
    if cfg['transport']=='local':port=cfg['url']
    else:port=cfg['url']+'?ign_set_control'
    argv=[sys.executable,'-m','esptool','--chip',args.get('chip','auto'),'--port',port,'--baud',str(args.get('baud',cfg.get('baud',115200))),*command]
    done=subprocess.run(argv,capture_output=True,text=True,errors='replace',timeout=600,cwd=output)
    log=output/'esptool.log'
    with log.open('a') as stream:stream.write('$ esptool '+' '.join(argv[3:])+'\n'+done.stdout+done.stderr+'\n')
    if done.returncode:raise UserError('esptool failed ('+str(done.returncode)+'): '+(done.stderr or done.stdout).strip()[-1500:])
    return done.stdout


def identity(log):
    found={}
    for key,pattern in (('chip',r'Chip (?:is|type):\s*(.+)'),('mac',r'MAC:\s*([0-9a-fA-F:]{17})'),('flash_size',r'Detected flash size:\s*(\S+)'),
                        ('features',r'Features:\s*(.+)'),('crystal',r'Crystal (?:is|frequency):\s*(.+)')):
        match=re.search(pattern,log)
        if match:found[key]=match.group(1).strip()
    return found


def inspect(cfg,args,output):
    found=identity(esptool(cfg,args,output,'flash-id'))
    (output/'device.json').write_text(json.dumps(found,indent=2))
    return {'status':'passed' if found.get('chip') else 'unknown','device':found,'files':['device.json','esptool.log'],
            'limits':['The board was reset into its bootloader to be identified.']}


def flash(cfg,args,source,output):
    image=Path(source)
    if image.suffix.lower()!='.bin' or not image.is_file():raise UserError('input must be the firmware .bin to write')
    if image.stat().st_size>16*1024*1024:raise UserError('firmware larger than 16 MiB')
    digest=hashlib.sha256(image.read_bytes()).hexdigest();offset=args.get('offset','0x0')
    approval=approved(cfg,'flash',sha256=digest)
    if not re.fullmatch(r'0x[0-9a-fA-F]{1,8}',offset):raise UserError('offset must be hexadecimal, for example 0x10000')
    shutil.copy2(image,output/'Sources'/image.name)
    before=identity(esptool(cfg,args,output,'flash-id'))
    if args.get('erase'):esptool(cfg,args,output,'erase-flash')
    esptool(cfg,args,output,'write-flash',offset,str(image))
    esptool(cfg,args,output,'verify-flash',offset,str(image))
    result={'status':'passed','approval':approval,'device':before,'image':image.name,'image_sha256':digest,'offset':offset,'erased':bool(args.get('erase')),'verified':True,
            'files':['esptool.log','flash.json'],
            'limits':['Flash content matches the image; the firmware behaviour on the board still has to be observed (for example with iot.capture).']}
    (output/'flash.json').write_text(json.dumps({'at':now(),**result},indent=2))
    return result


# --- Simulation -----------------------------------------------------------------------------

PROFILES={'flat':[1.0]*24,
          'commute':[0.1,0.05,0.05,0.05,0.1,0.3,0.7,1.0,0.9,0.6,0.5,0.55,0.6,0.55,0.5,0.6,0.8,1.0,0.9,0.6,0.4,0.3,0.2,0.15],
          'daytime':[0.2,0.15,0.1,0.1,0.15,0.3,0.5,0.7,0.85,0.95,1.0,1.0,1.0,1.0,0.95,0.9,0.85,0.8,0.7,0.55,0.45,0.35,0.3,0.25],
          'evening':[0.3,0.2,0.15,0.1,0.1,0.15,0.25,0.35,0.4,0.45,0.5,0.55,0.6,0.6,0.6,0.65,0.7,0.8,0.95,1.0,1.0,0.9,0.7,0.45]}


def scenario(path):
    try:data=json.loads(Path(path).read_text())
    except ValueError as error:raise UserError('scenario is not valid JSON') from error
    if not isinstance(data,dict) or not isinstance(data.get('devices'),list) or not data['devices']:
        raise UserError('scenario needs devices: [{"group": ..., "count": N, "sensors": [...]}]')
    start=datetime.datetime.fromisoformat(data.get('start','2026-01-05T00:00:00+00:00'))
    if start.tzinfo is None:start=start.replace(tzinfo=datetime.timezone.utc)
    hours=data.get('duration_hours',24);step=data.get('interval_seconds',300)
    if not (isinstance(hours,(int,float)) and 0<hours<=24*31) or not (isinstance(step,int) and 1<=step<=86400):
        raise UserError('duration_hours up to 744 and interval_seconds between 1 and 86400')
    total=sum(int(g.get('count',1)) for g in data['devices'])
    if total>5000:raise UserError('at most 5000 simulated devices')
    if total*hours*3600/step>2_000_000:raise UserError('more than 2 million readings: shorten the period or increase interval_seconds')
    for group in data['devices']:
        if not isinstance(group,dict) or not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',str(group.get('group',''))) or not group.get('sensors'):
            raise UserError('each device group needs a group name (letters, digits, - or _) and sensors')
        for sensor in group['sensors']:
            if not re.fullmatch(r'[A-Za-z0-9_]{1,40}',str(sensor.get('name',''))):raise UserError('each sensor needs a name (letters, digits or _)')
            if sensor.get('profile','flat') not in PROFILES and not (isinstance(sensor.get('profile'),list) and len(sensor['profile'])==24):
                raise UserError('profile: flat, commute, daytime, evening or 24 hourly factors')
    return data,start,hours,step


def simulate(args,source,output):
    data,start,hours,step=scenario(source)
    shutil.copy2(source,output/'Sources'/Path(source).name)
    rng=random.Random(args.get('seed',data.get('seed',20260105)))
    events=data.get('events',[])
    files={};summary={};count=0
    writer=(output/'telemetry.jsonl').open('w')
    columns=['t','device','group','sensor','value','unit','status']
    table=(output/'telemetry.csv').open('w',newline='');csv_writer=csv.writer(table);csv_writer.writerow(columns)
    steps=int(hours*3600/step)
    for group in data['devices']:
        for index in range(int(group.get('count',1))):
            device=f"{group['group']}-{index+1:04d}"
            state={s['name']:float(s.get('start',s.get('baseline',0))) for s in group['sensors']}
            failed_at=None
            failure=float(group.get('failure_rate_per_day',0))
            for k in range(steps):
                moment=start+datetime.timedelta(seconds=k*step)
                if failed_at is None and failure and rng.random()<failure*step/86400:failed_at=moment
                status='offline' if failed_at else 'ok'
                if status=='offline' and rng.random()<0.98:continue
                for sensor in group['sensors']:
                    name=sensor['name'];profile=sensor.get('profile','flat')
                    factor=(PROFILES[profile] if isinstance(profile,str) else profile)[moment.hour]
                    if moment.weekday()>=5:factor*=float(group.get('weekend_factor',sensor.get('weekend_factor',1.0)))
                    for event in events:
                        if event.get('group') in (None,group['group']) and event.get('sensor') in (None,name):
                            begin=datetime.datetime.fromisoformat(event['start']);end=datetime.datetime.fromisoformat(event['end'])
                            begin=begin if begin.tzinfo else begin.replace(tzinfo=datetime.timezone.utc);end=end if end.tzinfo else end.replace(tzinfo=datetime.timezone.utc)
                            if begin<=moment<end:factor*=float(event.get('factor',1.0))
                    mode=sensor.get('mode','level')
                    if mode=='accumulate':
                        # Fill level, counters: grows with the profile, resets when emptied.
                        state[name]+=float(sensor.get('rate_per_hour',1))*step/3600*factor*max(0.0,rng.gauss(1,float(sensor.get('noise',0.1))))
                        reset=sensor.get('reset_at')
                        if reset is not None and state[name]>=float(reset):state[name]=float(sensor.get('start',0))
                        value=state[name]
                    elif mode=='count':
                        # People, vehicles or events per interval.
                        value=float(max(0,round(rng.gauss(float(sensor.get('baseline',0))*factor,float(sensor.get('noise',1))))))
                    else:
                        value=float(sensor.get('baseline',0))*factor+float(sensor.get('drift_per_day',0))*(k*step/86400)+rng.gauss(0,float(sensor.get('noise',0)))
                    low,high=sensor.get('min'),sensor.get('max')
                    if low is not None:value=max(float(low),value)
                    if high is not None:value=min(float(high),value)
                    value=round(value,int(sensor.get('decimals',2)))
                    row={'t':moment.isoformat(),'device':device,'group':group['group'],'sensor':name,'value':value,'unit':sensor.get('unit',''),'status':status}
                    writer.write(json.dumps(row)+'\n');csv_writer.writerow([row[c] for c in columns]);count+=1
                    stats=summary.setdefault(group['group']+'.'+name,{'count':0,'min':value,'max':value,'sum':0.0,'unit':sensor.get('unit','')})
                    stats['count']+=1;stats['min']=min(stats['min'],value);stats['max']=max(stats['max'],value);stats['sum']+=value
            files[device]=failed_at.isoformat() if failed_at else None
    writer.close();table.close()
    sensors={k:{'count':v['count'],'min':v['min'],'max':v['max'],'mean':round(v['sum']/v['count'],4),'unit':v['unit']} for k,v in sorted(summary.items())}
    failures={k:v for k,v in files.items() if v}
    (output/'summary.json').write_text(json.dumps({'readings':count,'devices':len(files),'start':start.isoformat(),'hours':hours,'interval_seconds':step,
                                                   'sensors':sensors,'failed_devices':failures},indent=2))
    return {'status':'passed','readings':count,'devices':len(files),'failed_devices':len(failures),'sensors':list(sensors)[:40],
            'files':['telemetry.jsonl','telemetry.csv','summary.json'],
            'limits':['Synthetic data from the scenario: it tests the analysis and the hypotheses, not the real behaviour of people or devices.',
                      'Calibrate baselines, profiles and failure rates with real measurements before drawing conclusions.']}


# --- Android over network debugging (ADB) ---------------------------------------------------

PACKAGE=re.compile(r'[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_]+)+')
PROPERTIES={'ro.product.brand':'brand','ro.product.model':'model','ro.product.device':'device','ro.build.version.release':'android',
            'ro.build.version.sdk':'sdk','ro.build.version.security_patch':'security_patch','ro.build.fingerprint':'fingerprint',
            'ro.product.cpu.abi':'abi','ro.build.characteristics':'characteristics'}


class Adb:
    """One adb server for this job, with the connection's own key: the device asks to authorize it once."""
    def __init__(self,cfg,output):
        import tempfile
        if not shutil.which('adb'):raise RuntimeError('adb is not installed in this environment: add the iot tool to the environment')
        self.home=Path(tempfile.mkdtemp(prefix='righaven-adb-'));self.output=output
        key=self.home/'adbkey';key.write_text(cfg.get('adb_key',''));key.chmod(0o600)
        self.env={**{k:v for k,v in os.environ.items() if k in ('PATH','LANG','TZ')},'HOME':str(self.home),'ADB_VENDOR_KEYS':str(key),
                  'ANDROID_SDK_HOME':str(self.home),'ANDROID_USER_HOME':str(self.home/'.android')}
        self.serial=f"{cfg['host']}:{cfg['port']}"

    def run(self,*args,timeout=120,check=True,device=True):
        argv=['adb',*(['-s',self.serial] if device else []),*args]
        done=subprocess.run(argv,capture_output=True,text=True,errors='replace',timeout=timeout,env=self.env)
        with (self.output/'adb.log').open('a') as log:log.write('$ '+' '.join(argv)+'\n'+done.stdout[-4000:]+done.stderr[-2000:]+'\n')
        if check and done.returncode:raise UserError('adb '+args[0]+' failed: '+(done.stderr or done.stdout).strip()[-800:])
        return done.stdout

    def __enter__(self):
        self.run('start-server',device=False)
        self.run('connect',self.serial,device=False,check=False)
        state='';deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            state=self.run('get-state',check=False,timeout=20).strip()
            if state in ('device','sideload','recovery'):return self
            if 'unauthorized' in self.run('devices',device=False,check=False):state='unauthorized'
            time.sleep(3);self.run('connect',self.serial,device=False,check=False)
        if state=='unauthorized':
            raise UserError('The device has not authorized RigHaven yet: on the TV accept the debugging prompt ("Always allow from this computer") and retry')
        raise UserError('Android device not reachable on '+self.serial+': turn on network debugging (Developer options) and check the address')

    def __exit__(self,*error):
        self.run('disconnect',self.serial,device=False,check=False)
        self.run('kill-server',device=False,check=False)
        shutil.rmtree(self.home,ignore_errors=True)

    def state(self):
        return self.run('get-state',check=False,timeout=20).strip()


def properties(adb):
    found={}
    for line in adb.run('shell','getprop').splitlines():
        match=re.fullmatch(r'\[([^\]]+)\]: \[(.*)\]',line.strip())
        if match and match.group(1) in PROPERTIES:found[PROPERTIES[match.group(1)]]=match.group(2)
    return found


def packages(adb,flag=''):
    text=adb.run('shell','pm','list','packages',*( [flag] if flag else []))
    return sorted(line.split(':',1)[1].strip() for line in text.splitlines() if line.startswith('package:'))


def android(cfg,args,source,output):
    command=args['command']
    package=args.get('package','')
    if command in ('uninstall','disable','enable') and not PACKAGE.fullmatch(package):raise UserError('package must be an Android package name, for example com.example.app')
    approval=None
    if command in ('install','sideload'):
        image=Path(source or '')
        if image.suffix.lower()!=('.apk' if command=='install' else '.zip') or not image.is_file():
            raise UserError('input must be the '+('.apk to install' if command=='install' else 'OTA .zip to sideload'))
        digest=hashlib.sha256(image.read_bytes()).hexdigest()
        approval=approved(cfg,command,sha256=digest)
    elif command in ('uninstall','disable','enable'):approval=approved(cfg,command,package=package)
    elif command=='reboot':approval=approved(cfg,'reboot',mode=args.get('mode','system'))
    with Adb(cfg,output) as adb:
        state=adb.state()
        if command=='sideload':
            if state!='sideload':raise UserError('The device is not in sideload mode ('+state+'): reboot it into sideload first (approved reboot, mode sideload) and check that its recovery accepts ADB on the network')
            adb.run('sideload',str(image),timeout=1800)
            result={'status':'passed','approval':approval,'image':image.name,'image_sha256':digest,
                    'limits':['The device verifies and installs the package itself; read info after it restarts to confirm the new build.']}
        elif state!='device':raise UserError('The device is in '+state+' mode: this command needs it running normally')
        elif command=='info':
            info=properties(adb);info['packages']=len(packages(adb));info['third_party_packages']=len(packages(adb,'-3'))
            (output/'device.json').write_text(json.dumps(info,indent=2))
            result={'status':'passed','device':info,'files':['device.json','adb.log'],'limits':['Read only: nothing was changed on the device.']}
        elif command=='packages':
            listing={'all':packages(adb),'third_party':packages(adb,'-3'),'disabled':packages(adb,'-d')}
            (output/'packages.json').write_text(json.dumps(listing,indent=2))
            result={'status':'passed','packages':len(listing['all']),'third_party':len(listing['third_party']),'disabled':len(listing['disabled']),
                    'files':['packages.json'],'limits':['Read only: nothing was changed on the device.']}
        elif command=='logcat':
            record=Recorder(output,20000);seconds=args.get('seconds',10)
            process=subprocess.Popen(['adb','-s',adb.serial,'logcat','-v','time'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=adb.env)
            deadline=time.monotonic()+seconds
            try:
                while time.monotonic()<deadline and record.rows<20000:
                    ready,_,_=select.select([process.stdout],[],[],0.5)
                    if ready:
                        line=process.stdout.readline()
                        if not line:break
                        record.add({'source':'logcat','value':text(line.rstrip(b'\r\n'))})
            finally:process.kill()
            summary=record.close(seconds)
            result={'status':'passed','records':summary['records'],'files':['telemetry.jsonl','telemetry.csv','summary.json'],'limits':['Read only: logs may contain personal data; keep them in the task.']}
        elif command=='install':
            before=set(packages(adb))
            adb.run('install','-r',str(image),timeout=900)
            added=sorted(set(packages(adb))-before)
            result={'status':'passed','approval':approval,'apk':image.name,'apk_sha256':digest,'new_packages':added,
                    'limits':['Installed or updated; open the app on the device to check it works.']}
        elif command in ('uninstall','disable','enable'):
            argv={'uninstall':['pm','uninstall','--user','0',package],'disable':['pm','disable-user','--user','0',package],'enable':['pm','enable',package]}[command]
            adb.run('shell',*argv)
            present=package in packages(adb);disabled=package in packages(adb,'-d')
            ok={'uninstall':not present,'disable':disabled,'enable':present and not disabled}[command]
            result={'status':'passed' if ok else 'failed','approval':approval,'package':package,'installed_for_user':present,'disabled':disabled,
                    'limits':['Removed only for the user: restore with "cmd package install-existing '+package+'".' if command=='uninstall' else 'Reversible from the same device.']}
        else:
            mode=args.get('mode','system')
            adb.run('reboot',*([] if mode=='system' else [mode]),check=False)
            result={'status':'passed','approval':approval,'mode':mode,'limits':['The device restarts; connect again when it is back.']}
    (output/'android.json').write_text(json.dumps({'at':now(),'command':command,**result},indent=2,ensure_ascii=False))
    return result


# --- Vehicle diagnostics (OBD-II, ELM327) -----------------------------------------------------

def obd_port(cfg):
    if cfg.get('protocol')=='tcp':return f"socket://{cfg['host']}:{cfg['port']}"
    return cfg['url']


def obd_value(response):
    if response is None or response.is_null():return None
    value=response.value
    if hasattr(value,'magnitude'):return {'value':float(value.magnitude),'unit':str(value.units)}
    if isinstance(value,(list,tuple)):return [list(v) if isinstance(v,tuple) else str(v) for v in value]
    return value if isinstance(value,(int,float,str,bool)) else str(value)


def vehicle(cfg,args,output):
    import obd
    command=args['command']
    approval=approved(cfg,'clear_codes') if command=='clear_codes' else None
    connection=obd.OBD(obd_port(cfg),baudrate=cfg.get('baud'),fast=False,timeout=5)
    try:
        if not connection.is_connected():
            raise UserError('OBD adapter or vehicle not responding ('+str(connection.status())+'): ignition on, adapter paired and the right port')
        info={'status':str(connection.status()),'protocol':connection.protocol_name()}
        for name in ('ELM_VERSION','ELM_VOLTAGE','VIN'):
            if hasattr(obd.commands,name):info[name.lower()]=obd_value(connection.query(getattr(obd.commands,name),force=True))
        supported=sorted(c.name for c in connection.supported_commands)
        if command=='info':
            info['supported']=supported
            (output/'vehicle.json').write_text(json.dumps(info,indent=2,default=str))
            return {'status':'passed','vehicle':{k:v for k,v in info.items() if k!='supported'},'supported_count':len(supported),'files':['vehicle.json'],
                    'limits':['Read only. Manufacturer-specific data (body, ABS, airbags) is outside standard OBD-II.']}
        if command=='codes':
            codes={'stored':obd_value(connection.query(obd.commands.GET_DTC)),
                   'pending':obd_value(connection.query(obd.commands.FREEZE_DTC)) if hasattr(obd.commands,'FREEZE_DTC') else None,
                   'monitors':obd_value(connection.query(obd.commands.STATUS)) if hasattr(obd.commands,'STATUS') else None}
            (output/'codes.json').write_text(json.dumps({'at':now(),**info,**codes},indent=2,default=str))
            stored=codes['stored'] or []
            return {'status':'passed','stored_codes':stored,'files':['codes.json'],
                    'limits':['Read only. A code names the system and symptom, not the faulty part: a mechanic confirms the cause.']}
        if command=='clear_codes':
            before=obd_value(connection.query(obd.commands.GET_DTC))
            connection.query(obd.commands.CLEAR_DTC,force=True)
            after=obd_value(connection.query(obd.commands.GET_DTC))
            (output/'cleared.json').write_text(json.dumps({'at':now(),'approval':approval,'before':before,'after':after},indent=2,default=str))
            return {'status':'passed','approval':approval,'codes_before':before,'codes_after':after,'files':['cleared.json'],
                    'limits':['Clearing also resets readiness monitors: the vehicle may fail an inspection until it has driven enough. Codes come back if the fault persists.']}
        wanted=args.get('pids') or ['RPM','SPEED','COOLANT_TEMP','ENGINE_LOAD','THROTTLE_POS','INTAKE_TEMP']
        unknown=[p for p in wanted if not re.fullmatch(r'[A-Z0-9_]{2,40}',p) or not hasattr(obd.commands,p)]
        if unknown:raise UserError('Unknown OBD commands: '+', '.join(unknown[:10]))
        record=Recorder(output,100000);seconds=args.get('seconds',30);interval=args.get('interval_seconds',1.0)
        deadline=time.monotonic()+seconds;started=time.monotonic()
        while time.monotonic()<deadline:
            values={}
            for name in wanted:
                value=obd_value(connection.query(getattr(obd.commands,name)))
                if isinstance(value,dict):values[name]=value['value']
                elif value is not None:values[name]=value
            record.add({'source':'obd','value':values})
            time.sleep(interval)
        summary=record.close(round(time.monotonic()-started,2),{'vehicle':info,'pids':wanted})
        return {'status':'passed' if summary['records'] else 'no_data','records':summary['records'],'numeric_fields':list(summary['numeric_fields']),
                'files':['telemetry.jsonl','telemetry.csv','summary.json'],'limits':['Read only. Values the vehicle does not support stay empty.']}
    finally:
        connection.close()


# --- Tuya / Smart Life local protocol -------------------------------------------------------

def tuya_values(raw):
    """The data points to set, as a JSON object {"1": true, "3": 25}: DP numbers to values."""
    try:values=json.loads(raw or '')
    except ValueError as error:raise UserError('Tuya set needs a JSON object of data points, for example {"1": true}') from error
    if not isinstance(values,dict) or not values or len(values)>20:raise UserError('Tuya set needs 1-20 data points, for example {"1": true}')
    for key,value in values.items():
        if not re.fullmatch(r'[0-9]{1,3}',str(key)):raise UserError('Tuya data point numbers are 1-999: '+str(key)[:20])
        if not isinstance(value,(bool,int,float,str)) or isinstance(value,str) and len(value)>255:raise UserError('Tuya values are booleans, numbers or short text')
    return {str(k):v for k,v in values.items()}


def tuya_device(cfg):
    import tinytuya
    device=tinytuya.Device(cfg['username'],cfg['host'],cfg['password'],version=float(cfg.get('version') or 3.3),connection_timeout=5)
    device.set_socketRetryLimit(2);device.set_socketTimeout(5)
    return device


def tuya_status(device):
    status=device.status()
    if not isinstance(status,dict) or 'Error' in status or 'dps' not in status:
        detail=status.get('Error') if isinstance(status,dict) else str(status)
        raise UserError('The Tuya device did not answer ('+str(detail)[:200]+'): check the IP address, the device ID, the local key '
                        'and the protocol version (3.3, 3.4 or 3.5); the Smart Life app on the same network can also hold the connection')
    return status['dps']


def tuya(cfg,args,output):
    command=args['command']
    device=tuya_device(cfg)
    try:
        if command=='status':
            dps=tuya_status(device)
            (output/'status.json').write_text(json.dumps({'at':now(),'version':cfg.get('version'),'dps':dps},indent=2,default=str))
            return {'status':'passed','dps':dps,'files':['status.json'],
                    'limits':['Read only. Data point meanings depend on the product: the Tuya developer platform lists them for each device.']}
        approval=approved(cfg,'send',fingerprint=command_fingerprint(args))
        values=tuya_values(args.get('payload'))
        before=tuya_status(device)
        answer=device.set_multiple_values(values)
        if isinstance(answer,dict) and 'Error' in answer:raise UserError('The Tuya device refused the change: '+str(answer['Error'])[:200])
        time.sleep(1)
        after=tuya_status(device)
        (output/'set.json').write_text(json.dumps({'at':now(),'approval':approval,'values':values,'before':before,'after':after},indent=2,default=str))
        applied=all(str(after.get(k))==str(v) for k,v in values.items())
        return {'status':'passed' if applied else 'not_confirmed','approval':approval,'values':values,'before':before,'after':after,'files':['set.json'],
                'limits':['The device state after the change is read back; a value it does not report stays unconfirmed.']}
    finally:
        try:device.close()
        except Exception:pass


# --- Matter (through the RigHaven Matter controller) --------------------------------------------

MATTER_COMMAND_FIELDS=('endpoint','cluster','command','args')


def matter_call(cfg,command,args,timeout=60):
    from websockets.sync.client import connect
    deadline=time.monotonic()+timeout
    try:
        with connect(cfg['url'],open_timeout=5,close_timeout=2,max_size=16*1024*1024) as socket:
            socket.recv(timeout=10)
            identifier=hashlib.sha256(os.urandom(16)).hexdigest()[:16]
            socket.send(json.dumps({'message_id':identifier,'command':command,'args':args}))
            while time.monotonic()<deadline:
                message=json.loads(socket.recv(timeout=max(1,deadline-time.monotonic())))
                if message.get('message_id')!=identifier:continue
                if 'error_code' in message:raise UserError('Matter: '+str(message.get('details') or message['error_code'])[:300])
                return message.get('result')
    except (OSError,TimeoutError) as error:
        raise UserError('The RigHaven Matter controller is not reachable ('+str(error)[:200]+'): start it on the PC (RigHaven.exe matter enable)') from error
    raise UserError('The Matter controller did not answer in time')


def matter_request(raw):
    """{"endpoint": 1, "cluster": 6, "command": "On", "args": {}}: one cluster command."""
    try:value=json.loads(raw or '')
    except ValueError as error:raise UserError('Matter command needs a JSON object such as {"endpoint": 1, "cluster": 6, "command": "On"}') from error
    if not isinstance(value,dict) or set(value)-set(MATTER_COMMAND_FIELDS):raise UserError('Matter command fields: endpoint, cluster, command, args')
    if type(value.get('endpoint')) is not int or type(value.get('cluster')) is not int or not re.fullmatch(r'[A-Za-z][A-Za-z0-9]{0,63}',str(value.get('command',''))):
        raise UserError('Matter command needs an integer endpoint and cluster and a command name such as On, Off, MoveToLevel')
    if not isinstance(value.get('args',{}),dict):raise UserError('Matter command args must be an object')
    return value


def matter(cfg,args,output):
    command=args['command'];node=cfg['node_id']
    nodes=matter_call(cfg,'get_nodes',{})
    current=next((n for n in nodes or [] if isinstance(n,dict) and n.get('node_id')==node),None)
    if current is None:raise UserError('Matter node '+str(node)+' is not known to the controller any more: share the device again')
    attributes=current.get('attributes') or {}
    if command=='status':
        (output/'node.json').write_text(json.dumps({'at':now(),'node_id':node,'available':current.get('available'),'attributes':attributes},indent=2,default=str))
        return {'status':'passed','node_id':node,'available':bool(current.get('available')),'attributes':len(attributes),'files':['node.json'],
                'limits':['Read only. Attributes are named endpoint/cluster/attribute, for example 1/6/0 is On/Off of endpoint 1.']}
    if command=='read':
        path=args.get('attribute_path','')
        if not re.fullmatch(r'[0-9]{1,5}/[0-9]{1,6}/[0-9]{1,6}',path):raise UserError('attribute_path is endpoint/cluster/attribute, for example 1/6/0')
        value=matter_call(cfg,'read_attribute',{'node_id':node,'attribute_path':path})
        (output/'attribute.json').write_text(json.dumps({'at':now(),'node_id':node,'path':path,'value':value},indent=2,default=str))
        return {'status':'passed','path':path,'value':value,'files':['attribute.json'],'limits':['Read only.']}
    approval=approved(cfg,'send',fingerprint=command_fingerprint(args))
    request=matter_request(args.get('payload'))
    before={k:v for k,v in attributes.items() if k.startswith(f"{request['endpoint']}/{request['cluster']}/")}
    matter_call(cfg,'device_command',{'node_id':node,'endpoint_id':request['endpoint'],'cluster_id':request['cluster'],
                                      'command_name':request['command'],'payload':request.get('args',{})})
    time.sleep(1)
    after_nodes=matter_call(cfg,'get_nodes',{})
    after_node=next((n for n in after_nodes or [] if isinstance(n,dict) and n.get('node_id')==node),{})
    after={k:v for k,v in (after_node.get('attributes') or {}).items() if k.startswith(f"{request['endpoint']}/{request['cluster']}/")}
    (output/'command.json').write_text(json.dumps({'at':now(),'approval':approval,'node_id':node,'request':request,'before':before,'after':after},indent=2,default=str))
    return {'status':'passed','approval':approval,'request':request,'before':before,'after':after,'files':['command.json'],
            'limits':['The cluster attributes are read back after the command; some devices report changes a few seconds later.']}


def main(path):
    request=json.loads(Path(path).read_text())
    output=Path(request['output']);args=request['args'];action=request['action']
    if action=='simulate':result=simulate(args,request['input'],output)
    else:
        cfg=json.loads(Path(request['connection_file']).read_text())
        command=args.get('command')
        writing=action in ('send','inspect','flash') or (action=='android' and command in ('install','uninstall','disable','enable','reboot','sideload')) or (action=='obd' and command=='clear_codes') or (action=='tuya' and command=='set') or (action=='matter' and command=='command')
        if writing and cfg.get('write_enabled') is not True:
            raise UserError('Writing to this device is not allowed: the owner must enable writing on the connection and allow it for this task')
        if action=='capture':result=capture(cfg,args,output)
        elif action=='send':result=send(cfg,args,output)
        elif action=='inspect':result=inspect(cfg,args,output)
        elif action=='flash':result=flash(cfg,args,request['input'],output)
        elif action=='android':result=android(cfg,args,request.get('input'),output)
        elif action=='obd':result=vehicle(cfg,args,output)
        elif action=='tuya':result=tuya(cfg,args,output)
        elif action=='matter':result=matter(cfg,args,output)
        else:raise UserError('Unknown operation: '+action)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    try:main(sys.argv[1])
    except UserError as error:
        print(str(error),file=sys.stderr);sys.exit(3)
