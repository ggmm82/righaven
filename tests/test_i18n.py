"""Verify native internationalization (i18n): English default, Italian 100% complete, and Accept-Language routing."""
import json
import unittest
from pathlib import Path
from fastapi import FastAPI
from fastapi.testclient import TestClient

from righaven.i18n import load_dictionary, localize_clarification, normalize_locale, translate
from righaven.i18n_routes import router as i18n_router


def flatten_keys(d: dict, prefix: str = '') -> set[str]:
    keys = set()
    for k, v in d.items():
        full = f'{prefix}.{k}' if prefix else k
        if isinstance(v, dict):
            keys |= flatten_keys(v, full)
        else:
            keys.add(full)
    return keys


class I18nTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(i18n_router)
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()

    def test_english_is_default_and_italian_is_100_percent_complete(self):
        en = load_dictionary('en')
        it = load_dictionary('it')
        self.assertTrue(en)
        self.assertTrue(it)
        en_keys = flatten_keys(en)
        it_keys = flatten_keys(it)
        self.assertEqual(en_keys, it_keys, 'Italian dictionary must have 100% key parity with English default')

    def test_accept_language_header_selects_english_or_italian_with_fallback(self):
        self.assertEqual(normalize_locale(None), 'en')
        self.assertEqual(normalize_locale('en-US,en;q=0.9'), 'en')
        self.assertEqual(normalize_locale('it-IT,it;q=0.9,en;q=0.8'), 'it')
        self.assertEqual(normalize_locale('fr-FR,de;q=0.7'), 'en')

        res_default = self.client.get('/api/v1/i18n')
        self.assertEqual(res_default.status_code, 200)
        self.assertEqual(res_default.json()['locale'], 'en')

        res_it = self.client.get('/api/v1/i18n', headers={'Accept-Language': 'it-IT,it;q=0.9'})
        self.assertEqual(res_it.status_code, 200)
        self.assertEqual(res_it.json()['locale'], 'it')
        self.assertIn('Controllo RigHaven Harness', json.dumps(res_it.json()['dictionary']))

    def test_clarification_localization_supports_en_and_it(self):
        en_clar = localize_clarification(['Target resolution?'], locale='en')
        it_clar = localize_clarification(['Target resolution?'], locale='it')
        self.assertEqual(en_clar['locale'], 'en')
        self.assertIn('clarify', en_clar['prompt'].lower())
        self.assertEqual(it_clar['locale'], 'it')
        self.assertIn('chiarisci', it_clar['prompt'].lower())


if __name__ == '__main__':
    unittest.main()
