import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from righaven import state, gallery, hub_registry as hub


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.patch = patch.object(state, 'STATE', Path(self.temp.name))
        self.patch.start(); self.addCleanup(self.patch.stop)
        self.pack = dict(gallery.get_pack('skill-d2'))
        self.data = json.dumps({'packs': [self.pack]}).encode()
        self.pin = hashlib.sha256(self.data).hexdigest()

    def test_pinned_sync_is_namespaced_and_available_in_gallery(self):
        hub.configure('community', 'https://example.test/catalog.json', self.pin)
        hub.sync('community', fetch=lambda config:self.data)
        pack = gallery.get_pack('remote-community-skill-d2')
        self.assertEqual(pack['catalog_sha256'], self.pin)
        self.assertFalse(pack['verified'])
        self.assertEqual(gallery.get_pack('skill-d2')['id'], 'skill-d2')

    def test_changed_bytes_or_duplicate_entries_leave_previous_catalog_intact(self):
        hub.configure('community', 'https://example.test/catalog.json', self.pin)
        hub.sync('community', fetch=lambda config:self.data)
        previous = hub.remote_packs()
        with self.assertRaises(ValueError):hub.sync('community',fetch=lambda config:b'changed')
        self.assertEqual(hub.remote_packs(),previous)
        duplicate = json.dumps({'packs':[self.pack,self.pack]}).encode()
        hub.configure('community','https://example.test/catalog.json',hashlib.sha256(duplicate).hexdigest())
        with self.assertRaises(ValueError):hub.sync('community',fetch=lambda config:duplicate)
        self.assertEqual(hub.remote_packs(),previous)

    def test_unpinned_insecure_or_credential_bearing_urls_are_rejected(self):
        for url,pin in [('http://example.test',self.pin),('https://user:secret@example.test',self.pin),('https://example.test','latest')]:
            with self.assertRaises(ValueError):hub.configure('community',url,pin)
