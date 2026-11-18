"""The conformance, round-trip, strategy and freshness modules moved to the generator (PD-2, PD-3).

Each import runs in a fresh interpreter: a module imported once warns once per process, and the
suite has already imported the new paths.
"""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.unit.generation.test_freshness import DEFAULT_HINT
from tests.unit.testkit.test_freshness_plugin import INI, TEST, make_project

OLD = "rdf_persistence.testkit"
NEW = "rdf_persistence_generation.testkit"
# the public names each shim re-exports, by module
PUBLIC_NAMES = {
    "conformance": [
        "Conformance",
        "coverage_problems",
        "generated_classes",
        "load_cases",
        "run",
        "used_kinds",
        "verdict_problems",
    ],
    "roundtrip": [
        "FRAMING_KEYS",
        "assert_isomorphic",
        "internal_values",
        "public_projection",
        "round_trip",
        "without_framing",
    ],
    "strategies": [
        "IRI_BASE",
        "IRIS",
        "MAX_DEPTH",
        "MAX_ITEMS",
        "TEXT",
        "TYPE_VALUES",
        "aggregate",
    ],
    "freshness": ["DEFAULT_PROJECT", "PROJECTS_OPTION", "pytest_addoption", "pytest_sessionstart"],
}
# the old lazy name -> (new module, attribute)
LAZY = {
    "Conformance": ("conformance", "Conformance"),
    "conformance_problems": ("conformance", "run"),
    "round_trip": ("roundtrip", "round_trip"),
    "aggregate": ("strategies", "aggregate"),
}
RECORD = """
import json, sys, warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
{body}
moved = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)
         and "{new}" in str(w.message)]
print(json.dumps({{"moved": moved, "result": result}}))
"""


def run_python(body: str) -> dict:
    """Run ``body`` (it sets ``result``) in a fresh interpreter; return the moved-module warnings."""
    code = RECORD.format(body=textwrap.indent(textwrap.dedent(body), "    "), new=NEW)
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.splitlines()[-1])


@pytest.mark.parametrize("module", ["conformance"])
def test_importing_the_old_conformance_module_warns_once_and_re_exports(module: str) -> None:
    """TC-15: one DeprecationWarning naming the new module; ``Conformance`` is the moved class."""
    seen = run_python(
        f"""
        import {OLD}.{module} as old
        import {NEW}.{module} as new
        result = old.Conformance is new.Conformance
        """
    )
    assert len(seen["moved"]) == 1, f"expected one warning naming {NEW}.{module}: {seen['moved']}"
    assert f"{NEW}.{module}" in seen["moved"][0], seen["moved"]
    assert seen["result"] is True, "the shim re-exports the moved class itself"


@pytest.mark.parametrize("module", sorted(PUBLIC_NAMES))
def test_each_old_module_warns_naming_its_own_new_module(module: str) -> None:
    """TC-16: conformance, freshness, roundtrip, strategies each warn once and re-export every name."""
    names = PUBLIC_NAMES[module]
    seen = run_python(
        f"""
        import {OLD}.{module} as old
        import {NEW}.{module} as new
        result = [n for n in {names!r} if getattr(old, n) is not getattr(new, n)]
        """
    )
    assert len(seen["moved"]) == 1, f"expected one warning for {module}: {seen['moved']}"
    assert f"{NEW}.{module}" in seen["moved"][0], seen["moved"]
    assert seen["result"] == [], f"not the moved objects: {seen['result']}"


def test_the_lazy_public_names_are_the_moved_objects_and_warn() -> None:
    """TC-17: the four lazy names of ``rdf_persistence.testkit`` resolve to the moved objects."""
    seen = run_python(
        f"""
        from {OLD} import Conformance, conformance_problems, round_trip, aggregate
        import {NEW}.conformance as c, {NEW}.roundtrip as r, {NEW}.strategies as s
        result = [
            Conformance is c.Conformance,
            conformance_problems is c.run,
            round_trip is r.round_trip,
            aggregate is s.aggregate,
        ]
        """
    )
    assert seen["result"] == [True] * 4, "a lazy name is not the moved object"
    named = {
        module
        for module in ("conformance", "roundtrip", "strategies")
        if any(f"{NEW}.{module}" in message for message in seen["moved"])
    }
    assert named == {"conformance", "roundtrip", "strategies"}, seen["moved"]


