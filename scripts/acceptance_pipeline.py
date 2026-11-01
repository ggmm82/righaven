"""Offline fixtures of the data pipeline recipe, each with a known result.

Cases extend the existing sqlglot, duckdb, dlt and sqlmesh checks and cover tbls,
Faker and supercronic. When SQLGlot, Faker, dlt and SQLMesh are all installed the
SQLMesh case also runs the whole chain on a generated production package.
"""
import hashlib,json,shutil,subprocess,sys
from pathlib import Path
INSTALL=Path('/opt/righaven')
sys.path.insert(0,str(INSTALL))

DDL_PG='''CREATE SCHEMA vendite;
CREATE TABLE vendite."Cliente" ("Id" integer NOT NULL, "Nome" varchar(80) NOT NULL, "Email" varchar(120), "Creato" timestamp NOT NULL);
CREATE TABLE vendite.ordine (id bigint NOT NULL, cliente_id integer NOT NULL, importo numeric(10,2) NOT NULL, stato varchar(10),
  updated_at timestamp NOT NULL, CONSTRAINT importo_positivo CHECK (importo >= 0), CONSTRAINT stato_valido CHECK (stato IN ('nuovo','pagato')));
ALTER TABLE ONLY vendite."Cliente" ADD CONSTRAINT cliente_pkey PRIMARY KEY ("Id");
ALTER TABLE ONLY vendite."Cliente" ADD CONSTRAINT cliente_email UNIQUE ("Email");
ALTER TABLE ONLY vendite.ordine ADD CONSTRAINT ordine_pkey PRIMARY KEY (id);
ALTER TABLE ONLY vendite.ordine ADD CONSTRAINT ordine_cliente_fk FOREIGN KEY (cliente_id) REFERENCES vendite."Cliente"("Id");
COMMENT ON TABLE vendite.ordine IS 'Ordini di vendita';
COMMENT ON COLUMN vendite.ordine.importo IS 'Importo IVA inclusa';
'''
DOC='''name: vendite
description: Vendite del negozio online
tables:
  - name: Cliente
    description: Anagrafica clienti
    rows: 20
    columns:
      - {name: Nome, pii: true, description: Nome e cognome}
      - {name: Email, pii: true, description: Email di contatto}
  - name: ordine
    rows: 60
    columns:
      - {name: stato, description: Stato dell ordine}
'''
MODEL={'model_version':1,'name':'vendite','description':'Vendite','source':{'kind':'documented','dialect':'postgres'},'issues':[],'tables':[
 {'schema':'vendite','name':'Cliente','description':'Anagrafica clienti','kind':'table','rows':20,'primary_key':['Id'],'unique':[['Email']],'foreign_keys':[],'checks':[],'labels':[],
  'columns':[{'name':'Id','type':'INT','nullable':False,'description':'Codice cliente','pii':False},
             {'name':'Nome','type':'VARCHAR(80)','nullable':False,'description':'Nome e cognome','pii':True},
             {'name':'Email','type':'VARCHAR(120)','nullable':True,'description':'Email','pii':True},
             {'name':'Creato','type':'TIMESTAMP','nullable':False,'description':'Data di registrazione','pii':False}]},
 {'schema':'vendite','name':'ordine','description':'Ordini di vendita','kind':'table','rows':60,'primary_key':['id'],'unique':[],'labels':[],
  'foreign_keys':[{'name':'ordine_cliente_fk','columns':['cliente_id'],'references':{'schema':'vendite','table':'Cliente','columns':['Id']},'declared':True}],
  'checks':[{'name':'importo_positivo','expression':'importo >= 0'},{'name':'stato_valido','expression':"stato IN ('nuovo', 'pagato')"}],
  'columns':[{'name':'id','type':'BIGINT','nullable':False,'description':'Numero ordine','pii':False},
             {'name':'cliente_id','type':'INT','nullable':False,'description':'Cliente','pii':False},
             {'name':'importo','type':'DECIMAL(10, 2)','nullable':False,'description':'Importo','pii':False},
             {'name':'stato','type':'VARCHAR(10)','nullable':True,'description':'Stato','pii':False},
             {'name':'updated_at','type':'TIMESTAMP','nullable':False,'description':'Ultima modifica','pii':False}]}]}
