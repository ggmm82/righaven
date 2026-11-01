"""Bounded database discovery, extraction, SQL analysis and local transformation."""
try:from .schema_types import tool,STRING
except ImportError:from schema_types import tool,STRING
BOOL={'type':'boolean'}
CONNECTION={'database':STRING,'connection_file':STRING,'connection_env':STRING,'authorized':BOOL}

def operation(app,name,description,fields,required):
    return tool(app,name,description,{'output':STRING,**fields},['output',*required])

TOOLS={
 'usql':[operation('usql','query','Run a validated SELECT with the native universal SQL client. Use a read-only connection; retain SQL and result JSON, never connection secrets.',{'input':STRING,'dialect':STRING,**CONNECTION},['input'])],
 'schemacrawler':[operation('schemacrawler','inspect','Reverse engineer actual database schema, keys, constraints and associations with JDBC. Inferred relations remain hypotheses.',{**CONNECTION,'format':{'type':'string','enum':['json','html','dot']},'schemas':STRING},[])],
 'dlt':[
  operation('dlt','discover','Inspect SQL metadata with SQLAlchemy or MongoDB collection structure. Produce editable schema JSON; sampling is not complete semantic understanding.',{**CONNECTION},[]),
  operation('dlt','extract','Extract bounded local JSON/CSV or authorized read-only SQL/MongoDB data into a private DuckDB pipeline. Preserve pipeline, schema, receipt and reconciliation.',{'input':STRING,'table':STRING,'dialect':STRING,'max_rows':{'type':'integer','minimum':1,'maximum':100000},**CONNECTION},[])],
 'sqlglot':[operation('sqlglot','analyze','Parse and normalize SQL and derive actual table/column lineage where schema is available; do not invent business meaning or execute SQL.',{'input':STRING,'dialect':STRING,'schema':STRING},['input'])],
 'sqlmesh':[operation('sqlmesh','plan','Validate tests and explain a SQL/Python transformation project in an isolated local DuckDB environment. Apply only with apply_local=true; never auto-apply to a remote database.',{'input':STRING,'resource_dir':STRING,'apply_local':BOOL,'gateway':STRING,'warehouse':STRING},['input','resource_dir'])],
}
