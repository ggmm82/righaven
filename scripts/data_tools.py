"""Isolated file workflows; credentials never enter receipts or source archives."""
import json,os,re,shutil,subprocess,tempfile
from pathlib import Path
from urllib.parse import urlsplit,unquote

APPS={'usql','schemacrawler','dlt','sqlmesh','sqlglot'}


def secret_config(args,cli,output):
    if args.get('database'):
        source=cli.scoped(args['database'])
        if source.stat().st_size>256*1024**2:raise ValueError('Supply a bounded database snapshot of at most 256 MiB')
        target=output/'Sources'/source.name;shutil.copy2(source,target)
        return {'url':'sqlite:///'+str(target),'jdbc_url':'jdbc:sqlite:'+str(target)},[]
    if args.get('authorized') is not True:raise ValueError('Authorize the read-only data source explicitly and use a read-only database account')
    cfg={}
    if args.get('connection_env'):
        name=args['connection_env']
        if not re.fullmatch(r'RIGHAVEN_DB_[A-Z0-9_]{1,64}',name):raise ValueError('Use a RIGHAVEN_DB_* environment variable')
        value=os.environ.get(name)
        if not value:raise ValueError('The requested connection secret was not supplied to this job')
        cfg={'url':value}
    elif args.get('connection_file'):
        source=cli.scoped(args['connection_file'])
        cfg=json.loads(source.read_text())
    else:return None,[]
    if not isinstance(cfg,dict) or not all(isinstance(v,str) for v in cfg.values()) or not (cfg.get('url') or cfg.get('jdbc_url')):
        raise ValueError('Connection JSON requires url or jdbc_url, with optional username/password. Keep it outside source resources.')
    values=[v for key,v in cfg.items() if key in ('url','jdbc_url','password','username') and v]
    if cfg.get('url'):
        parsed=urlsplit(cfg['url'])
        if parsed.password:values.append(unquote(parsed.password))
    return cfg,values


def usql_url(url):
    # SQLAlchemy driver qualifiers are not part of usql connection schemes.
    scheme,separator,tail=url.partition('://')
    if not separator:raise ValueError('Expected a database connection URL')
    scheme=scheme.split('+',1)[0]
    return {'mssql':'sqlserver','postgres':'postgresql'}.get(scheme,scheme)+separator+tail


def redact(text,values):
    for value in sorted(set(values),key=len,reverse=True):
        if value:text=text.replace(value,'[REDACTED]')
    return text


def run(argv,output,cwd,env,values):
    result=subprocess.run(argv,cwd=cwd,capture_output=True,text=True,timeout=600,env={**os.environ,**env})
    (output/'native-stdout.log').write_text(redact(result.stdout,values))
    (output/'native-stderr.log').write_text(redact(result.stderr,values))
    if result.returncode:raise RuntimeError('Native data operation failed; inspect redacted native-stderr.log')


