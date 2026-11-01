"""Adapters of the end-to-end data pipeline recipe.

Every operation works on copies in a fresh output folder, keeps the editable
sources it used under Sources/, writes receipt.json and never connects to a
production system. DuckDB files are created with storage version v1.4.0 so the
DuckDB 2 (dlt) and 1.5 (SQLMesh, Faker) environments can share them.
"""
import collections,hashlib,json,os,re,shutil,subprocess,tempfile
from pathlib import Path
import xml.etree.ElementTree as ET

APPS={'tbls','faker','supercronic'}
EXTRA={('sqlglot','model'),('sqlglot','ddl'),('sqlglot','scaffold'),('duckdb','replicate'),('duckdb','infer'),('dlt','run')}
STORAGE='v1.4.0'
FILE_SUFFIXES={'.json':'json','.jsonl':'jsonl','.ndjson':'jsonl','.parquet':'parquet','.csv':'csv','.xml':'xml'}
MAX_FILES=200
MAX_BYTES=2*1024**3
SECRET_FILES=('.env','secrets.toml','.dlt/secrets.toml','credentials.json')
DENIED_DDL=re.compile(r'\b(ATTACH|DETACH|COPY|INSTALL|LOAD|EXPORT|IMPORT|PRAGMA|SET|CALL|SECRET)\b|read_\w+\s*\(|https?://|^\s*\.\w+',re.I|re.M)
DUCKDB='duckdb'


def handles(app,action):
    return app in APPS or (app,action) in EXTRA


def binary(app,cli):
    if app=='faker':return str(cli.INSTALL/'apps/faker/venv/bin/python')
    return app


def version_flags(app):
    return {'tbls':['version'],'supercronic':['-version'],
            'faker':['-c','import faker,duckdb;print("Faker",faker.VERSION,"DuckDB",duckdb.__version__)']}[app]


def venv(cli,app):
    path=cli.INSTALL/'apps'/app/'venv/bin/python'
    if not path.is_file():raise RuntimeError(app+' non è installato in questo ambiente: aggiungilo agli strumenti dell’ambiente')
    return str(path)


def run(argv,output,*,cwd=None,env=None,timeout=900,codes=(0,),label='native',user_errors=False):
    clean={k:v for k,v in os.environ.items() if not re.match(r'(?i).*(PASSWORD|SECRET|TOKEN|CREDENTIALS|API_KEY)',k)}
    result=subprocess.run([str(a) for a in argv],cwd=cwd or output,capture_output=True,text=True,errors='replace',timeout=timeout,env={**clean,**(env or {})})
    (output/(label+'-stdout.log')).write_text(result.stdout)
    (output/(label+'-stderr.log')).write_text(result.stderr)
    if user_errors and result.returncode==3:raise ValueError((result.stderr or result.stdout).strip()[-2000:])
    if result.returncode not in codes:
        raise RuntimeError(label+' terminato con codice '+str(result.returncode)+': '+(result.stderr or result.stdout)[-2500:])
    return result


def keep(path,output,name=None):
    target=output/'Sources'/(name or path.name)
    if target.exists():raise ValueError('Due sorgenti con lo stesso nome: '+target.name)
    shutil.copy2(path,target);return target


def receipt(output,app,action,inputs,result,limits):
    (output/'receipt.json').write_text(json.dumps({'app':app,'operation':action,'inputs_sha256':inputs,'result':result,'limits':limits},indent=2,ensure_ascii=False))
    return result


def load_model(path):
    data=json.loads(path.read_text())
    if not isinstance(data,dict) or not isinstance(data.get('tables'),list) or not data['tables']:
        raise ValueError('Serve il model.json prodotto da sqlglot model')
    for table in data['tables']:
        if not isinstance(table,dict) or not table.get('name') or not isinstance(table.get('columns'),list):raise ValueError('Tabella non valida nel modello')
        table.setdefault('schema','');table.setdefault('primary_key',[]);table.setdefault('foreign_keys',[]);table.setdefault('unique',[])
    return data


def qualified(table):
    return (table['schema']+'.' if table.get('schema') else '')+table['name']


def strip_literals(text):
    text=re.sub(r"'(?:[^']|'')*'","''",text)
    return re.sub(r'(?m)--.*$','',text)


