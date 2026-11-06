"""Tests that need real programs: skipped locally when missing, failures in CI.

CI sets RIGHAVEN_REQUIRE_TOOLS=1 after installing the programs, so a missing
tool can no longer turn a real check into a silent skip.
"""
import os
import shutil
import unittest


def requires(*programs):
    missing = [p for p in programs if shutil.which(p) is None]
    if not missing:
        return lambda test: test
    if os.getenv('RIGHAVEN_REQUIRE_TOOLS') == '1':
        def fail(test):
            if isinstance(test, type):
                def setUp(self):
                    self.fail('Missing required programs (RIGHAVEN_REQUIRE_TOOLS=1): ' + ', '.join(missing))
                test.setUp = setUp
                return test
            def run(self, *args, **kwargs):
                self.fail('Missing required programs (RIGHAVEN_REQUIRE_TOOLS=1): ' + ', '.join(missing))
            run.__name__ = test.__name__
            return run
        return fail
    return unittest.skip('Requires ' + ', '.join(missing))