def invoke(app,action,args,cli):
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    output.mkdir(parents=True);sources=output/'Sources';sources.mkdir();(output/'work').mkdir()
    source=cli.scoped(args['input']) if args.get('input') else None
    if source and source.stat().st_size>256*1024**2:raise ValueError('Use a bounded extract for input files larger than 256 MiB')
    original=cli.digest(source) if source else None
    if args.get('resource_dir'):
        root=cli.scoped(args['resource_dir'],directory=True)
        if not source or not source.is_relative_to(root) or output.is_relative_to(root):raise ValueError('Resources must contain the input and exclude output')
        if any(p.name.startswith('.env') or p.name=='secrets.toml' for p in root.rglob('*')):raise ValueError('Remove private credential files from deliverable resources')
        if any(p.is_symlink() for p in root.rglob('*')):raise ValueError('Source symlinks are not permitted')
        if args.get('connection_file') and cli.scoped(args['connection_file']).is_relative_to(root):raise ValueError('Keep connection credentials outside deliverable resources')
        shutil.copytree(root,sources,dirs_exist_ok=True);actual=sources/source.relative_to(root)
    elif source:
        actual=sources/source.name;shutil.copy2(source,actual)
    else:actual=None
    schema=cli.scoped(args['schema']) if args.get('schema') else None
    if schema:shutil.copy2(schema,sources/'schema.json')
    shutil.copy2(Path(__file__).with_name('data_job.py'),sources/'data_job.py')
    cfg,values=(None,[])
    if app in ('usql','schemacrawler') or app=='dlt' and (action=='discover' or any(args.get(k) for k in ('database','connection_file','connection_env'))):
        cfg,values=secret_config(args,cli,output)
        if cfg is None:raise ValueError('Select a local database or a supplied private connection')
    if app in ('dlt','usql') and cfg is not None and not cfg.get('url'):raise ValueError('This tool requires a SQLAlchemy/MongoDB URL, not a JDBC-only connection')
    if app=='dlt' and action=='extract' and source is None and not (cfg and cfg['url'].startswith(('mongodb://','mongodb+srv://'))):raise ValueError('Provide an input JSON/CSV file or a saved SELECT query')
    env={'DLT_TELEMETRY':'false','RUNTIME__DLTHUB_TELEMETRY':'false','OMP_NUM_THREADS':'2'}
    with tempfile.TemporaryDirectory(prefix='righaven-data-') as private:
        folder=Path(private);connection=folder/'connection.json'
        if cfg:connection.write_text(json.dumps(cfg));connection.chmod(0o600);env['RIGHAVEN_DATA_CONNECTION_FILE']=str(connection)
        spec={**args,'app':app,'action':action,'input':str(actual) if actual else None,'schema':str(sources/'schema.json') if schema else None,'output':str(output)}
        # Paths remain private and do not become part of sources or receipts.
        spec.pop('connection_file',None);spec.pop('connection_env',None)
        request=folder/'request.json';request.write_text(json.dumps(spec));request.chmod(0o600)
        if app in ('dlt','sqlglot'):
            argv=[str(cli.INSTALL/'apps'/app/'venv/bin/python'),str(Path(__file__).with_name('data_job.py')),str(request)]
            run(argv,output,output,env,values)
        elif app=='usql':
            if not actual or actual.suffix.lower()!='.sql':raise ValueError('Use a saved .sql SELECT query')
            check={**spec,'action':'validate_sql'};request.write_text(json.dumps(check))
            run([str(cli.INSTALL/'apps/sqlglot/venv/bin/python'),str(Path(__file__).with_name('data_job.py')),str(request)],output,output,env,values)
            config=folder/'usql.yaml';config.write_text(json.dumps({'connections':{'righaven':usql_url(cfg['url'])}}));config.chmod(0o600)
            run(['usql','--config',str(config),'--no-rc','--no-password','--json','--file',str(actual),'righaven'],output,output,env,values)
            shutil.copy2(output/'native-stdout.log',output/'query-result.json')
        elif app=='schemacrawler':
            jdbc=cfg.get('jdbc_url')
            username=cfg.get('username','');password=cfg.get('password','')
            if not jdbc:
                parsed=urlsplit(cfg['url']);dialect=parsed.scheme.split('+')[0]
                if dialect not in ('postgresql','postgres','mysql','mariadb'):raise ValueError('Provide an explicit jdbc_url plus separate username/password for this database')
                jdbc='jdbc:'+('postgresql' if dialect=='postgres' else dialect)+'://'+(parsed.hostname or '')+(':'+str(parsed.port) if parsed.port else '')+parsed.path
                username=unquote(parsed.username or '');password=unquote(parsed.password or '')
            if not jdbc.startswith(('jdbc:sqlite:','jdbc:postgresql:','jdbc:mysql:','jdbc:mariadb:','jdbc:sqlserver:','jdbc:oracle:','jdbc:db2:','jdbc:cassandra:')) or re.search(r'(?i)(password=|user=|://[^/]*@)',jdbc):raise ValueError('Use a plain JDBC URL and separate username/password')
            candidates=list((cli.INSTALL/'apps/schemacrawler').rglob('schemacrawler.sh'))
            if len(candidates)!=1:raise RuntimeError('SchemaCrawler installation is incomplete')
            fmt=args.get('format','json');target=output/('schema.'+fmt)
            argv=[str(candidates[0]),'--url='+jdbc,'--user='+username,'--password='+password,'--info-level=standard','--command='+('serialize' if fmt=='json' else 'schema'),'--output-format='+fmt,'--output-file='+str(target),'--no-info']
            if args.get('schemas'):argv+=['--schemas='+args['schemas']]
            run(argv,output,output,env,[*values,password])
            if not target.is_file() or not target.stat().st_size:raise RuntimeError('SchemaCrawler did not create schema output')
            target.write_text(redact(target.read_text(),[v for v in (password,) if v]))
        elif app=='sqlmesh':
            if not actual or actual.suffix.lower() not in ('.yaml','.yml'):raise ValueError('Use a local SQLMesh YAML configuration and its project resource directory')
            import yaml
            config=yaml.safe_load(actual.read_text()) or {}
            gateways=config.get('gateways')
            if not isinstance(gateways,dict) or not gateways:raise ValueError('Declare an explicit local DuckDB gateway')
            if (sources/'config.py').exists():raise ValueError('Use YAML configuration for the isolated local SQLMesh adapter')
            for gateway in gateways.values():
                for key in ('state_connection','test_connection'):
                    if gateway.get(key):raise ValueError('Use the local gateway for state and test connections')
                connection=gateway.get('connection') or {}
                if connection.get('type')!='duckdb' or set(connection)&{'password','token','host','user','url'}:raise ValueError('This adapter plans/applies isolated local DuckDB projects only')
                database=Path(connection.get('database','data.duckdb'))
                if database.is_absolute() or '..' in database.parts:raise ValueError('Keep SQLMesh state and data inside the copied project')
            project=output/'project';shutil.copytree(sources,project)
            argv=[str(cli.INSTALL/'apps/sqlmesh/venv/bin/sqlmesh'),'-p',str(project),'plan','dev','--no-prompts','--auto-apply'] if args.get('apply_local') else [str(cli.INSTALL/'apps/sqlmesh/venv/bin/sqlmesh'),'-p',str(project),'plan','dev','--no-prompts','--explain']
            run(argv,output,project,env,[])
            (output/'result.json').write_text(json.dumps({'mode':'applied_local' if args.get('apply_local') else 'plan_only','project':'project','limits':['No remote deployment is performed.']}))
    if source and cli.digest(source)!=original:raise RuntimeError('Original source was modified')
    result={'status':'passed','output':str(output),'sources':str(sources),'original_preserved':True}
    if (output/'result.json').is_file():result['analysis']=json.loads((output/'result.json').read_text())
    (output/'receipt.json').write_text(json.dumps({'app':app,'operation':action,'input_sha256':original,'result':result,
       'limits':['Read-only credentials are required for external sources. Inferred relationships and business meaning need independent validation. Credentials are excluded from sources.']},indent=2))
    return result
