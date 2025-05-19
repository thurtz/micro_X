# tests/conftest.py
#
# This file can be used to define project-wide fixtures, hooks, or plugins for pytest.
# For now, it can be empty or used to adjust Python's path if modules are not found.

import sys
import os

# Add the project root to the Python path to help pytest find your modules
# This assumes your 'tests' directory is at the root of your micro_X project,
# and 'modules' is also at the root.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# You can define shared fixtures here. For example:
# @pytest.fixture
# def some_shared_resource():
#     # setup code
#     yield resource
#     # teardown code