DDL_DUCK='''CREATE SCHEMA IF NOT EXISTS "vendite";
CREATE TABLE "vendite"."Cliente" ("Id" INTEGER NOT NULL, "Nome" VARCHAR NOT NULL, "Email" VARCHAR, "Creato" TIMESTAMP NOT NULL, PRIMARY KEY ("Id"), UNIQUE ("Email"));
CREATE TABLE "vendite"."ordine" ("id" BIGINT NOT NULL, "cliente_id" INTEGER NOT NULL, "importo" DECIMAL(10, 2) NOT NULL, "stato" VARCHAR, "updated_at" TIMESTAMP NOT NULL,
  PRIMARY KEY ("id"), FOREIGN KEY ("cliente_id") REFERENCES "vendite"."Cliente" ("Id"), CHECK (importo >= 0), CHECK (stato IN ('nuovo', 'pagato')));
'''


def operation(c,_operation,app=None,allowed=(0,2),**args):
    """Call any recipe tool; status failed (exit 2) is a result, not an error."""
    app=app or c.app
    p=subprocess.run([app+'-cli','call',_operation,json.dumps(args)],capture_output=True,text=True,timeout=1500)
    c.commands.append({'argv':[app+'-cli','call',_operation,args],'returncode':p.returncode,'stdout':p.stdout[-4000:],'stderr':p.stderr[-3000:]})
    if p.returncode not in allowed:raise RuntimeError(app+'.'+_operation+': '+(p.stderr or p.stdout)[-3000:])
    return json.loads(p.stdout) if p.returncode in (0,2) else None


def write(c,name,text):
    path=c.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text);return path


def python(app):
    return str(INSTALL/'apps'/app/'venv/bin/python')


def duck(app,database,sql,read_only=True):
    code=("import duckdb,json,sys;c=duckdb.connect(sys.argv[1],read_only=%s);print(json.dumps(c.execute(sys.argv[2]).fetchall(),default=str))"%read_only)
    return json.loads(subprocess.run([python(app),'-c',code,str(database),sql],capture_output=True,text=True,check=True,timeout=120).stdout)


def create_replica(app,path,ddl):
    code=("import duckdb,sys;c=duckdb.connect();c.execute(\"ATTACH '\"+sys.argv[1]+\"' AS r (STORAGE_VERSION 'v1.4.0')\");c.execute('USE r');c.execute(open(sys.argv[2]).read());c.close()")
    subprocess.run([python(app),'-c',code,str(path),str(ddl)],check=True,capture_output=True,text=True,timeout=120)


def sqlglot(c):
    ddl=write(c,'schema.sql',DDL_PG);doc=write(c,'documentazione.yaml',DOC)
    model=operation(c,'model',input=str(ddl),dialect='postgres',overrides=str(doc),output=str(c.root/'Model'))
    data=json.loads((c.root/'Model/model.json').read_text());tables={t['name']:t for t in data['tables']}
    c.check('DDL with ALTER, COMMENT and CHECK becomes the neutral model',model['summary']['tables']==2 and model['summary']['foreign_keys']==1
            and tables['ordine']['description']=='Ordini di vendita' and len(tables['ordine']['checks'])==2 and tables['Cliente']['unique']==[['Email']],model['summary'])
    c.check('Documentation adds descriptions and personal data labels without changing structure',
            model['summary']['pii_columns']==2 and tables['Cliente']['description']=='Anagrafica clienti' and tables['Cliente']['primary_key']==['Id'],tables['Cliente']['columns'])
    results={}
    for target in ('duckdb','tsql','fabric','oracle'):
        results[target]=operation(c,'ddl',input=str(c.root/'Model/model.json'),dialect=target,output=str(c.root/('DDL-'+target)))
    c.check('DDL for DuckDB, SQL Server, Fabric and Oracle is generated and re-parsed',all(r['statements']>=2 for r in results.values()),
            {k:r['statements'] for k,r in results.items()})
    c.check('Fabric limits on unenforced keys are reported',any('Fabric' in l for l in results['fabric']['limits']),results['fabric']['limits'])
    package=operation(c,'scaffold',input=str(c.root/'Model/model.json'),dialect='postgres',name='vendite',output=str(c.root/'Package'))
    root=c.root/'Package/package';tables_json=json.loads((root/'ingestion/tables.json').read_text())
    needed=['ingestion/pipeline.py','transform/config.yaml','ops/crontab','ops/run.sh','Dockerfile','compose.yaml','.env.example','README.md','stubs/stubgen.py','schema/replica.duckdb.sql']
    c.check('Production package contains ingestion, transformation, schedule, container and runbook',all((root/n).is_file() for n in needed),package['files'])
    c.check('Incremental cursor and dlt names come from the model',{t['target']:t['cursor'] for t in tables_json}=={'cliente':None,'ordine':'updated_at'},tables_json)
    compiled=subprocess.run([python('sqlglot'),'-m','py_compile',str(root/'ingestion/pipeline.py'),str(root/'stubs/stubgen.py')],capture_output=True,text=True)
    c.check('Generated Python sources compile',compiled.returncode==0,compiled.stderr[-500:])
    text=''.join(p.read_text(errors='replace') for p in root.rglob('*') if p.is_file() and p.suffix in ('.yaml','.yml','.example','.sh',''))
    c.check('No secret values are written in the package','PASSWORD=\n' in text and "env_var('WAREHOUSE_PASSWORD'" in text,'environment variables only')


