#!/usr/bin/env python3
"""netscan toolkit job, run in the netscan environment (nmap and testssl.sh from Debian, defusedxml).

Only the networks of the task connection are scanned; the container has no raw-socket
capability, so nmap runs unprivileged (TCP connect probes). Vulnerability scans run only with
the owner's approval of the exact targets and profile, delivered once in the connection file.
Exit code 3 is a user error.
"""
import csv,datetime,hashlib,ipaddress,json,re,shutil,subprocess,sys
from pathlib import Path

PORTS={'top100':['--top-ports','100'],'top1000':['--top-ports','1000'],'all-tcp':['-p-'],
       'common':['-p','21,22,23,25,53,80,110,139,143,443,445,993,995,1433,1521,1883,3306,3389,5432,5900,8080,8443,8883'],
       'iot':['-p','22,23,80,443,502,554,1883,1900,5000,5353,5555,5683,8000,8080,8443,8883,9100,20000,35000,47808']}
TLS_PORTS={443,465,636,853,993,995,1443,3389,5061,6443,8443,8883,9443}
CVE=re.compile(r'CVE-\d{4}-\d{4,7}')
CVSS=re.compile(r'\b(\d{1,2}\.\d)\b')
PACING=['-T3','--max-rate','200','--host-timeout','5m','--max-retries','2']


class UserError(ValueError):pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def scope_fingerprint(targets,profile):
    """Same function as righaven.device_changes.scope_fingerprint."""
    value={'targets':sorted(str(ipaddress.ip_network(str(t),strict=False)) for t in targets),'profile':profile}
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def scope(cfg,args):
    allowed=[ipaddress.ip_network(r) for r in cfg.get('ranges',[])]
    if not allowed:raise UserError('The connection lists no authorized network')
    targets=[ipaddress.ip_network(str(t),strict=False) for t in (args.get('targets') or cfg['ranges'])]
    for target in targets:
        if not any(target.version==a.version and target.subnet_of(a) for a in allowed):
            raise UserError('Target outside the networks authorized by the owner: '+str(target))
    return [str(t) for t in targets],[str(ipaddress.ip_network(e,strict=False)) for e in cfg.get('exclude',[])]


def approved(cfg,targets,profile):
    fingerprint=scope_fingerprint(targets,profile)
    for approval in cfg.get('approvals') or []:
        if approval.get('action')=='scan' and approval.get('fingerprint')==fingerprint:return approval['id']
    raise UserError('This vulnerability scan needs the owner approval of these targets and profile: ask with harness_device_change '
                    '(action scan), then run it exactly as approved')


def nmap(arguments,targets,exclude,output,name,timeout=1200):
    if not shutil.which('nmap'):raise RuntimeError('nmap is not installed in this environment: add the netscan tool to the environment')
    xml=output/(name+'.xml')
    argv=['nmap','--unprivileged',*PACING,*arguments,'-oX',str(xml),*(['--exclude',','.join(exclude)] if exclude else []),*targets]
    done=subprocess.run(argv,capture_output=True,text=True,errors='replace',timeout=timeout)
    (output/(name+'.log')).write_text('$ '+' '.join(argv)+'\n'+done.stdout+done.stderr)
    if done.returncode or not xml.is_file():raise UserError('nmap failed: '+(done.stderr or done.stdout).strip()[-800:])
    return parse(xml)


def parse(xml):
    from defusedxml import ElementTree
    root=ElementTree.parse(str(xml)).getroot()
    hosts=[]
    for host in root.findall('host'):
        status=host.find('status')
        if status is not None and status.get('state')!='up':continue
        address=next((a.get('addr') for a in host.findall('address') if a.get('addrtype') in ('ipv4','ipv6')),None)
        if not address:continue
        names=[h.get('name') for h in host.findall('hostnames/hostname') if h.get('name')]
        ports=[]
        for port in host.findall('ports/port'):
            state=port.find('state')
            if state is None or state.get('state')!='open':continue
            service=port.find('service')
            scripts=[{'id':s.get('id'),'output':(s.get('output') or '')[:4000]} for s in port.findall('script')]
            ports.append({'port':int(port.get('portid')),'protocol':port.get('protocol'),
                          'service':service.get('name','') if service is not None else '',
                          'product':' '.join(x for x in ((service.get('product') or ''),(service.get('version') or '')) if x).strip() if service is not None else '',
                          'tunnel':service.get('tunnel','') if service is not None else '','scripts':scripts})
        hosts.append({'address':address,'hostname':names[0] if names else '','ports':ports})
    return sorted(hosts,key=lambda h:ipaddress.ip_address(h['address']))


