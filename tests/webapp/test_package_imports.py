"""Test that the webapp package and its modules can be imported safely."""

import pytest
from unittest.mock import MagicMock

from dt.communication.db_client import DatabaseApiClient


def test_import_webapp():
    """Test that the main webapp module can be imported."""
    import dt.webapp.app as webapp_app

    db_client = MagicMock(spec=DatabaseApiClient)
    app = webapp_app.create_app(start_consumer=False, db_client=db_client)
    assert app is not None


def test_import_init():
    """Test that the webapp package itself can be imported."""
    try:
        import dt.webapp
        assert dt.webapp is not None
    except ImportError as e:
        pytest.fail(f"Could not import dt.webapp: {e}")