def duckdb_json(cli,database,sql,output,label):
    argv=[DUCKDB,'-json','-init','/dev/null',*(['-readonly'] if str(database)!=':memory:' else []),str(database),'-c',sql]
    result=run(argv,output,label=label)
    text=result.stdout.strip()
    return json.loads(text) if text else []


# --- sqlglot: model and ddl -------------------------------------------------

def schema_job(app,action,args,cli,output):
    source=cli.scoped(args['input']);inputs={source.name:cli.digest(source)}
    request={'action':action,'output':str(output),'input':str(keep(source,output))}
    for field in ('dialect','name','strict_references','comments','source_dialect','ingest_cron','transform_cron','stubs_cron','model_cron'):
        if field in args:request[field]=args[field]
    if args.get('overrides'):
        overrides=cli.scoped(args['overrides']);inputs[overrides.name]=cli.digest(overrides)
        request['overrides']=str(keep(overrides,output,'documentazione-'+overrides.name))
    here=Path(__file__).resolve().parent
    for helper in ('pipeline_model.py','pipeline_job.py','pipeline_scaffold.py','stubgen.py'):shutil.copy2(here/helper,output/'Sources'/helper)
    with tempfile.TemporaryDirectory(prefix='righaven-model-') as private:
        spec=Path(private)/'request.json';spec.write_text(json.dumps(request))
        run([venv(cli,'sqlglot'),str(here/'pipeline_job.py'),str(spec)],output,label='sqlglot',timeout=600,user_errors=True)
    result=json.loads((output/'result.json').read_text())
    limits=['Il modello distingue la struttura osservata da quella documentata; le relazioni non dichiarate restano ipotesi da confermare.']
    if action=='ddl':limits=['DDL generato da rivedere prima di eseguirlo su un server condiviso.']+result.get('limits',[])
    if action=='scaffold':limits=result.get('limits',[])
    return receipt(output,app,action,inputs,{'status':'passed','output':str(output),**result},limits)


# --- duckdb: replicate and infer -------------------------------------------

def replicate(args,cli,output):
    source=cli.scoped(args['input'])
    if source.suffix.lower()!='.sql':raise ValueError('Usa il DDL DuckDB prodotto da sqlglot ddl')
    text=source.read_text(errors='replace')
    if DENIED_DDL.search(strip_literals(text)):raise ValueError('Il DDL della replica può contenere solo CREATE SCHEMA/TABLE/VIEW e COMMENT: niente ATTACH, COPY, estensioni o letture di file')
    inputs={source.name:cli.digest(source)};ddl=keep(source,output)
    model=None
    if args.get('model'):
        model_path=cli.scoped(args['model']);inputs[model_path.name]=cli.digest(model_path);model=load_model(model_path);keep(model_path,output)
    replica=output/'replica.duckdb'
    script=output/'Sources/create-replica.sql'
    script.write_text("ATTACH '"+str(replica).replace("'","''")+"' AS replica (STORAGE_VERSION '"+STORAGE+"');\nUSE replica;\n.read '"+str(ddl).replace("'","''")+"'\n")
    run([DUCKDB,'-init','/dev/null','-bail','-f',str(script)],output,label='duckdb')
    tables=duckdb_json(cli,replica,"SELECT schema_name, table_name, column_count FROM duckdb_tables() ORDER BY 1,2",output,'duckdb-tables')
    constraints=duckdb_json(cli,replica,"SELECT schema_name, table_name, constraint_type, count(*) AS n FROM duckdb_constraints() GROUP BY ALL ORDER BY 1,2,3",output,'duckdb-constraints')
    found={(t['schema_name'].lower(),t['table_name'].lower()):t for t in tables}
    counts=collections.Counter()
    for c in constraints:counts[(c['schema_name'].lower(),c['table_name'].lower(),c['constraint_type'])]+=int(c['n'])
    checks=[];status='passed'
    if model:
        for table in model['tables']:
            if table.get('kind','table')!='table':continue
            k=((table['schema'] or 'main').lower(),table['name'].lower());actual=found.get(k)
            row={'table':qualified(table),'exists':bool(actual),'columns_expected':len(table['columns']),'columns_actual':actual['column_count'] if actual else 0,
                 'primary_key':bool(table['primary_key'])==bool(counts[k+('PRIMARY KEY',)]),
                 'foreign_keys_expected':sum(1 for fk in table['foreign_keys'] if fk.get('declared',True)),'foreign_keys_actual':counts[k+('FOREIGN KEY',)]}
            if not actual or row['columns_expected']!=row['columns_actual'] or not row['primary_key']:status='failed'
            checks.append(row)
    total=sum(1 for _ in tables)
    (output/'verification.json').write_text(json.dumps({'tables':tables,'constraints':constraints,'checks':checks},indent=2))
    result={'status':status,'output':str(output),'replica':'replica.duckdb','storage_version':STORAGE,'tables':total,
            'constraints':{t:sum(v for (s,n,kind),v in counts.items() if kind==t) for t in ('PRIMARY KEY','FOREIGN KEY','UNIQUE','CHECK','NOT NULL')},
            'mismatches':[c for c in checks if not c['exists'] or c['columns_expected']!=c['columns_actual'] or not c['primary_key']]}
    if model:
        missing_fk=[c for c in checks if c['foreign_keys_actual']<c['foreign_keys_expected']]
        if missing_fk:result['foreign_keys_not_enforced']=[c['table'] for c in missing_fk]
    return receipt(output,'duckdb','replicate',inputs,result,['Replica vuota per sviluppo e test: DuckDB non applica tutte le regole del motore di origine (trigger, sequenze, permessi, collation).'])