def save_inventory(hosts,output,ranges):
    (output/'hosts.json').write_text(json.dumps({'at':now(),'networks':ranges,'hosts':hosts},indent=2))
    with (output/'inventory.csv').open('w',newline='') as stream:
        writer=csv.writer(stream);writer.writerow(['address','hostname','port','protocol','service','product'])
        for host in hosts:
            for port in host['ports'] or [{'port':'','protocol':'','service':'','product':''}]:
                writer.writerow([host['address'],host['hostname'],port['port'],port['protocol'],port['service'],port['product']])
    lines=['graph LR']
    for index,network in enumerate(ranges):
        lines.append(f'  N{index}["{network}"]')
        net=ipaddress.ip_network(network)
        for host in hosts:
            if ipaddress.ip_address(host['address']) in net:
                node='H'+re.sub(r'[^0-9a-zA-Z]','_',host['address'])
                services=', '.join(f"{p['port']}/{p['service'] or '?'}" for p in host['ports'][:8])
                label=host['address']+(' '+host['hostname'] if host['hostname'] else '')+('<br/>'+services if services else '')
                lines.append(f'  N{index} --- {node}["{label}"]')
    (output/'network-map.mmd').write_text('\n'.join(lines)+'\n')


def discover(cfg,args,output):
    targets,exclude=scope(cfg,args)
    hosts=nmap(['-sn','-PS21,22,80,135,139,443,445,502,1883,3389,5555,8080,8443'],targets,exclude,output,'discover')
    save_inventory(hosts,output,targets)
    return {'status':'passed','hosts':len(hosts),'addresses':[h['address'] for h in hosts][:200],'files':['hosts.json','inventory.csv','network-map.mmd','discover.xml'],
            'limits':['Read only. Unprivileged TCP probes: hosts that answer on none of the probed ports, or firewalled ones, are not listed.']}


def services(cfg,args,output):
    targets,exclude=scope(cfg,args)
    hosts=nmap(['-sT','-Pn','-sV','--version-light',*PORTS[args.get('ports','top100')]],targets,exclude,output,'services',timeout=1300)
    hosts=[h for h in hosts if h['ports']]
    save_inventory(hosts,output,targets)
    (output/'services.json').write_text(json.dumps(hosts,indent=2))
    exposed=[f"{h['address']}:{p['port']}/{p['service']}" for h in hosts for p in h['ports'] if p['service'] in ('telnet','ftp','microsoft-ds','netbios-ssn','ms-wbt-server','vnc','mqtt','modbus','http')]
    return {'status':'passed','hosts_with_open_ports':len(hosts),'open_ports':sum(len(h['ports']) for h in hosts),'review_first':exposed[:50],
            'files':['services.json','hosts.json','inventory.csv','network-map.mmd','services.xml'],
            'limits':['Read only. Version detection is light: products and versions can be missing or approximate.']}


def severity(text):
    scores=[float(x) for x in CVSS.findall(text) if 0<float(x)<=10]
    score=max(scores) if scores else None
    if score is None:return ('high' if 'VULNERABLE' in text else 'info'),None
    return ('critical' if score>=9 else 'high' if score>=7 else 'medium' if score>=4 else 'low'),score


