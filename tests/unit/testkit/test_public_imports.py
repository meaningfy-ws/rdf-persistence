"""``testkit.assert_public_imports``: a test file may use ``rdf_persistence`` and its ``testkit`` only (PD-20)."""

from pathlib import Path

import pytest

from rdf_persistence.testkit import assert_public_imports

ALLOWED = [
    "from rdf_persistence import FusekiStore",
    "import rdf_persistence",
    "from rdf_persistence.testkit import access_token",
    "from rdf_persistence.testkit.containers import fixtures",
    "import rdf_persistence.testkit",
    "from tests.toy import TOY_SCHEMA",
    "import httpx",
    "from rdf_persistencex import thing",
]
REFUSED = [
    "from rdf_persistence.services.access import AccessRules",
    "import rdf_persistence.adapters.fuseki",
    "from rdf_persistence.domain import iris",
    "from rdf_persistence.entrypoints.service import install_service",
    "from rdf_persistence import services",
    "if True:\n    from rdf_persistence.services import store",
]


def module(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "test_consumer.py"
    path.write_text(source + "\n")
    return path


@pytest.mark.parametrize("source", ALLOWED)
def test_a_public_import_is_accepted(tmp_path, source):
    assert_public_imports(module(tmp_path, source))


@pytest.mark.parametrize("source", REFUSED)
def test_an_import_of_a_toolkit_layer_is_refused_and_named(tmp_path, source):
    with pytest.raises(AssertionError, match="rdf_persistence"):
        assert_public_imports(module(tmp_path, source))


def test_every_offending_import_is_listed_with_its_line(tmp_path):
    path = module(
        tmp_path,
        "from rdf_persistence import Store\nimport rdf_persistence.adapters.s3\nfrom rdf_persistence.services import files",
    )
    with pytest.raises(AssertionError) as caught:
        assert_public_imports(path)
    assert "test_consumer.py:2" in str(caught.value), "the adapter import is named with its line"
    assert "test_consumer.py:3" in str(caught.value), "and so is the services import"
