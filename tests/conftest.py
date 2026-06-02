"""Share pytest configuration for the test suite.

Why this exists:
    - Register the `slow` marker used by container tests so pytest doesn't warn
    - Provides a way skip slow tests by default: `pytest -m "not slow"`
    - Centralizes any fixture or hook that multiple test files share
"""
from __future__ import annotations

import pytest

def pytest_configure(config):
    """Register custom markers so they show up in `pytest --markers`."""
    config.addinivalue_line(
        "markers",
        "slow: tests that take more than a few seconds (e.g. container builds)",
    )
    

def pytest_collection_modifyitems(config, items):
    """Auto-mark all tests in test_container.py as 'slow'
    Let users run only the fast tests during dev:
        pytest -m "not slow"
    """
    for item in items:
        if "test_container" in str(item.fspath):
            item.add_marker(pytest.mark.slow)