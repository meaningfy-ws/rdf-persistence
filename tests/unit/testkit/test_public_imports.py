"""``testkit.assert_public_imports``: a test file may use ``rdf_persistence`` and its ``testkit`` only (PD-20)."""

from pathlib import Path

import pytest

from rdf_persistence.testkit import assert_public_imports

ALLOWED = [
    "from rdf_persistence import FusekiStore",
    "import rdf_persistence",
    "from rdf_persistence.testkit import access_token",
    "from rdf_persistence.testkit import TokenRefusedError",
    "from rdf_persistence.testkit import wait_until, wait_until_async",
    "from rdf_persistence.testkit.containers.fixtures import fuseki_url",
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
    "from rdf_persistence.testkit.exceptions import TokenRefusedError",
    "from rdf_persistence.testkit import exceptions",
    "import rdf_persistence.testkit.zitadel",
    "from rdf_persistence.testkit.fakes import FakeStore",
    "if True:\n    from rdf_persistence.services import store",
]


def module(tmp_path: Path, source: str) -> Path:
    path = tmp_path / "test_consumer.py"
    path.write_text(source + "\n")
    return path


@pytest.mark.parametrize("source", ALLOWED)
def test_a_public_import_is_accepted(tmp_path, source):
    assert_public_imports(module(tmp_path, source))


def test_the_waiting_helpers_are_exported_from_the_public_module():
    import rdf_persistence.testkit as testkit

    assert {"wait_until", "wait_until_async"} <= set(testkit.__all__)
    assert callable(testkit.wait_until) and callable(testkit.wait_until_async)


@pytest.mark.parametrize("source", REFUSED)
def test_an_import_of_a_toolkit_layer_is_refused_and_named(tmp_path, source):
    with pytest.raises(AssertionError, match="rdf_persistence"):
        assert_public_imports(module(tmp_path, source))


def test_a_testkit_module_is_refused_by_name(tmp_path):
    with pytest.raises(AssertionError, match=r"rdf_persistence\.testkit\.exceptions"):
        assert_public_imports(module(tmp_path, "from rdf_persistence.testkit.exceptions import X"))


def test_every_offending_import_is_listed_with_its_line(tmp_path):
    path = module(
        tmp_path,
        "from rdf_persistence import Store\nimport rdf_persistence.adapters.s3\nfrom rdf_persistence.services import files",
    )
    with pytest.raises(AssertionError) as caught:
        assert_public_imports(path)
    assert "test_consumer.py:2" in str(caught.value), "the adapter import is named with its line"
    assert "test_consumer.py:3" in str(caught.value), "and so is the services import"


def test_the_refusal_of_a_token_is_named_by_the_testkit_itself():
    from rdf_persistence.testkit import TokenRefusedError

    assert TokenRefusedError(401).status_code == 401, "the error a consumer's test expects"