def xml_to_jsonl(path,target,record=None):
    """Repeated child elements of the root become records; attributes and leaf text become fields."""
    if path.stat().st_size>256*1024**2:raise ValueError('File XML oltre 256 MiB: dividilo prima')
    root=ET.parse(path).getroot()
    tags=collections.Counter(child.tag for child in root)
    if not tags:raise ValueError(path.name+': nessun elemento ripetuto sotto la radice')
    tag=record or tags.most_common(1)[0][0]
    def value(element):
        children=list(element)
        if not children:return element.text.strip() if element.text and element.text.strip() else None
        nested={}
        for child in children:nested.setdefault(child.tag,[]).append(value(child))
        return {k:(v[0] if len(v)==1 else v) for k,v in nested.items()}
    count=0
    with target.open('w') as stream:
        for element in root.iter(tag):
            row={'@'+k:v for k,v in element.attrib.items()}
            for child in element:
                v=value(child);row[child.tag]=json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v
            stream.write(json.dumps(row,ensure_ascii=False)+'\n');count+=1
    if not count:raise ValueError(path.name+': nessun record <'+tag+'>')
    return tag,count


def table_name(path):
    stem=path.name.split('.')[0]
    name=re.sub(r'[^A-Za-z0-9_]','_',stem).strip('_').lower() or 'records'
    return name if not name[0].isdigit() else 't_'+name


