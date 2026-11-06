"""Refresh only the isolated PostgreSQL source service of an exported test lab.

Production sources are never written by this program. No RigHaven dependency.
"""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit


def main():
    if os.environ.get('PIPELINE_ENV') != 'lab':
        raise ValueError('Native synthetic source refresh is only available in lab mode')
    url=os.environ['SOURCES__SQL_DATABASE__CREDENTIALS']
    endpoint=urlsplit(url)
    if endpoint.hostname != 'source-db' or endpoint.path != '/source_lab':
        raise ValueError('Synthetic refresh is restricted to the isolated source-db/source_lab service')
    import duckdb
    from sqlalchemy import create_engine,text
    root=Path(os.environ.get('APP_DIR','/app'))
    model=json.loads((root/'schema/model.json').read_text())
    quote=lambda name:'"'+name.replace('"','""')+'"'
    import sys
    sys.path.insert(0,str(root/'stubs'))
    from stubgen import order
    tables=order([t for t in model['tables'] if t.get('kind','table')=='table'])
    name=lambda t:(quote(t['schema'])+'.' if t['schema'] else '')+quote(t['name'])
    engine=create_engine(url)
    try:
        with engine.begin() as destination,duckdb.connect(os.environ['RIGHAVEN_SOURCE_DUCKDB'],read_only=True) as source:
            destination.exec_driver_sql('TRUNCATE TABLE '+', '.join(name(t) for t in tables))
            # Deferring constraints permits documented FK order, including forward references.
            destination.exec_driver_sql('SET CONSTRAINTS ALL DEFERRED')
            for table in tables:
                rows=source.execute('SELECT * FROM '+name(table));columns=[c[0] for c in rows.description]
                statement=text('INSERT INTO '+name(table)+' ('+', '.join(map(quote,columns))+') VALUES ('+', '.join(':c'+str(i) for i in range(len(columns)))+')')
                while batch:=rows.fetchmany(1000):
                    destination.execute(statement,[{'c'+str(i):value for i,value in enumerate(row)} for row in batch])
    finally:engine.dispose()
    print('Synthetic snapshot copied into the isolated PostgreSQL source')


if __name__=='__main__':main()
