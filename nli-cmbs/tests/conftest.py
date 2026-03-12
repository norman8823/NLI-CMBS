import pytest


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless explicitly requested with -m integration."""
    if config.getoption("-m") and "integration" in config.getoption("-m"):
        return
    skip_integration = pytest.mark.skip(reason="use -m integration to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def sample_ex102_xml():
    from pathlib import Path

    return (Path(__file__).parent / "fixtures" / "sample_ex102.xml").read_text()
