"""Behavior tests for the public API of research_brief_schema."""

from __future__ import annotations

import pytest

import research_brief_schema


def test_normalize_trims_and_lowercases() -> None:
    assert research_brief_schema.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        research_brief_schema.normalize(value)


def test_version_is_semver() -> None:
    parts = research_brief_schema.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
