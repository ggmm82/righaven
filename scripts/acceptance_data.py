"""Real small database/data-engineering fixtures with known keys and totals."""
import hashlib,json,sqlite3,shutil
from pathlib import Path
try:from .acceptance_toolkit import call
except ImportError:from acceptance_toolkit import call


def database(root):
    path=root/'shop.sqlite'
    with sqlite3.connect(path) as db:
        db.executescript('CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL);CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),amount INTEGER NOT NULL);INSERT INTO customers VALUES(1,"Alice"),(2,"Bob");INSERT INTO orders VALUES(10,1,10),(11,1,20),(12,2,30);')
    return path


def usql(c):
    source=database(c.root);before=hashlib.sha256(source.read_bytes()).hexdigest()
    query=c.root/'query.sql';query.write_text('SELECT SUM(amount) AS total FROM orders;')
    output=c.root/'Query';call(c,'query',input=str(query),database=str(source),output=str(output),dialect='sqlite')
    data=json.loads((output/'query-result.json').read_text());c.check('Native multi-database SQL client returns the known total', '60' in json.dumps(data),data)
    c.check('Original database is unchanged',hashlib.sha256(source.read_bytes()).hexdigest()==before,'source checksum')


def schemacrawler(c):
    source=database(c.root);output=c.root/'Schema'
    call(c,'inspect',database=str(source),output=str(output),format='json')
    text=(output/'schema.json').read_text();data=json.loads(text)
    c.check('Actual JDBC schema contains declared foreign key and tables',all(value in text.lower() for value in ('customers','orders','customer_id','foreign')),list(data) if isinstance(data,dict) else type(data).__name__)


def dlt(c):
    source=database(c.root);output=c.root/'Metadata'
    call(c,'discover',database=str(source),output=str(output))
    data=json.loads((output/'result.json').read_text());orders=next(t for t in data['tables'] if t['name']=='orders')
    c.check('SQLAlchemy metadata preserves the actual declared relationship',orders['foreign_keys'][0]['referred_table']=='customers',orders['foreign_keys'])
    query=c.root/'query.sql';query.write_text('SELECT id, customer_id, amount FROM orders ORDER BY id;');extracted=c.root/'Extract'
    call(c,'extract',database=str(source),input=str(query),output=str(extracted),max_rows=100,dialect='sqlite')
    rows=[json.loads(line) for line in (extracted/'data.jsonl').read_text().splitlines()]
    c.check('Native dlt pipeline reconciles all bounded rows and total',len(rows)==3 and sum(row['amount'] for row in rows)==60 and (extracted/'data.duckdb').stat().st_size>0,rows)
    c.check('Native dlt schema and editable pipeline helper are retained',(extracted/'schema.yaml').is_file() and (extracted/'Sources/data_job.py').is_file(),'source and schema')


def sqlglot(c):
    source=c.root/'query.sql';source.write_text('SELECT o.customer_id, SUM(o.amount) AS total FROM orders AS o GROUP BY o.customer_id')
    schema=c.root/'schema.json';schema.write_text(json.dumps({'orders':{'customer_id':'INTEGER','amount':'INTEGER'}}));output=c.root/'Lineage'
    call(c,'analyze',input=str(source),schema=str(schema),output=str(output),dialect='sqlite')
    data=json.loads((output/'result.json').read_text());lineage=next(item for item in data['lineage'] if item['output']=='total')
    c.check('Column lineage comes from real SQL and schema',data['tables']==['orders'] and any('amount' in node['name'] for node in lineage['nodes']),lineage)


def sqlmesh(c):
    project=c.root/'Project';project.mkdir();(project/'models').mkdir();(project/'tests').mkdir()
    config=project/'config.yaml';config.write_text("gateways:\n  local:\n    connection:\n      type: duckdb\n      database: analytics.duckdb\ndefault_gateway: local\nmodel_defaults:\n  dialect: duckdb\n  start: '2026-01-01'\n")
    (project/'models/total.sql').write_text('MODEL (name analytics.total, kind FULL); SELECT 10 + 20 + 30 AS total;')
    (project/'tests/test_total.yaml').write_text('test_total:\n  model: analytics.total\n  outputs:\n    query:\n      rows:\n        - total: 60\n')
    output=c.root/'Plan';call(c,'plan',input=str(config),resource_dir=str(project),output=str(output),apply_local=True)
    import subprocess
    probe="import duckdb; from pathlib import Path; db=duckdb.connect('analytics.duckdb',read_only=True); tables=db.sql(\"SELECT table_schema,table_name FROM information_schema.tables WHERE table_name='total'\").fetchall(); assert tables,tables; values=[db.execute('SELECT total FROM \"'+schema+'\".\"'+table+'\"').fetchall() for schema,table in tables]; assert any(rows==[(60,)] for rows in values),values; print('reconciled total 60')"
    verified=subprocess.run(['/opt/righaven/apps/sqlmesh/venv/bin/python','-c',probe],cwd=output/'project',capture_output=True,text=True)
    c.check('Applied transformation independently reconciles the known total',verified.returncode==0,verified.stdout+verified.stderr)
    c.check('Native SQLMesh applies a local tested transformation project' ,(output/'project/analytics.duckdb').is_file() and (output/'project/models/total.sql').is_file(),'local source and analytical state; no remote deployment')

CASES={name:globals()[name] for name in ('usql','schemacrawler','dlt','sqlglot','sqlmesh')}
