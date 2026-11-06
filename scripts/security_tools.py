"""Pinned native scanners. No target code, delivered script or remote rule is executed."""
import hashlib,json,os,shutil
from pathlib import Path


def version(app,cli):
    import subprocess
    value=subprocess.run([str(cli.INSTALL/'apps'/app/'bin'/app),'--version'],capture_output=True,text=True,check=True,timeout=60)
    print(value.stdout+value.stderr)


def invoke(app,action,args,cli):
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True);output.mkdir(parents=True)
    source=cli.scoped(args['input'],directory=True) if 'input' in args else None
    binary=cli.INSTALL/'apps'/app/'bin'/app
    report=output/'report.json'
    root=cli.scoped(os.environ.get('RIGHAVEN_OUTPUT_DIR',str(output.parent)),exists=False,directory=True)
    argv=[binary]
    identity={'tool':app,'version':next(a['version'] for a in json.loads((cli.INSTALL/'installed.json').read_text()) if a['id']==app),'operation':action,'input':str(source) if source else None}
    if app=='opengrep':
        rules=cli.scoped(args['rules'])
        if rules.stat().st_size>200000:raise ValueError('Rule file too large')
        if rules.suffix.lower() not in ('.yaml','.yml'):raise ValueError('Use a local YAML rule file')
        saved=output/'rules.yaml';shutil.copyfile(rules,saved)
        identity['rules_sha256']=hashlib.sha256(saved.read_bytes()).hexdigest()
        argv += ['--config',saved,'--json','--disable-version-check','--no-git-ignore','--output',report,source]
    elif action=='config':argv+=['config','--skip-check-update','--format','json','--output',report,source]
    elif action=='sbom':argv+=['fs','--format','cyclonedx','--output',report,source]
    elif action=='database_update':
        argv+=['image','--download-db-only','--cache-dir',output]
    elif action=='vulnerabilities':
        database=cli.scoped(args['database'],directory=True)
        metadata=database/'db/metadata.json'
        if (not metadata.resolve().is_relative_to(database.resolve()) or not (database/'db/trivy.db').resolve().is_relative_to(database.resolve())
                or metadata.is_symlink() or not metadata.is_file() or metadata.stat().st_size>200000 or not (database/'db/trivy.db').is_file()):
            raise ValueError('Vulnerability database missing; use trivy.database_update and preserve metadata')
        identity['database']=json.loads(metadata.read_text())
        identity['database_metadata_sha256']=hashlib.sha256(metadata.read_bytes()).hexdigest()
        argv+=['fs','--scanners','vuln','--skip-db-update','--skip-java-db-update','--offline-scan','--cache-dir',database,'--format','json','--output',report,source]
    cli.run(app,argv,root)
    if action=='database_update':
        metadata=output/'db/metadata.json'
        if not metadata.is_file():raise ValueError('Downloaded database has no usable metadata')
        identity['database']=json.loads(metadata.read_text());identity['database_metadata_sha256']=hashlib.sha256(metadata.read_bytes()).hexdigest()
        count=None
    else:
        if report.stat().st_size>32*1024**2:raise ValueError('Report too large; narrow the scan scope')
        value=json.loads(report.read_text())
        if app=='opengrep':
            count=len(value.get('results',[]))
            if value.get('errors'):raise ValueError('Scanner reported parsing or rule errors; inspect report.json')
        elif action=='sbom':count=len(value.get('components',[]))
        else:count=sum(len(r.get('Misconfigurations',[]))+len(r.get('Vulnerabilities',[])) for r in value.get('Results',[]))
    identity.update(count=count,note='Native evidence; findings require triage against the brief. No security guarantee.')
    (output/'scan-recipe.json').write_text(json.dumps(identity,ensure_ascii=False,indent=2))
    return {'status':'passed','output':str(output),'report':str(report) if report.exists() else None,'findings':count,'recipe':str(output/'scan-recipe.json')}
