"""Real SQLite/WAL cutover and disposable-container persistence contracts."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
import yaml
from righaven.persistent_database import configure


class PersistentDatabaseTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.state=self.root/'volume';self.state.mkdir()
        self.config=self.state/'config.yaml'
        self.working=self.root/'disposable-container';self.working.mkdir()

    def config_for(self, directory='.righaven/data', backend='sqlite'):
        self.config.write_text(yaml.safe_dump({'database':{'backend':backend,'sqlite_dir':directory},'models':[{'model':'keep-this'}]}))

    def database(self, directory, value='previous-user'):
        directory.mkdir(parents=True,exist_ok=True)
        database=sqlite3.connect(directory/'righaven_core.db')
        database.execute('PRAGMA journal_mode=WAL')
        database.execute('CREATE TABLE accounts (id TEXT)')
        database.execute('INSERT INTO accounts VALUES (?)',(value,));database.commit()
        self.addCleanup(database.close)
        return database

    def test_wal_backup_preserves_committed_data_and_the_original(self):
        self.config_for();source=self.working/'.righaven/data'
        original=self.database(source)
        self.assertTrue((source/'righaven_core.db-wal').exists())
        configure(self.config,self.state,working_directory=self.working)
        target=self.state/'database/righaven_core.db'
        with sqlite3.connect(target) as connection:self.assertEqual(connection.execute('SELECT id FROM accounts').fetchone(),('previous-user',))
        self.assertEqual(original.execute('SELECT id FROM accounts').fetchone(),('previous-user',))
        content=yaml.safe_load(self.config.read_text())
        self.assertEqual(content['database']['sqlite_dir'],str(self.state/'database'))
        self.assertEqual(content['models'],[{'model':'keep-this'}])
        configure(self.config,self.state,working_directory=self.working)

    def test_new_database_location_survives_a_different_container_working_directory(self):
        self.config_for('/righaven-state/database')
        configure(self.config,self.state,working_directory=self.working)
        self.database(self.state/'database')
        replacement=self.root/'replacement-container';replacement.mkdir()
        configure(self.config,self.state,working_directory=replacement)
        with sqlite3.connect(self.state/'database/righaven_core.db') as connection:
            self.assertEqual(connection.execute('SELECT id FROM accounts').fetchone(),('previous-user',))
        self.assertFalse((replacement/'.righaven').exists())

    def test_two_existing_databases_are_never_silently_overwritten(self):
        self.config_for();self.database(self.working/'.righaven/data')
        target=self.database(self.state/'database','different-user')
        before=self.config.read_bytes()
        with self.assertRaisesRegex(ValueError,'Both previous'):configure(self.config,self.state,working_directory=self.working)
        self.assertEqual(target.execute('SELECT id FROM accounts').fetchone(),('different-user',))
        self.assertEqual(self.config.read_bytes(),before)

    def test_custom_absolute_and_postgres_settings_are_preserved(self):
        for directory,backend in [(str(self.root/'custom-mount'),'sqlite'),('.righaven/data','postgres'),('$SQLITE_DIR','sqlite')]:
            with self.subTest(backend=backend,directory=directory):
                self.config_for(directory,backend);before=self.config.read_bytes()
                configure(self.config,self.state,working_directory=self.working)
                self.assertEqual(self.config.read_bytes(),before)
