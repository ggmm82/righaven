import os
import unittest
from unittest.mock import patch
try:
    from righaven import build_routes
except ImportError:
    if os.getenv('RIGHAVEN_REQUIRE_GATEWAY_TESTS')=='1':raise
    build_routes=None


@unittest.skipIf(build_routes is None,'Requires native Gateway SDK')
class BuildIdentityTests(unittest.TestCase):
    def test_release_version_is_separate_from_source_identity(self):
        with patch.dict(os.environ,{'RIGHAVEN_VERSION':'0.7.6-rc.pr.19.123.1','RIGHAVEN_COMMIT':'a'*40}):
            identity=build_routes.identity()
        self.assertEqual(identity['version'],'0.7.6-rc.pr.19.123.1')
        self.assertEqual(identity['commit'],'a'*12)
        self.assertFalse(identity['local'])