def test_the_generator_testkit_exports_the_four_names_lazily() -> None:
    """TC-17 (PD-2): the new package has the four names, and loads pyshacl and hypothesis on use."""
    seen = run_python(
        f"""
        import {NEW} as kit
        before = [h for h in ("pyshacl", "hypothesis") if h in sys.modules]
        import {NEW}.conformance as c
        import {NEW}.roundtrip as r
        import {NEW}.strategies as s
        result = [
            before,
            kit.Conformance is c.Conformance,
            kit.conformance_problems is c.run,
            kit.round_trip is r.round_trip,
            kit.aggregate is s.aggregate,
            sorted(kit.__all__),
        ]
        """
    )
    assert seen["moved"] == [], "the new package never warns"
    before, *same, exported = seen["result"]
    assert before == [], f"importing the package loaded {before}"
    assert same == [True] * 4, "a lazy name is not the module's object"
    assert exported == sorted(LAZY), exported


def test_the_testkit_root_does_not_warn_nor_load_the_shims() -> None:
    """TC-20: ``import rdf_persistence.testkit`` loads no shim and warns about none."""
    seen = run_python(
        f"""
        import {OLD}
        result = [m for m in sys.modules if m.startswith("{OLD}.") and m.rsplit(".", 1)[1] in
                  ("conformance", "freshness", "roundtrip", "strategies")]
        """
    )
    assert seen["moved"] == [], f"the root warned: {seen['moved']}"
    assert seen["result"] == [], f"the root loaded a shim: {seen['result']}"


def test_the_generator_testkit_imports_without_linkml() -> None:
    """TC-21: with ``linkml`` unimportable the package imports and ``Conformance`` loads."""
    seen = run_python(
        f"""
        sys.modules["linkml"] = None
        import {NEW} as kit
        result = kit.Conformance.__name__
        """
    )
    assert seen["result"] == "Conformance", "Conformance did not load without linkml"


WARNING_AS_ERROR = (
    f"error:rdf_persistence.testkit.freshness moved to {NEW}.freshness:DeprecationWarning"
)


def stale_session(pytester: pytest.Pytester, plugin: str) -> None:
    """A rootdir with a generated toy project whose schema changed, the plugin at ``plugin``."""
    make_project(pytester.path)
    pytester.makeini(INI.replace("    other/pyproject.toml\n", ""))
    pytester.makeconftest(f'pytest_plugins = ["{plugin}"]\n')
    pytester.makepyfile(test_it=TEST)
    schema = pytester.path / "m.yaml"
    schema.write_text(schema.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")


def assert_stopped_as_stale(result: pytest.RunResult) -> None:
    assert result.ret == 1, "the session did not stop with exit code 1"
    result.stdout.fnmatch_lines(["*m.yaml*", f"*{DEFAULT_HINT}*"])
    assert "test_it" not in result.stdout.str(), "a test ran in a stale session"


@pytest.mark.slow
def test_the_old_plugin_path_still_stops_a_stale_session(pytester: pytest.Pytester) -> None:
    """TC-18: ``pytest_plugins`` naming the old path stops with the stale message and the command."""
    stale_session(pytester, f"{OLD}.freshness")
    assert_stopped_as_stale(pytester.runpytest_subprocess())


@pytest.mark.slow
def test_the_old_plugin_path_warns_naming_the_new_one(pytester: pytest.Pytester) -> None:
    """TC-18: the old path's DeprecationWarning, made an error, names the new plugin path."""
    stale_session(pytester, f"{OLD}.freshness")
    result = pytester.runpytest_subprocess("-W", WARNING_AS_ERROR)
    out = result.stdout.str() + result.stderr.str()
    assert f"{OLD}.freshness moved to {NEW}.freshness" in out, f"no warning raised:\n{out}"


@pytest.mark.slow
def test_the_new_plugin_path_stops_a_stale_session_without_a_warning(
    pytester: pytest.Pytester,
) -> None:
    """TC-19: the new path gives the same stop; the old path's warning, an error, never fires."""
    stale_session(pytester, f"{NEW}.freshness")
    assert_stopped_as_stale(pytester.runpytest_subprocess("-W", WARNING_AS_ERROR))


def test_the_removal_release_is_named_in_every_shim() -> None:
    """TC-16 (PD-3): each shim's docstring names the release that removes it."""
    folder = Path(__file__).resolve().parents[3] / "rdf_persistence" / "testkit"
    missing = [
        name
        for name in PUBLIC_NAMES
        if "will be removed in 0." not in (folder / f"{name}.py").read_text(encoding="utf-8")
    ]
    assert missing == [], f"shims that do not name their removal release: {missing}"
