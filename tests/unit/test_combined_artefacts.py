"""The combined RDF artefacts stay what 0.6.0 shipped (domain-model-per-theme TC-03, RISK-2).

The domain classes generate into five theme packages, but the shapes, the JSON-LD context, the frames and
the migration lock stay one combined set, built from every domain module into ``core`` (DEC-2). The
copies in ``tests/fixtures/v0_6_0/`` are the files of the ``v0.6.0`` tag, taken before the move; a
regeneration must reproduce them byte for byte. No git call at test time.
"""

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "v0_6_0"
GENERATED = ROOT / "rdf_persistence" / "core" / "domain" / "generated"
LOCK = ROOT / "rdf_persistence" / "model" / "migrations" / "schema.lock.json"


def _artefacts() -> list[tuple[Path, Path]]:
    """``(fixture, regenerated file)`` for each shapes, context, frame and lock copy."""
    pairs = [
        (fixture, GENERATED / fixture.name)
        for fixture in sorted(FIXTURES.iterdir())
        if fixture.name != "schema.lock.json"
    ]
    return [*pairs, (FIXTURES / "schema.lock.json", LOCK)]


def test_the_fixtures_hold_the_four_artefact_kinds():
    names = {fixture.name for fixture, _ in _artefacts()}

    assert {"shapes.ttl", "context.jsonld", "schema.lock.json"} <= names
    assert any(name.endswith(".frame.jsonld") for name in names), "no frame copied"


@pytest.mark.parametrize(("fixture", "regenerated"), _artefacts(), ids=lambda path: path.name)
def test_a_combined_artefact_is_byte_identical_to_its_0_6_0_copy(fixture: Path, regenerated: Path):
    assert regenerated.is_file(), f"{regenerated} is missing: the combined set stays in core"

    assert regenerated.read_bytes() == fixture.read_bytes(), (
        f"{regenerated.relative_to(ROOT)} differs from its v0.6.0 copy"
    )


def test_no_frame_is_added_or_lost():
    fixtures = {f.name for f in FIXTURES.glob("*.frame.jsonld")}
    generated = {f.name for f in GENERATED.glob("*.frame.jsonld")}

    assert generated == fixtures, f"frames differ: {sorted(generated ^ fixtures)}"
