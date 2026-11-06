"""Operations of the netscan toolkit: map and assess only the networks a task connection authorizes."""
try:from .schema_types import tool,STRING
except ImportError:from schema_types import tool,STRING

TARGETS={'type':'array','items':{'type':'string'},'minItems':1,'maxItems':50}
PORTS={'type':'string','enum':['top100','top1000','common','iot','all-tcp']}


def op(name,description,fields,required):
    return tool('netscan',name,description,{'output':STRING,'connection':STRING,**fields},['output','connection',*required])


TOOLS={'netscan':[
 op('discover','Find the active hosts of the authorized networks with unprivileged TCP probes (nmap). Saves hosts.json, inventory.csv and a Mermaid network map. Read only: no approval needed.',
    {'targets':TARGETS},[]),
 op('services','List open ports and identify services and versions on the authorized networks or a subset (nmap connect scan with light version detection). Saves services.json, inventory.csv and the network map. Read only: no approval needed.',
    {'targets':TARGETS,'ports':PORTS},[]),
 op('vulnerabilities','Check the authorized networks for known vulnerabilities, only with the owner approval of this exact scope and profile: safe runs nmap vulnerability scripts marked safe on identified services; tls checks TLS configuration with testssl.sh. Saves findings.json and report.md with severity and evidence.',
    {'targets':TARGETS,'profile':{'type':'string','enum':['safe','tls']},'ports':PORTS},['profile']),
]}
