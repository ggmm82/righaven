"""Native data-library operations executed in their own pinned Python environment."""
import json,os,re,sys
from pathlib import Path


def read_query(path,dialect=None):
    import sqlglot
    from sqlglot import exp
    text=Path(path).read_text()
    trees=sqlglot.parse(text,read=dialect or None)
    blocked=(exp.Insert,exp.Update,exp.Delete,exp.Create,exp.Drop,exp.Alter,exp.Command,exp.Copy)
    if len(trees)!=1 or trees[0] is None or not isinstance(trees[0],exp.Query) or any(isinstance(node,blocked) for node in trees[0].walk()):
        raise ValueError('Only one SELECT/CTE query is permitted; use a read-only database account')
    return trees[0],text


def connection(spec):
    return json.loads(Path(os.environ['RIGHAVEN_DATA_CONNECTION_FILE']).read_text())


def sqlalchemy_engine(cfg):
    from sqlalchemy import create_engine
    return create_engine(cfg['url'],pool_pre_ping=True)


def discover(cfg):
    if cfg['url'].startswith(('mongodb://','mongodb+srv://')):
        from pymongo import MongoClient
        client=MongoClient(cfg['url'],serverSelectionTimeoutMS=15000)
        try:
            database=client.get_default_database();collections=[]
            for name in sorted(database.list_collection_names())[:200]:
                fields={}
                for doc in database[name].find().limit(5):
                    for key,value in doc.items():fields.setdefault(key,set()).add(type(value).__name__)
                collections.append({'name':name,'sampled_fields':{k:sorted(v) for k,v in fields.items()}})
            return {'kind':'mongodb','collections':collections,'limits':['Five sampled documents per collection; field types and relationships are not a complete schema.']}
        finally:client.close()
    from sqlalchemy import inspect
    engine=sqlalchemy_engine(cfg)
    system={'information_schema','pg_catalog','pg_toast','sys','guest','db_owner','db_accessadmin','db_securityadmin','db_ddladmin','db_backupoperator',
            'db_datareader','db_datawriter','db_denydatareader','db_denydatawriter','mysql','performance_schema','sys','temp'}
    def optional(call,default):
        try:return call()
        except NotImplementedError:return default
        except Exception as error:
            if 'not implemented' in str(error).lower():return default
            raise
    try:
        inspector=inspect(engine);tables=[];limit=1000
        default=inspector.default_schema_name
        schemas=[s for s in optional(inspector.get_schema_names,[default]) if s and s.lower() not in system and not s.lower().startswith(('pg_temp','pg_toast'))]
        if default and default not in schemas:schemas.insert(0,default)
        names=[]
        for schema in schemas:
            names+=[(schema,n,'table') for n in inspector.get_table_names(schema=schema)]
            names+=[(schema,n,'view') for n in optional(lambda:inspector.get_view_names(schema=schema),[])]
        single=len(schemas)==1
        for schema,name,kind in names[:limit]:
            columns=[{'name':c['name'],'type':str(c['type']),'nullable':c.get('nullable'),'default':str(c['default']) if c.get('default') is not None else None,
                      'comment':c.get('comment') or ''} for c in inspector.get_columns(name,schema=schema)]
            entry={'schema':'' if single and schema==default else schema,'name':name,'kind':kind,'columns':columns,
                   'comment':(optional(lambda:inspector.get_table_comment(name,schema=schema),{}) or {}).get('text') or ''}
            if kind=='table':
                entry.update(primary_key=inspector.get_pk_constraint(name,schema=schema),foreign_keys=inspector.get_foreign_keys(name,schema=schema),
                             unique_constraints=optional(lambda:inspector.get_unique_constraints(name,schema=schema),[]),
                             check_constraints=optional(lambda:inspector.get_check_constraints(name,schema=schema),[]))
                declared={tuple(u.get('column_names') or []) for u in entry['unique_constraints']}
                for index in optional(lambda:inspector.get_indexes(name,schema=schema),[]):
                    columns_=tuple(c for c in index.get('column_names') or [] if c)
                    if index.get('unique') and columns_ and columns_ not in declared and list(columns_)!=list(entry['primary_key'].get('constrained_columns') or []):
                        entry['unique_constraints'].append({'name':index.get('name'),'column_names':list(columns_)});declared.add(columns_)
                for fk in entry['foreign_keys']:
                    if single and fk.get('referred_schema') in (None,default):fk['referred_schema']=''
            tables.append(entry)
        return {'kind':'sql','dialect':engine.dialect.name,'database':(engine.url.database or '').rsplit('/',1)[-1] or 'database','schemas':schemas,
                'tables':tables,'truncated':len(names)>limit,
                'limits':['Declared metadata is observed; business meaning and undeclared relationships require validation.']}
    finally:engine.dispose()