def infer(args,cli,output):
    source=cli.scoped(args['input'],directory=Path(args['input']).is_dir())
    files=[source] if source.is_file() else sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in FILE_SUFFIXES)
    if not files:raise ValueError('Nessun file JSON, JSON Lines, Parquet, CSV o XML da analizzare')
    if len(files)>MAX_FILES or sum(p.stat().st_size for p in files)>MAX_BYTES:raise ValueError('Troppi dati: analizza un campione (al massimo 200 file e 2 GiB)')
    if any(p.suffix.lower() not in FILE_SUFFIXES for p in files):raise ValueError('Formato non supportato: '+', '.join(sorted({p.suffix for p in files})))
    work=output/'work';work.mkdir();groups=collections.OrderedDict();inputs={};notes=[]
    for path in files:
        kind=FILE_SUFFIXES[path.suffix.lower()];inputs[str(path.relative_to(source.parent))]=cli.digest(path)
        if kind=='xml':
            target=work/(path.stem+'.jsonl');tag,count=xml_to_jsonl(path,target,args.get('record'))
            notes.append(path.name+': '+str(count)+' record <'+tag+'> convertiti in JSON Lines');path,kind=target,'jsonl'
        groups.setdefault((table_name(path),kind),[]).append(path)
    tables=[];con_sql=[]
    reader={'json':"read_json_auto({p}, format='auto')",'jsonl':"read_json_auto({p}, format='newline_delimited')",'parquet':'read_parquet({p})','csv':'read_csv_auto({p})'}
    for (name,kind),paths in groups.items():
        literal='['+', '.join("'"+str(p).replace("'","''")+"'" for p in paths)+']'
        relation=reader[kind].format(p=literal)
        described=duckdb_json(cli,':memory:',"DESCRIBE SELECT * FROM "+relation,output,'duckdb-describe')
        stats=duckdb_json(cli,':memory:',"SELECT count(*) AS n"+''.join(", count(DISTINCT \""+c['column_name'].replace('"','""')+"\") AS \"d"+str(i)+"\", count(\""+c['column_name'].replace('"','""')+"\") AS \"c"+str(i)+"\"" for i,c in enumerate(described))+" FROM "+relation,output,'duckdb-stats')[0]
        columns=[]
        for i,c in enumerate(described):
            data_type=c['column_type']
            if re.match(r'(STRUCT|MAP|UNION)\b|.*\[\]$',data_type):
                notes.append(name+'.'+c['column_name']+': tipo annidato '+data_type[:60]+' trattato come JSON');data_type='JSON'
            columns.append({'name':c['column_name'],'type':data_type,'nullable':stats['c'+str(i)]<stats['n'],'description':''})
        candidates=[c['column_name'] for i,c in enumerate(described) if stats['n'] and stats['d'+str(i)]==stats['n'] and stats['c'+str(i)]==stats['n']
                    and re.search(r'(^id$|_id$|^cod|code$|^key$)',c['column_name'],re.I)]
        if candidates:notes.append(name+': possibile chiave primaria '+', '.join(candidates)+' (univoca e non nulla nel campione; da confermare)')
        tables.append({'schema':'','name':name,'description':'','columns':columns,'primary_key':[],'foreign_keys':[],'labels':['file:'+kind],
                       'rows':min(int(stats['n']),1000000)})
    names={t['name'] for t in tables}
    for t in tables:
        for c in t['columns']:
            m=re.match(r'(?i)(?:id_?)?(\w+?)_?id$',c['name'])
            if m and c['name'].lower()!='id':
                parent=next((n for n in names if n!=t['name'] and n.rstrip('s') in (m.group(1).lower(),m.group(1).lower().rstrip('s'))),None)
                if parent:notes.append(t['name']+'.'+c['name']+': possibile riferimento a '+parent+' (relazione ipotetica, non dichiarata)')
    model={'model_version':1,'name':args.get('name') or (source.stem if source.is_file() else source.name),'description':'',
           'source':{'kind':'files','dialect':'duckdb'},'tables':tables,'issues':notes}
    (output/'model.json').write_text(json.dumps(model,indent=2,ensure_ascii=False))
    result={'status':'passed','output':str(output),'model':'model.json','tables':len(tables),'columns':sum(len(t['columns']) for t in tables),'notes':notes[:50]}
    return receipt(output,'duckdb','infer',inputs,result,['Tipi e nullabilità sono dedotti dai dati presenti: chiavi e relazioni sono solo candidate. Passa il modello a sqlglot model con la documentazione per descriverlo.'])


# --- tbls: catalog ------------------------------------------------------------