def duckdb(c):
    ddl=write(c,'replica.sql',DDL_DUCK);model=write(c,'model.json',json.dumps(MODEL))
    result=operation(c,'replicate',input=str(ddl),model=str(model),output=str(c.root/'Replica'))
    c.check('Empty replica matches the model: tables, columns and keys',result['status']=='passed' and result['tables']==2
            and result['constraints']['FOREIGN KEY']==1 and result['constraints']['PRIMARY KEY']==2,result)
    rows=subprocess.run(['duckdb','-json','-readonly',str(c.root/'Replica/replica.duckdb'),'-c','SELECT count(*) AS n FROM vendite.ordine'],capture_output=True,text=True)
    c.check('Replica is empty and readable',rows.returncode==0 and json.loads(rows.stdout)[0]['n']==0,rows.stdout+rows.stderr)
    bad=write(c,'cattivo.sql',"ATTACH 'altro.duckdb' AS x; CREATE TABLE t(a INT);")
    denied=subprocess.run(['duckdb-cli','call','replicate',json.dumps({'input':str(bad),'output':str(c.root/'Denied')})],capture_output=True,text=True)
    c.check('Replica DDL cannot attach or read other files',denied.returncode!=0,denied.stderr[-300:])
    folder=c.root/'Files';folder.mkdir()
    (folder/'clienti.json').write_text(json.dumps([{'id':1,'nome':'Ada','citta':'Roma'},{'id':2,'nome':'Bruno','citta':None}]))
    (folder/'ordini.csv').write_text('id,clienti_id,importo\n10,1,12.5\n11,2,7.25\n12,1,3.00\n')
    (folder/'prodotti.xml').write_text('<catalogo><prodotto codice="A1"><nome>Penna</nome><prezzo>1.20</prezzo></prodotto><prodotto codice="B2"><nome>Matita</nome><prezzo>0.80</prezzo></prodotto></catalogo>')
    inferred=operation(c,'infer',input=str(folder),output=str(c.root/'Infer'))
    model_data=json.loads((c.root/'Infer/model.json').read_text());by_name={t['name']:t for t in model_data['tables']}
    c.check('Schema is inferred from JSON, CSV and XML files',inferred['tables']==3 and {'@codice','nome','prezzo'}<={col['name'] for col in by_name['prodotti']['columns']}
            and by_name['ordini']['rows']==3,inferred)
    c.check('Keys and references are only candidates',any('possibile chiave primaria' in n for n in inferred['notes']) and not any(t['primary_key'] for t in model_data['tables']),inferred['notes'])


