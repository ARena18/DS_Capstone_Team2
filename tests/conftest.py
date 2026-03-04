# conftest.py — shared pytest configuration
# Ensures the project root is on sys.path so `import app` etc. work.

import importlib
import sys
import os

# Add project root to path
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "combined"))


"""
tests/conftest.py

test_app.py stubs 'planner_query_tools' in sys.modules with ALL_TOOLS=[]
and no tool functions. This conftest removes that stub before
test_planner_query_tools.py tests run, so they get the real module.
"""

def pytest_runtest_setup(item):
    if "test_planner_query_tools" in item.nodeid:
        # Remove the hollow stub injected by test_app.py
        sys.modules.pop("planner_query_tools", None)
        # Also remove query_library stub so the real one loads
        sys.modules.pop("query_library", None)
        # Re-import the real module
        importlib.import_module("planner_query_tools")