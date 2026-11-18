"""The ``rdf_persistence.domain.base`` shim (thematic-structure PD-8, TC-05).

``RpModel`` is defined in ``rdf_persistence.core.domain.base``. A consumer's generated code written before
the move still imports it from ``rdf_persistence.domain.base``, which warns and re-exports until the
release that removes it. This test names the old path on purpose, so ``test_no_old_module_paths`` exempts it.
"""

import json
import subprocess
import sys

import grimp

SHIM = "rdf_persistence.domain.base"
NEW = "rdf_persistence.core.domain.base"
# A fresh interpreter, because the warning fires on the first import only.
PROBE = f"""
import json, warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import {SHIM} as shim
    import {NEW} as core
print(json.dumps({{
    "warnings": [[w.category.__name__, str(w.message)] for w in caught if "rdf_persistence" in str(w.message)],
    "same": shim.RpModel is core.RpModel,
}}))
"""


def _import_in_a_fresh_interpreter() -> dict:
    run = subprocess.run(
        [sys.executable, "-c", PROBE], capture_output=True, text=True, check=True, timeout=120
    )
    return json.loads(run.stdout.splitlines()[-1])


def test_importing_the_old_path_warns_once_naming_the_new_path_and_hands_back_the_same_class():
    answer = _import_in_a_fresh_interpreter()

    assert [category for category, _ in answer["warnings"]] == ["DeprecationWarning"], (
        "one DeprecationWarning, no other"
    )
    assert NEW in answer["warnings"][0][1], "the message names the new path"
    assert answer["same"], "RpModel of the shim is the object defined in core"


def test_no_module_of_the_package_imports_the_shim():
    graph = grimp.build_graph("rdf_persistence")

    importers = graph.find_modules_that_directly_import(SHIM)

    assert importers == set(), f"modules that import the shim: {sorted(importers)}"


def test_rpmodel_is_defined_in_core_domain_base():
    from rdf_persistence.core.domain.base import RpModel

    assert RpModel.__module__ == NEW, "TC-03: RpModel is defined at its new home"
