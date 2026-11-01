"""Writing verified tables into an owner-enabled schema: SQLAlchemy targets and the T-SQL script for Microsoft accounts."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    import duckdb
    import sqlalchemy
except ImportError:
    duckdb = None


@unittest.skipIf(duckdb is None, 'Requires DuckDB and SQLAlchemy (the dlt environment)')
class PipelineLoadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'marts.duckdb'
        with duckdb.connect(str(self.source)) as db:
            db.execute("CREATE TABLE vendite_mese (mese DATE, regione VARCHAR, fatturato DECIMAL(12,2), ordini BIGINT, chiuso BOOLEAN)")
            db.execute("INSERT INTO vendite_mese VALUES ('2026-01-01','Nord',1234.50,12,true),('2026-02-01','Sud',99.90,1,false),('2026-03-01','Isole d''Italia',NULL,0,NULL)")

    def load(self, connection, tables=('vendite_mese',), mode='replace'):
        path = self.root / 'connection.json'; path.write_text(json.dumps(connection))
        request = self.root / 'request.json'
        request.write_text(json.dumps({'connection_file': str(path), 'database': str(self.source), 'tables': list(tables), 'mode': mode,
                                       'script': str(self.root / 'load.sql')}))
        return subprocess.run([sys.executable, str(ROOT / 'scripts/pipeline_load.py'), str(request)], capture_output=True, text=True)

    def test_sqlalchemy_target_replace_and_append(self):
        target = self.root / 'target.sqlite'
        connection = {'kind': 'postgres', 'url': 'sqlite:///' + str(target), 'write_enabled': True, 'write_schema': 'main'}
        result = self.load(connection)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout.strip().splitlines()[-1])
        self.assertEqual((report['writer'], report['rows'], report['tables'][0]['columns']), ('sqlalchemy', 3, 5))
        self.assertEqual(self.load(connection, mode='append').returncode, 0)
        engine = sqlalchemy.create_engine('sqlite:///' + str(target))
        with engine.connect() as db:
            self.assertEqual(db.exec_driver_sql('SELECT count(*) FROM vendite_mese').scalar(), 6)
        self.assertEqual(self.load(connection).returncode, 0)
        with engine.connect() as db:
            self.assertEqual(db.exec_driver_sql('SELECT count(*) FROM vendite_mese').scalar(), 3, 'replace rewrites the table')

    def test_microsoft_account_target_gets_a_tsql_script_for_usql(self):
        connection = {'kind': 'sqlserver', 'usql_url': 'azuresql://x@srv.datawarehouse.fabric.microsoft.com:1433?database=wh', 'write_enabled': True, 'write_schema': 'righaven'}
        result = self.load(connection)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout.strip().splitlines()[-1])['writer'], 'usql')
        script = (self.root / 'load.sql').read_text()
        self.assertIn("IF OBJECT_ID('righaven.vendite_mese', 'U') IS NOT NULL DROP TABLE [righaven].[vendite_mese];", script)
        self.assertIn('[fatturato] DECIMAL(12,2)', script)
        self.assertIn("'Isole d''Italia'", script)
        self.assertIn("('2026-01-01', 'Nord', 1234.50, 12, 1)", script)

    def test_refuses_unknown_tables_bad_names_and_too_many_rows(self):
        connection = {'kind': 'postgres', 'url': 'sqlite:///' + str(self.root / 't.sqlite'), 'write_enabled': True, 'write_schema': 'main'}
        self.assertEqual(self.load(connection, tables=('inesistente',)).returncode, 3)
        self.assertEqual(self.load(connection, tables=('x; DROP TABLE y',)).returncode, 3)
        self.assertEqual(self.load(connection, tables=('main.vendite_mese',)).returncode, 0, 'schema.table names are accepted')
        self.assertEqual(self.load(connection, tables=('a.b.c',)).returncode, 3)
        self.assertEqual(self.load({**connection, 'write_schema': 'a b'}).returncode, 3)


if __name__ == '__main__':
    unittest.main()