def tbls(c):
    model=write(c,'model.json',json.dumps(MODEL))
    doc=operation(c,'document',input=str(model),output=str(c.root/'Catalog'))
    readme=(c.root/'Catalog/catalogo/README.md').read_text()
    c.check('Catalog pages and ER diagram are generated from the model',doc['status']=='passed' and doc['diagrams']>=1 and 'vendite.ordine' in readme and 'Ordini di vendita' in readme,doc)
    pages={p.name.lower():p.read_text() for p in (c.root/'Catalog/catalogo').glob('*.md')}
    ordine=next((v for k,v in pages.items() if 'ordine' in k),'');cliente=next((v for k,v in pages.items() if 'cliente' in k),'')
    c.check('Relations and personal data labels appear in the table pages','vendite.Cliente' in ordine and 'pii' in cliente,sorted(pages))
    undocumented=json.loads(json.dumps(MODEL));undocumented['tables'][0]['description']='';undocumented['tables'][1]['columns'][3]['description']=''
    lint=operation(c,'lint',input=str(write(c,'senza-descrizioni.json',json.dumps(undocumented))),output=str(c.root/'Lint'))
    findings=(c.root/'Lint/findings.txt').read_text()
    c.check('Missing descriptions are reported by the catalog linter',lint['status']=='failed' and 'Cliente' in findings,findings[-800:])


def faker(c):
    ddl=write(c,'replica.sql',DDL_DUCK);model=write(c,'model.json',json.dumps(MODEL));replica=c.root/'replica.duckdb'
    create_replica('faker',replica,ddl)
    first=operation(c,'generate',input=str(model),database=str(replica),formats=['duckdb','csv','parquet','jsonl','xml'],output=str(c.root/'Batch0'))
    second=operation(c,'generate',input=str(model),database=str(c.root/'Batch0/stub.duckdb'),output=str(c.root/'Batch1'))
    stub=c.root/'Batch1/stub.duckdb'
    orphans=duck('faker',stub,'SELECT count(*) FROM vendite.ordine o LEFT JOIN vendite."Cliente" c ON o.cliente_id=c."Id" WHERE c."Id" IS NULL')[0][0]
    totals=duck('faker',stub,'SELECT (SELECT count(*) FROM vendite."Cliente"),(SELECT count(*) FROM vendite.ordine),(SELECT count(DISTINCT id) FROM vendite.ordine),(SELECT min(importo) FROM vendite.ordine)')[0]
    c.check('Two periodic batches load with enforced foreign keys and no orphans',first['batch']==0 and second['batch']==1 and orphans==0 and totals[:3]==[40,120,120],totals)
    c.check('CHECK constraints guide values',float(totals[3])>=0 and {r[0] for r in duck('faker',stub,'SELECT DISTINCT stato FROM vendite.ordine WHERE stato IS NOT NULL')}<={'nuovo','pagato'},totals)
    again=c.root/'replica-again.duckdb';create_replica('faker',again,ddl)
    operation(c,'generate',input=str(model),database=str(again),batch=0,output=str(c.root/'Again'))
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    c.check('The same batch is reproduced byte for byte',digest(c.root/'Batch0/data/vendite/ordine.batch-00000.csv')==digest(c.root/'Again/data/vendite/ordine.batch-00000.csv'),'sha256')
    xml=(c.root/'Batch0/data/vendite/ordine.batch-00000.xml').read_text()
    c.check('Parquet, JSON Lines and XML are written for the batch',xml.count('<ordine>')==60 and (c.root/'Batch0/data/vendite/ordine.batch-00000.parquet').stat().st_size>0,len(xml))
    repeated=subprocess.run(['faker-cli','call','generate',json.dumps({'input':str(model),'database':str(stub),'batch':1,'output':str(c.root/'Repeat')})],capture_output=True,text=True)
    c.check('A batch already loaded is refused',repeated.returncode!=0 and 'già presente' in repeated.stderr,repeated.stderr[-300:])


