"""Every error the Gateway raises is available in Italian and English."""
import unittest

from righaven import error_catalog


class ErrorCatalogTests(unittest.TestCase):
    def test_every_raised_message_has_a_decision_in_both_catalogs(self):
        raised = {text for text, _ in error_catalog.raised_messages()}
        english, italian = error_catalog.catalog('en'), error_catalog.catalog('it')
        self.assertEqual(sorted(raised - set(english)), [], 'Add these messages to locales/en/errors.json')
        self.assertEqual(sorted(set(english) - raised), [], 'Remove messages no longer raised from locales/en/errors.json')
        english_sources = {text for text, value in english.items() if value is None}
        self.assertEqual(sorted(english_sources - set(italian)), [], 'Add these English sources to locales/it/errors.json')
        self.assertEqual(sorted(set(italian) - english_sources), [], 'locales/it/errors.json translates only English sources')

    def test_messages_follow_the_viewer_language(self):
        localize = error_catalog.localize
        self.assertEqual(localize('Progetto non disponibile', 'en-US'), 'Project unavailable')
        self.assertEqual(localize('Progetto non disponibile', 'it-IT'), 'Progetto non disponibile')
        self.assertEqual(localize('Dipendenza mancante: d2', 'en'), 'Missing dependency: d2')  # composed message
        self.assertEqual(localize('Invalid credentials', 'it'), 'Credenziali non valide')
        self.assertEqual(localize('Invalid credentials', 'en'), 'Invalid credentials')
        self.assertEqual(localize('Messaggio sconosciuto', 'en'), 'Messaggio sconosciuto')
        self.assertEqual(localize({'code': 'x'}, 'en'), {'code': 'x'})

    def test_http_errors_are_served_in_the_language_of_the_workspace(self):
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient
        from starlette.exceptions import HTTPException as StarletteHTTPException
        app = FastAPI()
        app.add_exception_handler(StarletteHTTPException, error_catalog.localized_http_exception)

        @app.get('/fail')
        async def fail():
            raise HTTPException(409, 'Progetto non disponibile')

        @app.get('/structured')
        async def structured():
            raise HTTPException(400, {'code': 'not_authenticated'})
        client = TestClient(app)
        self.assertEqual(client.get('/fail', cookies={'locale': 'en-US'}).json()['detail'], 'Project unavailable')
        self.assertEqual(client.get('/fail', cookies={'locale': 'it-IT'}).json()['detail'], 'Progetto non disponibile')
        self.assertEqual(client.get('/fail', headers={'Accept-Language': 'en-GB,en'}).json()['detail'], 'Project unavailable')
        self.assertEqual(client.get('/structured', cookies={'locale': 'en-US'}).json()['detail'], {'code': 'not_authenticated'})
        self.assertEqual(client.get('/missing', cookies={'locale': 'it-IT'}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
