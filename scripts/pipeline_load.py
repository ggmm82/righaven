#!/usr/bin/env python3
"""Load verified local DuckDB tables into the write-enabled schema of a user connection.

Runs in the dlt environment (DuckDB, SQLAlchemy and database drivers). Two writers:
- SQLAlchemy URL (PostgreSQL, MySQL/MariaDB, SQL Server with SQL user, Oracle; SQLite in tests);
- Microsoft account connections (Azure SQL, Fabric) only have an access-token usql URL:
  this script writes a T-SQL script that the caller runs with usql.
Only the listed tables are written, only into the schema the owner enabled for writing.
"""
import datetime
import decimal
import json
import re
import sys
from pathlib import Path

import duckdb

NAME = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,127}\Z')
MAX_ROWS = 1_000_000
BATCH = 500


def source_name(table):
    """'mart' or 'schema.mart' in the local database; the destination table keeps the last part."""
    parts = table.split('.')
    if not 1 <= len(parts) <= 2 or not all(NAME.fullmatch(p) for p in parts):
        raise ValueError('Invalid table name: ' + table)
    return ('main', parts[0]) if len(parts) == 1 else (parts[0], parts[1])


def quoted(table):
    schema, name = source_name(table)
    return '"' + schema + '"."' + name + '"'


def columns(source, table):
    return [(name, kind.upper()) for name, kind, *_ in source.execute('DESCRIBE ' + quoted(table)).fetchall()]


def sqlalchemy_type(kind, sa, dialect):
    if kind == 'BOOLEAN':
        return sa.Boolean()
    if kind in ('TINYINT', 'SMALLINT', 'INTEGER', 'UTINYINT', 'USMALLINT'):
        return sa.Integer()
    if kind in ('BIGINT', 'HUGEINT', 'UINTEGER', 'UBIGINT'):
        return sa.BigInteger()
    if kind in ('DOUBLE', 'FLOAT', 'REAL'):
        return sa.Float()
    match = re.fullmatch(r'DECIMAL\((\d+),\s*(\d+)\)', kind)
    if match:
        return sa.Numeric(int(match[1]), int(match[2]))
    if kind == 'DATE':
        return sa.Date()
    if kind.startswith('TIMESTAMP'):
        return sa.DateTime(timezone='TIME ZONE' in kind)
    if kind.startswith('TIME'):
        return sa.Time()
    # MySQL needs a bounded VARCHAR; long text goes to TEXT there.
    return sa.Text() if dialect == 'mysql' else sa.String(4000)


def write_sqlalchemy(source, tables, url, schema, mode):
    import sqlalchemy as sa
    engine = sa.create_engine(url)
    dialect = engine.dialect.name
    report = []
    with engine.begin() as target:
        for table in tables:
            spec = sa.Table(source_name(table)[1], sa.MetaData(), *[sa.Column(name, sqlalchemy_type(kind, sa, dialect)) for name, kind in columns(source, table)],
                            schema=None if dialect == 'sqlite' else schema)
            if mode == 'replace':
                spec.drop(target, checkfirst=True)
            spec.create(target, checkfirst=True)
            rows, cursor = 0, source.execute('SELECT * FROM ' + quoted(table))
            names = [c.name for c in spec.columns]
            while batch := cursor.fetchmany(BATCH):
                target.execute(spec.insert(), [dict(zip(names, row)) for row in batch])
                rows += len(batch)
            report.append({'table': table, 'target': spec.name, 'rows': rows, 'columns': len(names)})
    engine.dispose()
    return report


def tsql_type(kind):
    match = re.fullmatch(r'DECIMAL\((\d+),\s*(\d+)\)', kind)
    return ('BIT' if kind == 'BOOLEAN' else 'INT' if kind in ('TINYINT', 'SMALLINT', 'INTEGER', 'UTINYINT', 'USMALLINT')
            else 'BIGINT' if kind in ('BIGINT', 'HUGEINT', 'UINTEGER', 'UBIGINT') else 'FLOAT' if kind in ('DOUBLE', 'FLOAT', 'REAL')
            else f'DECIMAL({match[1]},{match[2]})' if match else 'DATE' if kind == 'DATE' else 'DATETIME2(6)' if kind.startswith('TIMESTAMP')
            else 'TIME(6)' if kind.startswith('TIME') else 'VARCHAR(8000)')


def literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float, decimal.Decimal)):
        return repr(value) if isinstance(value, float) else str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return "'" + value.isoformat(sep=' ') + "'" if isinstance(value, datetime.datetime) else "'" + value.isoformat() + "'"
    return "'" + str(value).replace("'", "''") + "'"


def write_tsql(source, tables, schema, mode, script):
    """T-SQL for SQL Server, Azure SQL and Fabric Warehouse, run by usql with the account's access token."""
    report, lines = [], ['SET NOCOUNT ON;']
    for table in tables:
        cols = columns(source, table)
        name = source_name(table)[1]
        target = f'[{schema}].[{name}]'
        if mode == 'replace':
            lines.append(f"IF OBJECT_ID('{schema}.{name}', 'U') IS NOT NULL DROP TABLE {target};")
            lines.append(f"CREATE TABLE {target} ({', '.join(f'[{n}] {tsql_type(k)}' for n, k in cols)});")
        else:
            lines.append(f"IF OBJECT_ID('{schema}.{name}', 'U') IS NULL CREATE TABLE {target} ({', '.join(f'[{n}] {tsql_type(k)}' for n, k in cols)});")
        rows, cursor = 0, source.execute('SELECT * FROM ' + quoted(table))
        names = ', '.join(f'[{n}]' for n, _ in cols)
        while batch := cursor.fetchmany(BATCH):
            lines.append(f'INSERT INTO {target} ({names}) VALUES ' + ', '.join('(' + ', '.join(literal(v) for v in row) + ')' for row in batch) + ';')
            rows += len(batch)
        report.append({'table': table, 'target': name, 'rows': rows, 'columns': len(cols)})
    Path(script).write_text('\n'.join(lines) + '\n')
    return report


def main(request_path):
    request = json.loads(Path(request_path).read_text())
    connection = json.loads(Path(request['connection_file']).read_text())
    schema, mode, tables = connection['write_schema'], request['mode'], request['tables']
    if not NAME.fullmatch(schema) or mode not in ('replace', 'append') or not tables:
        raise ValueError('Invalid load request')
    wanted = [source_name(t) for t in tables]
    if len({name for _, name in wanted}) != len(wanted):
        raise ValueError('Two tables would get the same name in the destination')
    source = duckdb.connect(request['database'], read_only=True)
    present = set(source.execute('SELECT table_schema, table_name FROM information_schema.tables').fetchall())
    missing = sorted('.'.join(w) for w in wanted if w not in present)
    if missing:
        raise ValueError('Tables not found in the local database: ' + ', '.join(missing))
    total = sum(source.execute('SELECT count(*) FROM ' + quoted(t)).fetchone()[0] for t in tables)
    if total > MAX_ROWS:
        raise ValueError(f'{total} rows exceed the {MAX_ROWS} rows a single load may write')
    if connection.get('url'):
        report = write_sqlalchemy(source, tables, connection['url'], schema, mode)
        writer = 'sqlalchemy'
    else:
        report = write_tsql(source, tables, schema, mode, request['script'])
        writer = 'usql'
    print(json.dumps({'writer': writer, 'tables': report, 'schema': schema, 'mode': mode, 'rows': total}))


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except ValueError as error:
        print(str(error), file=sys.stderr)
        sys.exit(3)