def supercronic(c):
    good=write(c,'crontab','# pipeline\nPIPELINE_ENV=test\n*/30 * * * * /app/ops/run.sh stubs\n7 * * * * /app/ops/run.sh ingest\n@daily /app/ops/run.sh transform\n')
    result=operation(c,'validate',input=str(good),output=str(c.root/'Valid'))
    c.check('Valid crontab lists every job',result['status']=='passed' and len(result['jobs'])==3 and result['jobs'][2]['schedule']=='@daily',result['jobs'])
    bad=write(c,'crontab-bad','61 * * * * /app/ops/run.sh ingest\n')
    invalid=operation(c,'validate',input=str(bad),output=str(c.root/'Invalid'))
    c.check('Invalid schedule is rejected by supercronic',invalid['status']=='failed' and not invalid['valid'],invalid['native'][-300:])
    leaked=operation(c,'validate',input=str(write(c,'crontab-secret','DB_PASSWORD=x\n7 * * * * /app/ops/run.sh ingest\n')),output=str(c.root/'Secret'))
    c.check('Secrets in the crontab environment are flagged',leaked['status']=='failed' and leaked['secrets_in_crontab']==['DB_PASSWORD'],leaked['secrets_in_crontab'])


def dlt(c):
    import pipeline_scaffold
    project=c.root/'ingestion';project.mkdir()
    (project/'tables.json').write_text(json.dumps([{k:v for k,v in t.items() if k!='columns'} for t in pipeline_scaffold.plan_tables(MODEL)]))
    (project/'pipeline.py').write_text(pipeline_scaffold.PIPELINE.replace('{name}','vendite'))
    ddl=write(c,'replica.sql',DDL_DUCK);source=c.root/'source.duckdb';create_replica('dlt',source,ddl)
    code=("import duckdb,sys;c=duckdb.connect(sys.argv[1]);c.execute(\"INSERT INTO vendite.\\\"Cliente\\\" VALUES (1,'Ada',NULL,'2026-01-01 10:00'),(2,'Bruno','b@example.org','2026-01-02 11:00')\");"
          "c.execute(\"INSERT INTO vendite.ordine VALUES (10,1,12.50,'nuovo','2026-01-03 09:00'),(11,2,7.25,'pagato','2026-01-03 10:00'),(12,1,3.00,NULL,'2026-01-04 08:00')\");c.close()")
    subprocess.run([python('dlt'),'-c',code,str(source)],check=True,capture_output=True,text=True)
    result=operation(c,'run',input=str(project/'pipeline.py'),resource_dir=str(project),source_database=str(source),pipeline_env='test',output=str(c.root/'Run'))
    rows={t['table']:t['rows'] for t in result['tables']}
    c.check('The generated dlt pipeline loads the stub source into the local warehouse',rows.get('cliente')==2 and rows.get('ordine')==3 and result['dlt_loads']>=1,result['tables'])
    total=duck('dlt',c.root/'Run/warehouse.duckdb','SELECT sum(importo) FROM raw.ordine')[0][0]
    c.check('Loaded amounts reconcile with the source (22.75)',abs(float(total)-22.75)<1e-9,total)
    if (INSTALL/'apps/sqlmesh/venv/bin/python').is_file():
        readable=subprocess.run([python('sqlmesh'),'-c',"import duckdb,sys;print(duckdb.connect(sys.argv[1],read_only=True).execute('SELECT count(*) FROM raw.ordine').fetchone()[0])",str(c.root/'Run/warehouse.duckdb')],capture_output=True,text=True)
        c.check('The warehouse written by DuckDB 2 is readable by the SQLMesh DuckDB',readable.stdout.strip()=='3',readable.stderr[-300:])
    secret=c.root/'leaky';shutil.copytree(project,secret);(secret/'.env').write_text('X=1\n')
    denied=subprocess.run(['dlt-cli','call','run',json.dumps({'input':str(secret/'pipeline.py'),'resource_dir':str(secret),'source_database':str(source),'output':str(c.root/'Denied')})],capture_output=True,text=True)
    c.check('A project containing a credentials file is refused',denied.returncode!=0,denied.stderr[-300:])


