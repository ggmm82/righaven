"""Operations of the end-to-end data pipeline recipe: model, replica, catalog, stub data, schedule, ingestion run."""
try:from .schema_types import tool,STRING
except ImportError:from schema_types import tool,STRING

BOOL={'type':'boolean'}
DIALECTS=['postgres','tsql','mysql','oracle','sqlite','duckdb','fabric','snowflake','bigquery','databricks','redshift']
TARGETS=['duckdb','postgres','tsql','fabric','mysql','oracle','sqlite']


def op(app,name,description,fields,required):
    return tool(app,name,description,{'output':STRING,**fields},['output',*required])


# Extra operations of tools that already exist in the catalog.
EXTRA={
 'sqlglot':[
  op('sqlglot','model','Build the engine-neutral schema model (tables, portable types, keys, descriptions, PII, stub hints) from dlt discover metadata, DDL in any dialect or a documented model, then apply documentation overrides. Observed structure is never silently changed.',
     {'input':STRING,'dialect':{'type':'string','enum':DIALECTS},'overrides':STRING,'name':STRING,'strict_references':BOOL},['input']),
  op('sqlglot','ddl','Generate ordered, re-parsed DDL for a target engine from the schema model; constraints the engine cannot enforce are reported, not hidden.',
     {'input':STRING,'dialect':{'type':'string','enum':TARGETS},'comments':BOOL},['input','dialect']),
  op('sqlglot','scaffold','Generate the production package from the schema model: dlt ingestion with incremental cursors, SQLMesh staging views with key audits and an example mart, local and production gateways (PostgreSQL, SQL Server, Fabric or DuckDB), periodic stub job, supercronic crontab, locked job runner, Dockerfile, compose, CI and runbook. No secret values are written.',
     {'input':STRING,'dialect':{'type':'string','enum':['postgres','tsql','fabric','duckdb']},'source_dialect':{'type':'string','enum':DIALECTS},'name':STRING,
      'ingest_cron':STRING,'transform_cron':STRING,'stubs_cron':STRING,'model_cron':{'type':'string','enum':['@hourly','@daily','@weekly']}},['input','dialect'])],
 'duckdb':[
  op('duckdb','replicate','Create an empty local DuckDB replica from DuckDB DDL and verify tables, columns and keys against the schema model.',{'input':STRING,'model':STRING},['input']),
  op('duckdb','infer','Infer a schema model from JSON, JSON Lines, Parquet, CSV or XML files (a file or a folder of files); XML records become JSON Lines first.',
     {'input':STRING,'name':STRING,'record':STRING},['input'])],
 'dlt':[
  op('dlt','run','Run a project dlt pipeline locally against a stub source database and a local DuckDB destination; production credentials are never used.',
     {'input':STRING,'resource_dir':STRING,'source_database':STRING,'pipeline_env':{'type':'string','enum':['local','test']}},['input','resource_dir','source_database'])],
}

TOOLS={
 'tbls':[
  op('tbls','document','Generate the data catalog from the schema model: Markdown pages per table, ER diagram, relations, labels and description coverage.',
     {'input':STRING,'er_format':{'type':'string','enum':['svg','mermaid']}},['input']),
  op('tbls','lint','Check the schema model against catalog rules (table and column descriptions, primary keys, unrelated tables, column count) and save the findings.',
     {'input':STRING,'require_column_comments':BOOL,'max_columns':{'type':'integer','minimum':5,'maximum':1000}},['input'])],
 'faker':[
  op('faker','generate','Generate deterministic, foreign-key consistent stub data from the schema model for a batch (periodic runs use increasing batch numbers) into a DuckDB copy and Parquet/CSV/JSON Lines/XML files. Data is synthetic; PII columns are always fake.',
     {'input':STRING,'database':STRING,'rows':{'type':'integer','minimum':1,'maximum':100000},'batch':{'type':'integer','minimum':0,'maximum':100000},
      'seed':{'type':'integer','minimum':0,'maximum':2147483647},'locale':{'type':'string','enum':['it_IT','en_US','de_DE','fr_FR','es_ES']},
      'formats':{'type':'array','items':{'type':'string','enum':['duckdb','parquet','csv','jsonl','xml']},'minItems':1,'uniqueItems':True}},['input'])],
 'supercronic':[
  op('supercronic','validate','Validate a crontab with supercronic and list each job with its schedule; nothing is executed.',{'input':STRING},['input'])],
}
