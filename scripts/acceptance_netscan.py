"""Offline fixture of the netscan toolkit, with known results on the loopback network.

Mapping finds a local HTTP service and respects the excluded address; a target outside
the authorized networks is refused; a vulnerability scan is refused without the owner's
approval of its exact scope and runs once approved.
"""
import http.server,json,subprocess,sys,threading
from pathlib import Path
CONNECTIONS=Path('/run/righaven/connections')


def call(c,operation,allowed=(0,),**args):
    p=subprocess.run(['netscan-cli','call',operation,json.dumps(args)],capture_output=True,text=True,timeout=900)
    c.commands.append({'argv':['netscan-cli','call',operation,args],'returncode':p.returncode,'stdout':p.stdout[-3000:],'stderr':p.stderr[-2000:]})
    if p.returncode not in allowed:raise RuntimeError('netscan.'+operation+': '+(p.stderr or p.stdout)[-2000:])
    return json.loads(p.stdout) if p.returncode==0 else p.stderr


def netscan(c):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    server=http.server.ThreadingHTTPServer(('127.0.0.1',8080),Quiet)
    server.handle_error=lambda *args:None  # probes close connections early
    threading.Thread(target=server.serve_forever,daemon=True).start()
    created=not CONNECTIONS.exists()
    try:
        CONNECTIONS.mkdir(parents=True,exist_ok=True)
        sys.path.insert(0,str(Path(__file__).resolve().parent))
        from netscan_job import scope_fingerprint
        base={'kind':'network','ranges':['127.0.0.0/30'],'exclude':['127.0.0.2'],'write_enabled':True}
        (CONNECTIONS/'acceptance-lan.json').write_text(json.dumps(base))
        (CONNECTIONS/'acceptance-approved.json').write_text(json.dumps({**base,'approvals':[{'id':'acceptance','action':'scan','fingerprint':scope_fingerprint(['127.0.0.1'],'safe')}]}))
        found=call(c,'discover',connection='acceptance-lan',output=str(c.root/'Discover'))
        c.check('Mapping finds the local host and skips the excluded address','127.0.0.1' in found['addresses'] and '127.0.0.2' not in found['addresses'],found['addresses'])
        listed=call(c,'services',connection='acceptance-lan',targets=['127.0.0.1'],ports='common',output=str(c.root/'Services'))
        rows=(c.root/'Services/inventory.csv').read_text()
        c.check('Service listing identifies the local HTTP server','127.0.0.1,' in rows and ',8080,tcp,http' in rows,rows[-300:])
        outside=call(c,'services',allowed=(1,),connection='acceptance-lan',targets=['10.0.0.1'],output=str(c.root/'Outside'))
        c.check('A target outside the authorized networks is refused','outside the networks' in outside,outside[-200:])
        refused=call(c,'vulnerabilities',allowed=(1,),connection='acceptance-lan',targets=['127.0.0.1'],profile='safe',ports='common',output=str(c.root/'Refused'))
        c.check('A vulnerability scan without the owner approval is refused','harness_device_change' in refused,refused[-200:])
        scanned=call(c,'vulnerabilities',connection='acceptance-approved',targets=['127.0.0.1'],profile='safe',ports='common',output=str(c.root/'Scan'))
        c.check('The approved scan runs and writes its report',scanned['approval']=='acceptance' and (c.root/'Scan/report.md').is_file(),scanned['by_severity'])
        c.check('Network map is written for the delivery',(c.root/'Services/network-map.mmd').read_text().startswith('graph LR'),'mermaid')
    finally:
        server.shutdown()
        for name in ('acceptance-lan','acceptance-approved'):(CONNECTIONS/(name+'.json')).unlink(missing_ok=True)
        if created:
            try:CONNECTIONS.rmdir();CONNECTIONS.parent.rmdir()
            except OSError:pass


CASES={'netscan':netscan}
