"""The combined RDF artefacts stay one set in ``core`` (domain-model-per-theme TC-03, RISK-2).

The domain classes generate into five theme packages, but the shapes, the JSON-LD context, the frames and
the migration lock stay one combined set, built from every domain module into ``core`` (DEC-2). The
frame copies in ``tests/fixtures/v0_6_0/`` are the files of the ``v0.6.0`` tag, taken before the move; no
frame is added or lost. The shapes, context and lock are no longer pinned byte for byte to 0.6.0: the
model changed on purpose (collection-has-part, PD-10). The content is proved by ``make check-generated``
(committed artefacts equal a regeneration) and by the model-shape snapshot. No git call at test time.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "v0_6_0"
GENERATED = ROOT / "rdf_persistence" / "core" / "domain" / "generated"
LOCK = ROOT / "rdf_persistence" / "model" / "migrations" / "schema.lock.json"


def test_the_combined_set_holds_the_four_artefact_kinds_in_core():
    assert (GENERATED / "shapes.ttl").is_file(), "the combined shapes stay in core"
    assert (GENERATED / "context.jsonld").is_file(), "the combined JSON-LD context stays in core"
    assert any(GENERATED.glob("*.frame.jsonld")), "no frame in core"
    assert LOCK.is_file(), "the toolkit's migration lock stays beside the metamodel"


def test_no_frame_is_added_or_lost():
    fixtures = {f.name for f in FIXTURES.glob("*.frame.jsonld")}
    generated = {f.name for f in GENERATED.glob("*.frame.jsonld")}

    assert generated == fixtures, f"frames differ: {sorted(generated ^ fixtures)}"