def tbls_schema(model):
    tables=[];relations=[]
    index={((t['schema'] or '').lower(),t['name'].lower()):t for t in model['tables']}
    for t in model['tables']:
        name=qualified(t);constraints=[]
        if t['primary_key']:
            constraints.append({'name':t['name']+'_pkey','type':'PRIMARY KEY','def':'PRIMARY KEY ('+', '.join(t['primary_key'])+')','table':name,'columns':list(t['primary_key'])})
        for i,u in enumerate(t.get('unique') or []):
            constraints.append({'name':t['name']+'_unique_'+str(i+1),'type':'UNIQUE','def':'UNIQUE ('+', '.join(u)+')','table':name,'columns':list(u)})
        for i,fk in enumerate(t['foreign_keys']):
            parent=index.get(((fk['references'].get('schema') or '').lower(),fk['references']['table'].lower()))
            if parent is None:continue
            definition='FOREIGN KEY ('+', '.join(fk['columns'])+') REFERENCES '+qualified(parent)+'('+', '.join(fk['references']['columns'])+')'
            if fk.get('declared',True):
                constraints.append({'name':fk.get('name') or t['name']+'_fk_'+str(i+1),'type':'FOREIGN KEY','def':definition,'table':name,
                                    'referenced_table':qualified(parent),'columns':list(fk['columns']),'referenced_columns':list(fk['references']['columns'])})
            nullable=any(c['nullable'] for c in t['columns'] if c['name'] in fk['columns'])
            relations.append({'table':name,'columns':list(fk['columns']),'cardinality':'zero_or_more','parent_table':qualified(parent),
                              'parent_columns':list(fk['references']['columns']),'parent_cardinality':'zero_or_one' if nullable else 'exactly_one',
                              'def':definition if fk.get('declared',True) else 'Relazione documentata, non dichiarata nel database','virtual':not fk.get('declared',True)})
        columns=[]
        for c in t['columns']:
            labels=[{'name':'pii','virtual':True}] if c.get('pii') else []
            labels+=[{'name':str(l),'virtual':True} for l in c.get('labels') or []]
            columns.append({'name':c['name'],'type':c['type'],'nullable':bool(c.get('nullable',True)),'default':c.get('default'),'comment':c.get('description') or '',
                            **({'labels':labels} if labels else {})})
        table={'name':name,'type':'VIEW' if t.get('kind')=='view' else 'BASE TABLE','comment':t.get('description') or '','columns':columns,
               'indexes':[],'constraints':constraints,'triggers':[],'def':t.get('definition') or ''}
        labels=[{'name':str(l),'virtual':True} for l in t.get('labels') or []]
        if labels:table['labels']=labels
        tables.append(table)
    return {'name':model.get('name') or 'database','desc':model.get('description') or '','tables':tables,'relations':relations,
            'driver':{'name':(model.get('source') or {}).get('dialect') or 'json','database_version':'righaven-model-'+str(model.get('model_version',1))}}


def catalog(action,args,cli,output):
    source=cli.scoped(args['input']);model=load_model(source);inputs={source.name:cli.digest(source)};keep(source,output)
    schema=output/'Sources/tbls-schema.json';schema.write_text(json.dumps(tbls_schema(model),indent=2,ensure_ascii=False))
    config=output/'Sources/.tbls.yml';home=output/'private-home';home.mkdir()
    lines=['dsn: json://'+str(schema),'docPath: '+str(output/'catalogo'),'name: '+json.dumps(model.get('name') or 'database'),
           'er:','  format: '+args.get('er_format','svg'),'format:','  adjust: true','  number: true']
    if action=='lint':
        excluded=['id','created_at','updated_at']
        lines+=['lint:','  requireTableComment:','    enabled: true',
                '  requireColumnComment:','    enabled: '+('true' if args.get('require_column_comments',True) else 'false'),'    exclude: '+json.dumps(excluded),
                '  unrelatedTable:','    enabled: true','  duplicateRelations:','    enabled: true',
                '  columnCount:','    enabled: true','    max: '+str(args.get('max_columns',80))]
    config.write_text('\n'.join(lines)+'\n')
    env={'HOME':str(home),'TBLS_DSN':'','TBLS_DOC_PATH':''}
    if action=='document':
        run(['tbls','doc','-c',str(config),'--force'],output,env=env,label='tbls')
        coverage=run(['tbls','coverage','-c',str(config),'--format','json'],output,env=env,label='tbls-coverage')
        try:cover=json.loads(coverage.stdout)
        except ValueError:cover={'raw':coverage.stdout[-2000:]}
        pages=sorted(p.name for p in (output/'catalogo').glob('*.md'))
        if 'README.md' not in pages:raise RuntimeError('tbls non ha prodotto il catalogo README.md')
        diagrams=sorted(p.name for p in (output/'catalogo').glob('*.svg'))
        if args.get('er_format','svg')=='svg' and not diagrams:raise RuntimeError('tbls non ha prodotto il diagramma ER')
        result={'status':'passed','output':str(output),'catalog':'catalogo/README.md','pages':len(pages),'diagrams':len(diagrams),'coverage':cover}
    else:
        linted=run(['tbls','lint','-c',str(config)],output,env=env,label='tbls-lint',codes=(0,1))
        findings=[l for l in (linted.stdout+linted.stderr).splitlines() if l.strip() and not l.startswith(('\x1b',' ')) and ':' in l]
        missing_pk=[qualified(t) for t in model['tables'] if t.get('kind','table')=='table' and not t['primary_key']]
        (output/'findings.txt').write_text(linted.stdout+linted.stderr+''.join('requirePrimaryKey: '+t+' non ha chiave primaria\n' for t in missing_pk))
        result={'status':'passed' if linted.returncode==0 and not missing_pk else 'failed','output':str(output),'findings':'findings.txt',
                'tbls_returncode':linted.returncode,'tables_without_primary_key':missing_pk,'sample':findings[:30]}
    return receipt(output,'tbls',action,inputs,result,['Il catalogo descrive il modello: la correttezza delle descrizioni va confermata da chi conosce il dominio.'])