def vulnerabilities(cfg,args,output):
    profile=args['profile'];targets,exclude=scope(cfg,args)
    approval=approved(cfg,targets,profile)
    findings=[]
    if profile=='safe':
        hosts=nmap(['-sT','-Pn','-sV','--version-light','--script','vuln and safe',*PORTS[args.get('ports','top100')]],targets,exclude,output,'vulnerabilities',timeout=1300)
        for host in hosts:
            for port in host['ports']:
                for script in port['scripts']:
                    text=script['output']
                    cves=sorted(set(CVE.findall(text)))
                    if 'VULNERABLE' not in text and not cves:continue
                    level,score=severity(text)
                    findings.append({'host':host['address'],'port':port['port'],'service':port['service'],'product':port['product'],'check':script['id'],
                                     'severity':level,'cvss':score,'cves':cves[:30],'evidence':text[:1500]})
    else:
        tester=shutil.which('testssl') or shutil.which('testssl.sh')
        if not tester:raise RuntimeError('testssl.sh is not installed in this environment: add the netscan tool to the environment')
        hosts=nmap(['-sT','-Pn','-p',','.join(map(str,sorted(TLS_PORTS)))],targets,exclude,output,'tls-ports')
        endpoints=[f"{h['address']}:{p['port']}" for h in hosts for p in h['ports']][:20]
        for index,endpoint in enumerate(endpoints):
            report=output/f'testssl-{index}.json'
            done=subprocess.run([tester,'--quiet','--warnings','off','--color','0','--severity','LOW','--jsonfile',str(report),endpoint],
                                capture_output=True,text=True,errors='replace',timeout=600)
            (output/f'testssl-{index}.log').write_text(done.stdout[-20000:]+done.stderr[-4000:])
            if not report.is_file():continue
            for item in json.loads(report.read_text() or '[]'):
                level=str(item.get('severity','')).lower()
                if level in ('low','medium','high','critical'):
                    findings.append({'host':endpoint.rsplit(':',1)[0],'port':int(endpoint.rsplit(':',1)[1]),'service':'tls','product':'','check':item.get('id',''),
                                     'severity':level,'cvss':None,'cves':sorted(set(CVE.findall(str(item.get('cve','')))))[:30],'evidence':str(item.get('finding',''))[:1500]})
    order={'critical':0,'high':1,'medium':2,'low':3,'info':4}
    findings.sort(key=lambda f:(order.get(f['severity'],5),f['host'],f['port']))
    (output/'findings.json').write_text(json.dumps({'at':now(),'approval':approval,'profile':profile,'targets':targets,'findings':findings},indent=2))
    counts={k:sum(1 for f in findings if f['severity']==k) for k in order}
    lines=[f'# Vulnerability scan ({profile})','',f'Targets: {", ".join(targets)}  ',f'Approved change: {approval}  ',f'At: {now()}','',
           '| Severity | Count |','|---|---|',*[f'| {k} | {v} |' for k,v in counts.items()],'','## Findings','']
    for f in findings[:200]:
        lines+= [f"### {f['severity'].upper()} · {f['host']}:{f['port']} · {f['check']}",'',
                 (f"Service: {f['service']} {f['product']}".strip()),'',('CVE: '+', '.join(f['cves'])) if f['cves'] else '','','```',f['evidence'][:800],'```','']
    lines+=['## Limits','','Automated checks find known issues only; absence of findings is not proof of security. Confirm each finding before fixing and re-scan after.']
    (output/'report.md').write_text('\n'.join(lines))
    return {'status':'passed','approval':approval,'findings':len(findings),'by_severity':counts,'top':[f"{f['severity']} {f['host']}:{f['port']} {f['check']}" for f in findings[:10]],
            'files':['findings.json','report.md'],
            'limits':['Non-intrusive checks only (nmap scripts marked safe, or TLS configuration). Findings need confirmation; no exploitation was attempted.']}


def main(path):
    request=json.loads(Path(path).read_text())
    output=Path(request['output']);args=request['args'];action=request['action']
    cfg=json.loads(Path(request['connection_file']).read_text())
    if cfg.get('kind')!='network':raise UserError('Not a network connection')
    result={'discover':discover,'services':services,'vulnerabilities':vulnerabilities}[action](cfg,args,output)
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    try:main(sys.argv[1])
    except UserError as error:
        print(str(error),file=sys.stderr);sys.exit(3)
