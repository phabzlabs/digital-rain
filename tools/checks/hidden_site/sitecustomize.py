"""Check runs only (tools/checks/hidden.py puts this folder on PYTHONPATH): make any
tkinter root a child creates transparent and non-activating. Does nothing
unless MATRIX_CHECK_HIDDEN=1. tkinter is patched when it is first imported, so
processes that never import it pay nothing."""

import os
import sys

if os.environ.get("MATRIX_CHECK_HIDDEN") == "1" and sys.platform == "win32":
    import importlib.abc
    import importlib.util

    class _Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path, target=None):
            if name != "tkinter":
                return None
            sys.meta_path.remove(self)
            try:
                spec = importlib.util.find_spec(name)
            finally:
                sys.meta_path.insert(0, self)
            if spec is None or spec.loader is None:
                return spec
            loader = spec.loader
            orig_exec = loader.exec_module

            def exec_module(module):
                orig_exec(module)
                tools = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                sys.path.insert(0, tools)
                try:
                    import hidden

                    hidden.patch_tk(module)
                except Exception:
                    pass
                finally:
                    sys.path.remove(tools)
                    sys.modules.pop("hidden", None)

            loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _Finder())
