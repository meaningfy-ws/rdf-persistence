"""The container fixtures need the extra ``rdf-persistence[testkit]``; the testkit root does not (PD-16)."""

import importlib
import subprocess
import sys

import pytest

CONTAINERS = "rdf_persistence.testkit.containers"


def test_testkit_root_does_not_import_testcontainers() -> None:
    code = "import sys, rdf_persistence.testkit; sys.exit('testcontainers' in sys.modules)"
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0


def test_missing_extra_names_the_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "testcontainers", None)  # makes `import testcontainers` fail
    for name in [m for m in sys.modules if m.startswith(CONTAINERS)]:
        monkeypatch.delitem(sys.modules, name)
    with pytest.raises(ImportError, match=r"rdf-persistence\[testkit\]"):
        importlib.import_module(CONTAINERS)


def test_testkit_root_does_not_import_the_token_or_provisioning_libraries() -> None:
    code = "import sys, rdf_persistence.testkit; sys.exit('jwt' in sys.modules or 'cryptography' in sys.modules)"
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0


@pytest.mark.parametrize(
    "name", ["TokenSigner", "new_key", "access_token", "create_machine_user", "provision_project"]
)
def test_the_token_and_provisioning_names_load_on_first_use(name: str) -> None:
    import rdf_persistence.testkit as testkit

    assert callable(getattr(testkit, name))


def test_an_unknown_testkit_name_is_an_attribute_error() -> None:
    import rdf_persistence.testkit as testkit

    with pytest.raises(AttributeError, match="no_such_helper"):
        testkit.no_such_helper  # noqa: B018


def test_every_name_of_all_resolves() -> None:
    import rdf_persistence.testkit as testkit

    assert [name for name in testkit.__all__ if not hasattr(testkit, name)] == [], (
        "every name in __all__ resolves"
    )


@pytest.mark.parametrize("heavy", ["hypothesis", "pyshacl"])
def test_testkit_root_does_not_import_the_heavy_libraries(heavy: str) -> None:
    code = f"import sys, rdf_persistence.testkit; sys.exit({heavy!r} in sys.modules)"
    assert subprocess.run([sys.executable, "-I", "-c", code], check=False).returncode == 0, (
        "the import ran clean in a fresh interpreter"
    )


@pytest.mark.parametrize(
    "name",
    [
        "assert_models_generated",
        "model_shape_diff",
        "model_schema_diff",
        "class_shapes",
        "read_snapshot",
        "write_snapshot",
        "snapshot_diff",
        "Conformance",
        "conformance_problems",
        "round_trip",
        "aggregate",
    ],
)
def test_the_guard_api_is_in_all(name: str) -> None:
    import rdf_persistence.testkit as testkit

    assert name in testkit.__all__, "the name is exported"
