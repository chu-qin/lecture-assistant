"""Pytest fixtures"""

import sys
from pathlib import Path

import pytest

# Add project root to path
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))


@pytest.fixture
def project_root():
    return _project_root
