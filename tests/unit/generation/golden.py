"""Golden comparison for the extension tests (PD-25): the file set exactly, Turtle by meaning, the rest by text.

The goldens are rewritten only when ``RP_REFRESH_GOLDEN`` is set (a make target sets it); a plain
test run never writes them.
"""

import os
from pathlib import Path

from rdflib import Graph
from rdflib.compare import graph_diff, isomorphic, to_isomorphic

GOLDEN_ROOT = Path(__file__).parents[2] / "fixtures" / "library" / "golden"
REFRESH_VARIABLE = "RP_REFRESH_GOLDEN"
TURTLE = ".ttl"
PYTHON = ".py"
KEPT_AS = ".golden"  # a Python golden is kept as text, so no tool lints, types or imports it


def _files(folder: Path) -> list[Path]:
    return sorted(p.relative_to(folder) for p in folder.rglob("*") if p.is_file())


def stored(name: Path) -> Path:
    """The name a golden is kept under: a Python file gets a ``.golden`` suffix."""
    return name.with_name(name.name + KEPT_AS) if name.suffix == PYTHON else name


def _golden_names(golden: Path) -> list[Path]:
    """The golden files of a folder under the names they stand for."""
    names = [
        p.with_name(p.name.removesuffix(KEPT_AS)) if p.suffix == KEPT_AS else p
        for p in _files(golden)
    ]
    return sorted(names)


def _refresh(produced: Path, golden: Path, names: list[Path]) -> None:
    for old in _files(golden) if golden.exists() else []:
        (golden / old).unlink()
    for name in names:
        (golden / stored(name)).parent.mkdir(parents=True, exist_ok=True)
        (golden / stored(name)).write_bytes((produced / name).read_bytes())


def turtle_difference(produced: Path, golden: Path) -> str | None:
    """None when the two Turtle files are the same graph; otherwise the triples only one has."""
    left, right = Graph().parse(produced), Graph().parse(golden)
    if isomorphic(left, right):
        return None
    _, only_golden, only_produced = graph_diff(to_isomorphic(right), to_isomorphic(left))
    return (
        f"only in the golden:\n{only_golden.serialize(format='turtle')}\n"
        f"only in the produced:\n{only_produced.serialize(format='turtle')}"
    )


def assert_matches_golden(module: str, produced: Path) -> None:
    """Fail unless ``produced`` holds exactly the files of ``golden/<module>/``, each equal by kind."""
    golden = GOLDEN_ROOT / module
    names = _files(produced)
    if os.environ.get(REFRESH_VARIABLE):
        _refresh(produced, golden, names)
    expected = _golden_names(golden) if golden.exists() else []
    assert names == expected, f"{module}: the produced file set differs from the golden one"
    for name in names:
        if name.suffix == TURTLE:
            difference = turtle_difference(produced / name, golden / stored(name))
            assert difference is None, f"{module}/{name} differs as RDF:\n{difference}"
        else:
            produced_text = (produced / name).read_text(encoding="utf-8")
            assert produced_text == (golden / stored(name)).read_text(encoding="utf-8"), (
                f"{module}/{name} differs from the golden text"
            )
