"""Test that all alert engine modules can be imported without side effects."""



def test_import_alerts_package():
    """Verify dt.alerts package imports and exposes create_app."""
    from dt.alerts import create_app

    assert callable(create_app), "create_app should be a callable function"


def test_import_config_modules():
    """Verify config submodules import without errors."""


def test_import_state_modules():
    """Verify state submodules import without errors."""


def test_import_engine_modules():
    """Verify engine submodules import without errors."""


def test_import_service_module():
    """Verify service module imports without errors."""


def test_import_api_module():
    """Verify API module imports without errors."""


def test_import_app_module():
    """Verify app module imports without errors."""
