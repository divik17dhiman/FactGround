"""Smoke tests for the project package foundation."""

from superjoin_fact_knowledge import __version__


def test_package_metadata_is_present() -> None:
    """The package should expose a minimal version marker for future work."""
    assert __version__ == "0.1.0"