# --- faker: stub data -----------------------------------------------------------

def stubs(args,cli,output):
    source=cli.scoped(args['input']);model=load_model(source);inputs={source.name:cli.digest(source)};keep(source,output,'model.json')
    here=Path(__file__).resolve().parent;shutil.copy2(here/'stubgen.py',output/'Sources/stubgen.py')
    formats=args.get('formats') or (['duckdb','csv'] if args.get('database') else ['csv','parquet'])
    argv=[venv(cli,'faker'),str(here/'stubgen.py'),'--model',str(output/'Sources/model.json'),'--output',str(output/'data'),
          '--rows',str(args.get('rows',50)),'--seed',str(args.get('seed',20260101)),'--locale',args.get('locale','it_IT'),'--formats',','.join(formats),
          '--batch',str(args['batch']) if 'batch' in args else 'auto']
    if 'duckdb' in formats:
        if not args.get('database'):raise ValueError('Il formato duckdb richiede database: la replica vuota o il database di prova del lotto precedente')
        database=cli.scoped(args['database']);inputs[database.name]=cli.digest(database)
        target=output/'stub.duckdb';shutil.copy2(database,target);argv+=['--database',str(target)]
    run(argv,output,label='stubgen',env={'HOME':str(output)},timeout=1200)
    manifests=sorted((output/'data').glob('manifest.batch-*.json'))
    if not manifests:raise RuntimeError('Il generatore non ha prodotto il manifest del lotto')
    manifest=json.loads(manifests[-1].read_text())
    result={'status':'passed','output':str(output),'batch':manifest['batch'],'rows_per_table':manifest['rows_per_table'],
            'database':'stub.duckdb' if 'duckdb' in formats else None,'database_totals':manifest['database_totals'],
            'files':len(manifest['files']),'manifest':str(manifests[-1].relative_to(output)),'issues':manifest['issues'][:30]}
    return receipt(output,'faker','generate',inputs,result,manifest['limits'])


# --- supercronic: schedule ----------------------------------------------------

def schedule(args,cli,output):
    source=cli.scoped(args['input']);inputs={source.name:cli.digest(source)};crontab=keep(source,output)
    tested=run(['supercronic','-test','-quiet',str(crontab)],output,label='supercronic',codes=(0,1,2))
    jobs=[];environment=[]
    for line in crontab.read_text().splitlines():
        text=line.strip()
        if not text or text.startswith('#'):continue
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*=',text):environment.append(text.split('=',1)[0]);continue
        if text.startswith('@'):expression,_,command=text.partition(' ')
        else:
            fields=text.split()
            count=7 if len(fields)>7 and re.fullmatch(r'[\d*/,\-]+',fields[5]) and re.fullmatch(r'[\d*/,\-]+',fields[6]) else 5
            expression,command=' '.join(fields[:count]),' '.join(fields[count:])
        jobs.append({'schedule':expression,'command':command.strip()})
    leaked=[n for n in environment if re.search(r'(?i)PASSWORD|SECRET|TOKEN|KEY',n)]
    status='passed' if tested.returncode==0 and jobs and not leaked else 'failed'
    result={'status':status,'output':str(output),'valid':tested.returncode==0,'jobs':jobs,'environment':environment,
            'secrets_in_crontab':leaked,'native':(tested.stderr or tested.stdout)[-1500:]}
    return receipt(output,'supercronic','validate',inputs,result,['La validazione controlla la sintassi; durata, sovrapposizioni e fuso orario vanno provati nell’ambiente di destinazione.'])


# --- dlt: local pipeline run ----------------------------------------------------

