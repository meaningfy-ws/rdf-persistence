"""The conformance, round-trip, strategy and freshness modules live in the generator (PD-2, PD-3).

The old paths in ``rdf_persistence.testkit`` are gone (#165); their absence is tested in
``tests/unit/testkit/test_generator_shims_removed.py``. Each import runs in a fresh interpreter, so
no module the suite has imported hides a leftover.
"""

import json
import subprocess
import sys
import textwrap

import pytest

from tests.generator.unit.test_freshness import DEFAULT_HINT
from tests.generator.unit.test_freshness_plugin import INI, TEST, make_project

NEW = "rdf_persistence_generation.testkit"
# the lazy public names of the generator's testkit -> (module, attribute)
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
warned = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
print(json.dumps({{"warned": warned, "result": result}}))
"""


def run_python(body: str) -> dict:
    """Run ``body`` (it sets ``result``) in a fresh interpreter; return its deprecation warnings."""
    code = RECORD.format(body=textwrap.indent(textwrap.dedent(body), "    "))
    done = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.splitlines()[-1])


def test_the_generator_testkit_exports_the_four_names_lazily() -> None:
    """TC-17 (PD-2): the package has the four names, and loads pyshacl and hypothesis on use."""
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
    assert seen["warned"] == [], "the new package never warns"
    before, *same, exported = seen["result"]
    assert before == [], f"importing the package loaded {before}"
    assert same == [True] * 4, "a lazy name is not the module's object"
    assert exported == sorted(LAZY), exported


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


@pytest.mark.slow
def test_the_plugin_path_stops_a_stale_session(pytester: pytest.Pytester) -> None:
    """TC-19: the plugin path stops a stale session with the stale message and the command."""
    make_project(pytester.path)
    pytester.makeini(INI.replace("    other/pyproject.toml\n", ""))
    pytester.makeconftest(f'pytest_plugins = ["{NEW}.freshness"]\n')
    pytester.makepyfile(test_it=TEST)
    schema = pytester.path / "m.yaml"
    schema.write_text(schema.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8")
    result = pytester.runpytest_subprocess("-W", "error::DeprecationWarning")
    assert result.ret == 1, "the session did not stop with exit code 1"
    result.stdout.fnmatch_lines(["*m.yaml*", f"*{DEFAULT_HINT}*"])
    assert "test_it" not in result.stdout.str(), "a test ran in a stale session"
