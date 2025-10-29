"""Tests for libertas package."""

import libertas


def test_version() -> None:
    """Test that version is defined."""
    assert hasattr(libertas, "__version__")
    assert isinstance(libertas.__version__, str)
