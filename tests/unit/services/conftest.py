"""The toy library's documents, read once, for the tests of bodies and representations."""

from pathlib import Path

import pytest

from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from tests.toy import TOY_SCHEMA

GENERATED = Path(__file__).parents[2] / "fixtures" / "library" / "generated"


@pytest.fixture(scope="module")
def documents() -> Documents:
    return Documents(load_schema(TOY_SCHEMA), GENERATED)


@pytest.fixture(scope="module")
def book_class(documents: Documents):
    return documents.aggregates["books"]


@pytest.fixture(scope="module")
def scan_class(documents: Documents):
    return documents.aggregates["scans"]
