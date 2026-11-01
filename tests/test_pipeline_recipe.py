"""Pure-Python parts of the data pipeline recipe (no SQLGlot, Faker or DuckDB needed)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import pipeline_scaffold  # noqa: E402
import pipeline_tools  # noqa: E402
import stubgen  # noqa: E402
from acceptance_pipeline import MODEL  # noqa: E402


class NamingAndCursors(unittest.TestCase):
    def test_dlt_snake_case(self):
        cases = {'Cliente': 'cliente', 'ClienteId': 'cliente_id', 'ClienteID': 'cliente_id', 'updated_at': 'updated_at',
                 'Data Ordine': 'data_ordine', '2fa': '_2fa', 'HTTPServer': 'http_server'}
        for name, expected in cases.items():
            self.assertEqual(pipeline_scaffold.snake(name), expected, name)

    def test_cursor_requires_not_null_timestamp(self):
        tables = {t['target']: t for t in pipeline_scaffold.plan_tables(MODEL)}
        self.assertEqual(tables['ordine']['cursor'], 'updated_at')
        self.assertIsNone(tables['cliente']['cursor'], 'Creato is a created timestamp but the table has no modified one')
        nullable = json.loads(json.dumps(MODEL))
        nullable['tables'][1]['columns'][4]['nullable'] = True
        self.assertIsNone({t['target']: t for t in pipeline_scaffold.plan_tables(nullable)}['ordine']['cursor'])
        self.assertEqual(tables['ordine']['write_disposition'], 'replace')
        self.assertFalse(tables['ordine']['cursor_confirmed'])

    def test_multi_schema_targets_are_prefixed(self):
        model = json.loads(json.dumps(MODEL))
        model['tables'][0]['schema'] = 'anagrafica'
        targets = {t['target'] for t in pipeline_scaffold.plan_tables(model)}
        self.assertEqual(targets, {'anagrafica_cliente', 'vendite_ordine'}, 'dlt reduces repeated underscores')


class StubHints(unittest.TestCase):
    def test_simple_checks_become_hints(self):
        table = MODEL['tables'][1]
        hints, skipped = stubgen.hints_from_checks(table)
        self.assertEqual(hints['stato']['values'], ['nuovo', 'pagato'])
        self.assertEqual(hints['importo']['min'], 0)
        self.assertEqual(skipped, [])
        odd = {**table, 'checks': [{'name': '', 'expression': 'length(stato) = 5 OR stato IS NULL'}]}
        self.assertEqual(len(stubgen.hints_from_checks(odd)[1]), 1, 'unsupported CHECK is reported, not guessed')

    def test_parents_before_children(self):
        names = [t['name'] for t in stubgen.order(list(reversed(MODEL['tables'])))]
        self.assertEqual(names, ['Cliente', 'ordine'])

    def test_rows_are_pure_functions_of_seed_table_batch_row(self):
        self.assertEqual(stubgen.stable(1, 'vendite.ordine', 0, 5), stubgen.stable(1, 'vendite.ordine', 0, 5))
        self.assertNotEqual(stubgen.stable(1, 'vendite.ordine', 0, 5), stubgen.stable(1, 'vendite.ordine', 1, 5))


class CatalogAndInputs(unittest.TestCase):
    def test_tbls_schema_from_model(self):
        model = json.loads(json.dumps(MODEL))
        model['tables'][1]['foreign_keys'].append({'columns': ['stato'], 'references': {'schema': 'vendite', 'table': 'Cliente', 'columns': ['Id']}, 'declared': False})
        schema = pipeline_tools.tbls_schema(model)
        tables = {t['name']: t for t in schema['tables']}
        self.assertEqual({c['type'] for c in tables['vendite.ordine']['constraints']}, {'PRIMARY KEY', 'FOREIGN KEY'})
        self.assertEqual([r['virtual'] for r in schema['relations']], [False, True])
        self.assertIn({'name': 'pii', 'virtual': True}, next(c for c in tables['vendite.Cliente']['columns'] if c['name'] == 'Nome')['labels'])
        self.assertEqual(schema['relations'][0]['parent_cardinality'], 'exactly_one')

    def test_xml_records_become_json_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'prodotti.xml'
            source.write_text('<catalogo><prodotto codice="A1"><nome>Penna</nome><dettagli><colore>blu</colore></dettagli></prodotto>'
                              '<prodotto codice="B2"><nome>Matita</nome></prodotto></catalogo>')
            target = Path(folder) / 'prodotti.jsonl'
            tag, count = pipeline_tools.xml_to_jsonl(source, target)
            rows = [json.loads(line) for line in target.read_text().splitlines()]
            self.assertEqual((tag, count), ('prodotto', 2))
            self.assertEqual(rows[0]['@codice'], 'A1')
            self.assertEqual(json.loads(rows[0]['dettagli']), {'colore': 'blu'})

    def test_replica_ddl_cannot_attach_or_read_files(self):
        allowed = "CREATE TABLE vendite.t (a INT);\nCOMMENT ON TABLE vendite.t IS 'copy and attach in a comment';"
        self.assertIsNone(pipeline_tools.DENIED_DDL.search(pipeline_tools.strip_literals(allowed)))
        for denied in ("ATTACH 'x.duckdb' AS x;", "CREATE TABLE t AS SELECT * FROM read_csv('f.csv');", ".shell ls", "INSTALL httpfs;"):
            self.assertIsNotNone(pipeline_tools.DENIED_DDL.search(pipeline_tools.strip_literals(denied)), denied)


class PackageTemplates(unittest.TestCase):
    def test_runner_and_dockerfile_contracts(self):
        self.assertIn('flock -n 9', pipeline_scaffold.RUN_SH)
        self.assertIn('disabled in production', pipeline_scaffold.RUN_SH)
        docker = pipeline_scaffold.dockerfile('fabric')
        self.assertIn('msodbcsql18', docker)
        self.assertIn(pipeline_scaffold.SUPERCRONIC['amd64'], docker)
        self.assertIn('USER pipeline', docker)
        self.assertNotIn('msodbcsql18', pipeline_scaffold.dockerfile('postgres'))
        env = pipeline_scaffold.env_example('fabric', 'oracle')
        self.assertTrue(all(line.endswith('=') or '=' not in line or line.split('=', 1)[1] in ('test', 'raw', 'local', '200', 'fabric', 'project_ingestion', 'html', '/data/source-stub.duckdb', '/data/warehouse.duckdb')
                            for line in env.splitlines() if not line.startswith('#')), 'no secret values in .env.example')

    def test_production_gateway_uses_env_var_secrets(self):
        for target in ('postgres', 'tsql', 'fabric'):
            config = pipeline_scaffold.sqlmesh_config(target, 'vendite', '@hourly')
            self.assertIn('default_gateway: local', config)
            self.assertIn("{{ env_var('RIGHAVEN_WAREHOUSE_DUCKDB'",config, 'generated f-string must retain actual Jinja braces')
            for line in config.splitlines():
                if 'password' in line:
                    self.assertIn('env_var(', line, target)


if __name__ == '__main__':
    unittest.main()
