"""The lazy public names of the testkit (PD-4), touched one by one in a fresh interpreter."""

import subprocess
import sys

import pytest

LAZY = ["assert_isomorphic"]
EAGER = [
    "assert_models_generated",
    "model_shape_diff",
    "model_schema_diff",
    "class_shapes",
    "read_snapshot",
    "write_snapshot",
    "snapshot_diff",
]


@pytest.mark.parametrize("name", [*LAZY, *EAGER])
def test_each_guard_name_resolves_in_a_fresh_interpreter(name: str) -> None:
    code = f"import rdf_persistence.testkit as t; assert callable(t.{name}) or isinstance(t.{name}, type)"
    done = subprocess.run([sys.executable, "-I", "-c", code], check=False, capture_output=True)
    assert done.returncode == 0, done.stderr.decode()


@pytest.mark.parametrize("name", LAZY)
def test_a_lazy_name_loads_nothing_until_it_is_touched(name: str) -> None:
    code = (
        "import sys, rdf_persistence.testkit as t\n"
        "heavy = ('pyshacl', 'hypothesis')\n"
        "assert not any(h in sys.modules for h in heavy), 'loaded at import'\n"
        f"t.{name}\n"
    )
    done = subprocess.run([sys.executable, "-I", "-c", code], check=False, capture_output=True)
    assert done.returncode == 0, done.stderr.decode()


def test_a_lazy_name_is_kept_after_the_first_touch() -> None:
    import rdf_persistence.testkit as testkit

    first = testkit.assert_isomorphic
    assert testkit.__dict__["assert_isomorphic"] is first, "cached in the module, not re-imported"