def sqlmesh(c):
    project=c.root/'Gateways';(project/'models').mkdir(parents=True)
    config="gateways:\n  local:\n    connection:\n      type: duckdb\n      database: analytics.duckdb\n  prod:\n    connection:\n      type: postgres\n      host: \"{{ env_var('WAREHOUSE_HOST', 'localhost') }}\"\n      port: 5432\n      database: warehouse\n      user: sqlmesh\n      password: \"{{ env_var('WAREHOUSE_PASSWORD', '') }}\"\ndefault_gateway: local\nmodel_defaults:\n  dialect: duckdb\n  start: '2026-01-01'\n"
    (project/'config.yaml').write_text(config)
    (project/'models/total.sql').write_text('MODEL (name analytics.total, kind FULL); SELECT 40 + 2 AS total;')
    plan=operation(c,'plan',input=str(project/'config.yaml'),resource_dir=str(project),apply_local=True,output=str(c.root/'GatewayPlan'))
    result=json.loads((c.root/'GatewayPlan/result.json').read_text())
    c.check('A project with a production gateway runs only on the local gateway',result['gateway']=='local' and result['production_gateways']==['prod'],result)
    leaky=c.root/'Leaky';shutil.copytree(project,leaky);(leaky/'config.yaml').write_text(config.replace("\"{{ env_var('WAREHOUSE_PASSWORD', '') }}\"",'segreto'))
    denied=subprocess.run(['sqlmesh-cli','call','plan',json.dumps({'input':str(leaky/'config.yaml'),'resource_dir':str(leaky),'output':str(c.root/'Denied')})],capture_output=True,text=True)
    c.check('An inline production password is refused',denied.returncode!=0 and 'env_var' in denied.stderr,denied.stderr[-300:])
    if all((INSTALL/'apps'/a/'venv/bin/python').is_file() for a in ('sqlglot','faker','dlt')):end_to_end(c)


def end_to_end(c):
    """Model -> package -> replica -> two stub batches -> dlt run -> SQLMesh plan with audits -> reconciled mart."""
    ddl=write(c,'e2e/schema.sql',DDL_PG);doc=write(c,'e2e/documentazione.yaml',DOC)
    operation(c,'model',app='sqlglot',input=str(ddl),dialect='postgres',overrides=str(doc),output=str(c.root/'E2E/Model'))
    model=c.root/'E2E/Model/model.json'
    operation(c,'scaffold',app='sqlglot',input=str(model),dialect='postgres',name='vendite',output=str(c.root/'E2E/Package'))
    package=c.root/'E2E/Package/package';replica=c.root/'E2E/replica.duckdb'
    create_replica('faker',replica,package/'schema/replica.duckdb.sql')
    operation(c,'generate',app='faker',input=str(model),database=str(replica),output=str(c.root/'E2E/Stub0'))
    operation(c,'generate',app='faker',input=str(model),database=str(c.root/'E2E/Stub0/stub.duckdb'),output=str(c.root/'E2E/Stub1'))
    stub=c.root/'E2E/Stub1/stub.duckdb'
    run=operation(c,'run',app='dlt',input=str(package/'ingestion/pipeline.py'),resource_dir=str(package/'ingestion'),source_database=str(stub),pipeline_env='test',output=str(c.root/'E2E/Run'))
    plan=operation(c,'plan',input=str(package/'transform/config.yaml'),resource_dir=str(package/'transform'),warehouse=str(c.root/'E2E/Run/warehouse.duckdb'),
                   apply_local=True,output=str(c.root/'E2E/Plan'))
    warehouse=c.root/'E2E/Plan/project/warehouse.duckdb'
    marts=duck('sqlmesh',warehouse,"SELECT table_schema, table_name FROM information_schema.tables WHERE table_name='ordine_by_cliente' ORDER BY 1")
    c.check('The generated SQLMesh project applies on the loaded warehouse with its audits',plan['status']=='passed' and bool(marts),marts)
    schema,table=marts[0]
    reconciled=duck('sqlmesh',warehouse,'SELECT sum(ordine_count) FROM "'+schema+'"."'+table+'"')[0][0]
    loaded=next(t['rows'] for t in run['tables'] if t['table']=='ordine')
    c.check('The example mart reconciles with the loaded orders (two batches of 60)',int(reconciled)==loaded==120,{'mart':reconciled,'loaded':loaded})


CASES={'tbls':tbls,'faker':faker,'supercronic':supercronic}
EXTENSIONS={'sqlglot':sqlglot,'duckdb':duckdb,'dlt':dlt,'sqlmesh':sqlmesh}
