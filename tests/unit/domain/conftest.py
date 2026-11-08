import pytest

from rdf_persistence.domain import iris


@pytest.fixture
def until_stage_two(monkeypatch):
    """Lets a test build an ``Iris`` with an access, meta, registry or principal template (PD-12a)."""
    monkeypatch.setattr(iris, "STAGE_TWO_TEMPLATES", ())
