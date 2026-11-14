"""The private pieces of ``Transaction`` have one caller each (PD-32 item 5).

``_allow_state`` lets a write set the state of an aggregate, which only a transition may do;
``_require_match`` and ``_require_present`` add a guard to a commit for the collection and the
discussion code. A call from anywhere else would be a way past a rule the toolkit keeps, so the
callers are pinned: a new one fails here and has to be argued for.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).parents[3] / "rdf_persistence"
DEFINED_IN = "services/session.py"
CALLERS = {
    "_allow_state": {"services/transitions.py"},
    "_require_match": {"services/reference_collections.py"},
    "_require_present": {"services/discussion.py"},
}


def uses_and_definitions(name: str) -> tuple[set[str], set[str]]:
    """The files of the package that use ``name`` as an attribute, and those that define a function so named."""
    used, defined = set(), set()
    for path in PACKAGE.rglob("*.py"):
        relative = path.relative_to(PACKAGE).as_posix()
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr == name:
                used.add(relative)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
                defined.add(relative)
    return used, defined


@pytest.mark.parametrize("name", sorted(CALLERS))
def test_a_private_piece_of_the_transaction_has_one_caller_and_one_definition(name):
    used, defined = uses_and_definitions(name)
    assert defined == {DEFINED_IN}, (
        f"{name} is defined in {sorted(defined)}, not only in the session"
    )
    assert used == CALLERS[name], (
        f"{name} is used by {sorted(used)}, expected {sorted(CALLERS[name])}"
    )