def pipeline_run(args,cli,output):
    root=cli.scoped(args['resource_dir'],directory=True);script=cli.scoped(args['input'])
    if not script.is_relative_to(root) or script.suffix!='.py':raise ValueError('input deve essere lo script .py della pipeline dentro resource_dir')
    if output.is_relative_to(root):raise ValueError('output deve stare fuori dal progetto')
    for path in root.rglob('*'):
        relative=str(path.relative_to(root))
        if path.is_symlink():raise ValueError('Il progetto non può contenere collegamenti simbolici')
        if relative in SECRET_FILES or path.name in ('.env','secrets.toml'):raise ValueError('Rimuovi i file di credenziali dal progetto ('+relative+'): in produzione arrivano da variabili d’ambiente')
    database=cli.scoped(args['source_database'])
    if database.suffix!='.duckdb':raise ValueError('source_database deve essere il database DuckDB dei dati di prova')
    inputs={str(p.relative_to(root)):cli.digest(p) for p in sorted(root.rglob('*')) if p.is_file()};inputs[database.name]=cli.digest(database)
    project=output/'project';shutil.copytree(root,project,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.dlt/pipelines'))
    work=output/'work';work.mkdir();source=work/'source.duckdb';shutil.copy2(database,source)
    warehouse=output/'warehouse.duckdb';python=venv(cli,'dlt')
    run([python,'-c',"import duckdb,sys;c=duckdb.connect();c.execute(\"ATTACH '\"+sys.argv[1].replace(\"'\",\"''\")+\"' AS w (STORAGE_VERSION '"+STORAGE+"')\");c.close()",str(warehouse)],output,label='warehouse')
    env={'PIPELINE_ENV':args.get('pipeline_env','local'),'RIGHAVEN_SOURCE_DUCKDB':str(source),'RIGHAVEN_WAREHOUSE_DUCKDB':str(warehouse),
         'DLT_DATA_DIR':str(work/'dlt'),'DLT_PROJECT_DIR':str(project),'DLT_TELEMETRY':'false','RUNTIME__DLTHUB_TELEMETRY':'false',
         'HOME':str(work),'OMP_NUM_THREADS':'2','PYTHONDONTWRITEBYTECODE':'1'}
    run([python,str(project/script.relative_to(root))],output,cwd=project,env=env,label='pipeline',timeout=1800)
    counts=run([python,'-c',"import duckdb,json,sys;c=duckdb.connect(sys.argv[1],read_only=True);rows=c.execute(\"SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema NOT IN ('information_schema','pg_catalog') ORDER BY 1,2\").fetchall();print(json.dumps([[s,t,c.execute('SELECT count(*) FROM \"'+s+'\".\"'+t+'\"').fetchone()[0]] for s,t in rows]))",str(warehouse)],output,label='warehouse-counts')
    tables=json.loads(counts.stdout.strip().splitlines()[-1])
    loaded=[{'schema':s,'table':t,'rows':n} for s,t,n in tables if not t.startswith('_dlt_')]
    loads=next((n for s,t,n in tables if t=='_dlt_loads'),0)
    if not loaded:raise RuntimeError('La pipeline non ha caricato tabelle nel warehouse locale')
    result={'status':'passed','output':str(output),'warehouse':'warehouse.duckdb','storage_version':STORAGE,'tables':loaded,'dlt_loads':loads,
            'pipeline_env':env['PIPELINE_ENV']}
    return receipt(output,'dlt','run',inputs,result,['Esecuzione locale sui dati di prova: connessione, permessi e volumi del sistema reale vanno provati nell’ambiente di test.'])


def invoke(app,action,args,cli):
    output=cli.scoped(args['output'],exists=False,directory=True,fresh=True)
    output.mkdir(parents=True);(output/'Sources').mkdir()
    if app=='sqlglot':return schema_job(app,action,args,cli,output)
    if (app,action)==('duckdb','replicate'):return replicate(args,cli,output)
    if (app,action)==('duckdb','infer'):return infer(args,cli,output)
    if app=='tbls':return catalog(action,args,cli,output)
    if app=='faker':return stubs(args,cli,output)
    if app=='supercronic':return schedule(args,cli,output)
    if (app,action)==('dlt','run'):return pipeline_run(args,cli,output)
    raise ValueError('Operazione non supportata: '+app+'.'+action)
