"""Operations of the iot toolkit: devices and interfaces reached only through task connections."""
try:from .schema_types import tool,STRING
except ImportError:from schema_types import tool,STRING

BOOL={'type':'boolean'}
ADDRESS={'type':'integer','minimum':0,'maximum':65535}


def op(name,description,fields,required):
    return tool('iot',name,description,{'output':STRING,**fields},['output',*required])


TOOLS={'iot':[
 op('capture','Read an assigned device connection for a bounded time without writing to it: MQTT subscription, Modbus TCP register polling, HTTP polling, a serial port (local or RFC 2217) or a raw TCP stream. Saves telemetry.jsonl, telemetry.csv and summary.json with counts, rates, gaps and value ranges.',
    {'connection':STRING,'seconds':{'type':'integer','minimum':1,'maximum':600},'max_records':{'type':'integer','minimum':1,'maximum':100000},
     'interval_seconds':{'type':'number','minimum':0.2,'maximum':60},'register_kind':{'type':'string','enum':['holding','input','coil','discrete']},
     'register_address':ADDRESS,'register_count':{'type':'integer','minimum':1,'maximum':125}},['connection']),
 op('send','Write to an assigned device connection the owner enabled for writing in this task: MQTT publish, Modbus TCP register or coil write, HTTP POST/PUT, serial or TCP bytes. Optionally reads the reply for a few seconds. Every write is recorded in the receipt.',
    {'connection':STRING,'payload':STRING,'encoding':{'type':'string','enum':['text','hex','json']},'topic':STRING,'retain':BOOL,
     'method':{'type':'string','enum':['POST','PUT']},'address':ADDRESS,'values':{'type':'array','items':{'type':'integer','minimum':0,'maximum':65535},'minItems':1,'maxItems':50},
     'coil':BOOL,'reply_seconds':{'type':'integer','minimum':0,'maximum':30},
     'reply_until':{'type':'string','maxLength':16,'description':'End of the reply (a prompt such as > or OK; hex bytes with encoding hex): reading stops there instead of waiting reply_seconds'},
     'reply_topic':{'type':'string','maxLength':200,'description':'MQTT: topic or filter where the device answers (for example stat/plug/#), subscribed before publishing in the same connection; only topics inside the connection topic filter are recorded'}},['connection']),
 op('simulate','Generate deterministic synthetic telemetry from a scenario JSON (device groups, sensors with baseline, daily profile, noise, drift, failures and events) to test hypotheses before hardware exists: JSON Lines, CSV and per-device summaries. Data is synthetic.',
    {'input':STRING,'seed':{'type':'integer','minimum':0,'maximum':2147483647}},['input']),
 op('inspect','Identify an ESP board on an assigned serial connection with esptool (chip, MAC, flash size). The board is reset into its bootloader, so the owner must enable writing for this task.',
    {'connection':STRING,'chip':{'type':'string','enum':['auto','esp32','esp32s2','esp32s3','esp32c3','esp32c6','esp32h2','esp8266']}},['connection']),
 op('flash','Write a firmware image to an ESP board on an assigned serial connection with esptool, then verify the written flash against the image. Requires write consent for this task; the image digest is recorded.',
    {'connection':STRING,'input':STRING,'offset':{'type':'string','pattern':'^0x[0-9a-fA-F]{1,8}$'},
     'chip':{'type':'string','enum':['auto','esp32','esp32s2','esp32s3','esp32c3','esp32c6','esp32h2','esp8266']},
     'baud':{'type':'integer','enum':[115200,230400,460800,921600]},'erase':BOOL},['connection','input']),
 op('android','Android and Android TV over network debugging (ADB on Wi-Fi). Reads: info (model, Android version, build, security patch, apps), packages, logcat for a few seconds. Writes, each only with the owner approval of that exact change: install an APK, uninstall, disable or enable an app for the user, reboot (system, recovery, bootloader, sideload) and sideload an OTA update when the device is in sideload mode.',
    {'connection':STRING,'command':{'type':'string','enum':['info','packages','logcat','install','uninstall','disable','enable','reboot','sideload']},
     'input':STRING,'package':STRING,'mode':{'type':'string','enum':['system','recovery','bootloader','sideload']},'seconds':{'type':'integer','minimum':1,'maximum':120}},['connection','command']),
 op('obd','Vehicle diagnostics through an OBD-II ELM327 adapter (Bluetooth paired as a serial port, USB, RFC 2217 or Wi-Fi TCP). Reads: info (protocol, voltage, VIN when available, supported PIDs), live values of PIDs for a few seconds, stored and pending trouble codes. Clearing trouble codes is a write and needs the owner approval.',
    {'connection':STRING,'command':{'type':'string','enum':['info','live','codes','clear_codes']},
     'pids':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':20},'seconds':{'type':'integer','minimum':1,'maximum':300},
     'interval_seconds':{'type':'number','minimum':0.2,'maximum':60}},['connection','command']),
    op('tuya','Tuya / Smart Life devices (Wi-Fi plugs, bulbs, IR remotes, sensors) over their local protocol, with the device ID and local key stored in the connection; nothing goes through the Tuya cloud. Reads: status (the data points, DPS, and their values). Writes: set data points given as a JSON object in payload with encoding json, for example {"1": true} to switch on, only with the owner approval of that exact command (harness_device_change send with the same payload and encoding); the state is read back.',
    {'connection':STRING,'command':{'type':'string','enum':['status','set']},'payload':STRING,'encoding':{'type':'string','enum':['json']}},['connection','command']),
    op('matter','Matter devices joined to the RigHaven Matter controller (lights, plugs, sensors, thermostats), through a connection created from the Matter devices list. Reads: status (all attributes, named endpoint/cluster/attribute), read one attribute_path such as 1/6/0. Writes: command with payload {"endpoint": 1, "cluster": 6, "command": "On", "args": {}} and encoding json, only with the owner approval of that exact command (harness_device_change send with the same payload and encoding); the cluster attributes are read back.',
    {'connection':STRING,'command':{'type':'string','enum':['status','read','command']},'attribute_path':{'type':'string','pattern':'^[0-9]{1,5}/[0-9]{1,6}/[0-9]{1,6}$'},
     'payload':STRING,'encoding':{'type':'string','enum':['json']}},['connection','command']),
]}
