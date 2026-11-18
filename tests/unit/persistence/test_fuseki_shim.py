"""The ``rdf_persistence.adapters.fuseki`` shim (thematic-structure PD-8, TC-44).

``FusekiStore`` is defined in ``rdf_persistence.persistence.adapters.fuseki``. A consumer's code written
before the move still imports it from ``rdf_persistence.adapters.fuseki``, which warns and re-exports
until the release that removes it. This test names the old path on purpose, so ``test_no_old_module_paths``
exempts it.
"""

import json
import subprocess
import sys

import grimp

SHIM = "rdf_persistence.adapters.fuseki"
NEW = "rdf_persistence.persistence.adapters.fuseki"
PROTOCOL = "rdf_persistence.persistence.adapters.sparql_protocol"
# The names a consumer may have imported from the old module.
OLD_NAMES = ("FusekiStore", "SPARQL_QUERY", "SPARQL_UPDATE", "RESULTS_JSON", "GRAPH_PARAM")
# A fresh interpreter, because the warning fires on the first import only.
PROBE = f"""
import json, warnings
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import {SHIM} as shim
    import {NEW} as moved
    import {PROTOCOL} as protocol
    import rdf_persistence
print(json.dumps({{
    "warnings": [[w.category.__name__, str(w.message)] for w in caught if "rdf_persistence" in str(w.message)],
    "same": shim.FusekiStore is moved.FusekiStore is rdf_persistence.FusekiStore,
    "names": [
        name for name in {OLD_NAMES!r}
        if getattr(shim, name) == getattr(moved, name, None) or getattr(shim, name) == getattr(protocol, name, None)
    ],
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
    assert answer["same"], "FusekiStore of the shim is the class of rdf_persistence.FusekiStore"


def test_the_shim_hands_back_every_name_the_old_module_had_that_stays_public():
    answer = _import_in_a_fresh_interpreter()

    assert answer["names"] == list(OLD_NAMES), "each re-exported name is the moved object"


def test_no_module_of_the_package_imports_the_shim():
    graph = grimp.build_graph("rdf_persistence")

    importers = graph.find_modules_that_directly_import(SHIM)

    assert importers == set(), f"modules that import the shim: {sorted(importers)}"


def test_fusekistore_is_defined_in_the_persistence_adapters():
    from rdf_persistence.persistence.adapters.fuseki import FusekiStore

    assert FusekiStore.__module__ == NEW, "TC-44: FusekiStore is defined at its new home"
