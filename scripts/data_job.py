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
    try:
        inspector=inspect(engine);tables=[]
        names=inspector.get_table_names()
        for name in names[:200]:
            columns=[{'name':c['name'],'type':str(c['type']),'nullable':c.get('nullable')} for c in inspector.get_columns(name)]
            tables.append({'name':name,'columns':columns,'primary_key':inspector.get_pk_constraint(name),'foreign_keys':inspector.get_foreign_keys(name),'unique_constraints':inspector.get_unique_constraints(name)})
        return {'kind':'sql','tables':tables,'truncated':len(names)>200,'limits':['Declared metadata is observed; business meaning and undeclared relationships require validation.']}
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