def extract(spec,cfg,output):
    import dlt
    maximum=spec.get('max_rows',10000);table=spec.get('table','records')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}',table):raise ValueError('Choose a simple lower-case table name')
    if cfg:
        if cfg['url'].startswith(('mongodb://','mongodb+srv://')):
            from pymongo import MongoClient
            client=MongoClient(cfg['url'],serverSelectionTimeoutMS=15000)
            try:rows=list(client.get_default_database()[table].find().limit(maximum))
            finally:client.close()
            rows=json.loads(json.dumps(rows,default=str))
        else:
            from sqlalchemy import text
            _,query=read_query(spec['input'],spec.get('dialect'))
            engine=sqlalchemy_engine(cfg)
            try:
                with engine.connect() as session:rows=[dict(row) for row in session.execute(text(query)).mappings().fetchmany(maximum)]
            finally:engine.dispose()
    else:
        source=Path(spec['input'])
        if source.suffix.lower()=='.csv':
            import csv
            with source.open(newline='') as stream:
                import itertools
                rows=list(itertools.islice(csv.DictReader(stream),maximum))
        else:
            value=json.loads(source.read_text())
            if not isinstance(value,list) or any(not isinstance(row,dict) for row in value):raise ValueError('Provide a JSON list of records or a CSV file')
            rows=value[:maximum]
    # Portable snapshots avoid DuckDB file-format incompatibilities across tools.
    (output/'data.jsonl').write_text(''.join(json.dumps(row,default=str)+'\n' for row in rows))
    pipeline=dlt.pipeline(pipeline_name='righaven_extract',destination=dlt.destinations.duckdb(str(output/'data.duckdb')),dataset_name='righaven',pipelines_dir=str(output/'work/pipelines'))
    pipeline.run(rows,table_name=table,write_disposition='replace')
    (output/'schema.yaml').write_text(pipeline.default_schema.to_pretty_yaml())
    return {'extracted_rows':len(rows),'row_limit':maximum,'destination':'data.duckdb','portable_snapshot':'data.jsonl','table':table,'limits':['Extraction is bounded and not a transactionally consistent full database backup.']}


def analyze(spec,output):
    import sqlglot
    from sqlglot import exp
    tree=sqlglot.parse_one(Path(spec['input']).read_text(),read=spec.get('dialect') or None)
    tables=sorted({table.name for table in tree.find_all(exp.Table)})
    (output/'normalized.sql').write_text(tree.sql(pretty=True))
    lineage=[];limits=[]
    if spec.get('schema'):
        from sqlglot.lineage import lineage as derive
        schema=json.loads(Path(spec['schema']).read_text())
        for name in tree.named_selects:
            if name=='*':limits.append('Wildcard lineage requires schema expansion');continue
            node=derive(name,tree,schema=schema,dialect=spec.get('dialect') or None)
            lineage.append({'output':name,'nodes':[{'name':n.name,'expression':n.expression.sql()} for n in node.walk()]})
    else:limits.append('Column lineage not established: supply actual table/column schema, not invented types.')
    return {'tables':tables,'columns':tree.named_selects,'lineage':lineage,'limits':limits}


def main():
    spec=json.loads(Path(sys.argv[1]).read_text());output=Path(spec['output'])
    if spec['action']=='validate_sql':
        tree,text=read_query(spec['input'],spec.get('dialect'));result={'valid':True,'query':text}
    elif spec['app']=='sqlglot':result=analyze(spec,output)
    elif spec['action']=='discover':result=discover(connection(spec))
    else:result=extract(spec,connection(spec) if os.environ.get('RIGHAVEN_DATA_CONNECTION_FILE') else None,output)
    (output/'result.json').write_text(json.dumps(result,default=str,indent=2))
    print(json.dumps({'status':'passed','result':'result.json'}))

if __name__=='__main__':main()
