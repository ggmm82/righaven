"""Internal adapter for the pinned orchestration dependency.

Both import names must resolve to the same modules, so runtime user context,
configuration caches and persistence engines are never duplicated.
"""
import importlib
import importlib.abc
import importlib.util
import os
import sys


def sync_environment():
    for key, value in list(os.environ.items()):
        if key.startswith('RIGHAVEN_'):
            os.environ['DEER_FLOW_' + key.removeprefix('RIGHAVEN_')] = value


sync_environment()


class CoreAlias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'righaven_core' or fullname.startswith('righaven_core.'):
            sync_environment()
            original = 'deerflow' + fullname[len('righaven_core'):]
            spec = importlib.util.find_spec(original)
            if spec is not None:
                return importlib.util.spec_from_loader(
                    fullname, self, is_package=spec.submodule_search_locations is not None)

    def create_module(self, spec):
        return importlib.import_module('deerflow' + spec.name[len('righaven_core'):])

    def exec_module(self, module):
        pass


sys.meta_path.insert(0, CoreAlias())
