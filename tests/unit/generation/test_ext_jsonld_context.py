"""Step 5 (PD-12, PD-25): the JSON-LD context and one frame per aggregate type, on the toy library."""

import json
from pathlib import Path

import pytest
from pyld import jsonld

from rdf_persistence.generation.exceptions import SchemaGenerationError
from rdf_persistence.generation.extensions.jsonld_context import render_context
from rdf_persistence.generation.steps import CONTEXT_STEP

from .golden import TOY_TARGET, assert_matches_toy, run_toy

BOOK = "https://example.org/books/1"
BOOK_BODY = {
    "id": BOOK,
    "type": "Book",
    "label": "Dune",
    "description": "A desert planet.",
    "isbn": "9780441172719",
    "authors": ["Frank Herbert"],
    "published": "1965-08-01",
    "chapters": [
        {
            "id": f"{BOOK}/c1",
            "type": "Chapter",
            "number": 1,
            "notes": [
                {"id": f"{BOOK}/c1/n1", "type": "Note", "label": "Opening", "text": "Water."}
            ],
        },
        {"id": f"{BOOK}/c2", "type": "Chapter", "number": 2},
    ],
}


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_toy(CONTEXT_STEP, tmp_path_factory.mktemp("context"))


@pytest.fixture(scope="module")
def staged(rendered: Path) -> Path:
    return rendered / str(TOY_TARGET.python)


def read(staged: Path, name: str) -> dict:
    document: dict = json.loads((staged / name).read_text(encoding="utf-8"))
    return document


def test_the_output_equals_the_committed_tree(rendered: Path) -> None:
    assert_matches_toy(rendered, "generated/context.jsonld", "generated/*.frame.jsonld")


def test_one_frame_per_aggregate_type_and_the_tenant_root(staged: Path) -> None:
    frames = sorted(p.name for p in staged.glob("*.frame.jsonld"))
    assert frames == [
        "Book.frame.jsonld",
        "Library.frame.jsonld",
        "LibraryAccess.frame.jsonld",
        "Scan.frame.jsonld",
        "Shelf.frame.jsonld",
    ], "a frame per class with AggregateRoot ancestry, and the tenant root"


def test_id_and_type_are_aliased(staged: Path) -> None:
    context = read(staged, "context.jsonld")["@context"]
    assert (context["id"], context["type"]) == ("@id", "@type"), (
        "id and type are the JSON-LD keywords"
    )


def test_an_internal_slot_is_left_out_of_the_context(staged: Path) -> None:
    text = (staged / "context.jsonld").read_text(encoding="utf-8")
    assert "file_key" not in text, "StoredFile.file_key is internal"
    assert "file_name" in text, "the other StoredFile slots stay"


def test_the_book_frame_nests_chapters_and_their_notes(staged: Path) -> None:
    frame = read(staged, "Book.frame.jsonld")
    assert frame["@context"] == "context.jsonld", "the frame sits beside its context"
    assert frame["chapters"]["notes"]["@embed"] == "@always", "notes nest under chapters"


def test_the_output_is_reproducible(staged: Path, tmp_path: Path) -> None:
    again = run_toy(CONTEXT_STEP, tmp_path) / str(TOY_TARGET.python)
    first = {p.name: p.read_bytes() for p in staged.iterdir()}
    assert first == {p.name: p.read_bytes() for p in again.iterdir()}, "two runs differ"


def test_framing_the_triples_of_a_book_returns_the_body(staged: Path) -> None:
    context = read(staged, "context.jsonld")["@context"]
    expanded = jsonld.expand(BOOK_BODY, {"expandContext": context})
    triples = jsonld.to_rdf(expanded, {"format": "application/n-quads"})
    flat = jsonld.from_rdf(triples, {"format": "application/n-quads", "useNativeTypes": True})
    frame = read(staged, "Book.frame.jsonld") | {"@context": context}
    assert jsonld.frame(flat, frame) == {"@context": context, **BOOK_BODY}, (
        "the framed book differs"
    )


def test_the_context_is_json_ld_1_1(staged: Path) -> None:
    context = read(staged, "context.jsonld")["@context"]
    assert context["@version"] == 1.1, "property-scoped contexts need JSON-LD 1.1"


@pytest.mark.parametrize("term", ["target", "graph", "loaded_graph", "owned_by"])
def test_a_uri_ranged_slot_is_an_iri(staged: Path, term: str) -> None:
    context = read(staged, "context.jsonld")["@context"]
    assert context[term]["@type"] == "@id", f"{term} has range uri, which the shapes read as an IRI"


def test_an_enum_slot_maps_each_value_to_its_meaning_iri(staged: Path) -> None:
    action = read(staged, "context.jsonld")["@context"]["action"]
    assert action["@type"] == "@vocab", "the values of an enum are terms, read as IRIs"
    assert action["@context"] == {
        "read": "http://www.w3.org/ns/odrl/2/read",
        "modify": "http://www.w3.org/ns/odrl/2/modify",
        "delete": "http://www.w3.org/ns/odrl/2/delete",
        "administer": "https://meaningfy.ws/ns/rdf-persistence#administer",
    }, "one term per permissible value, its meaning expanded"


def test_an_enum_value_is_stored_as_its_meaning_and_compacted_back(staged: Path) -> None:
    context = read(staged, "context.jsonld")["@context"]
    node = {"@context": context, "id": "https://example.org/g", "action": "read"}
    (expanded,) = jsonld.expand(node)
    assert expanded["http://www.w3.org/ns/odrl/2/action"] == [
        {"@id": "http://www.w3.org/ns/odrl/2/read"}
    ], "the value expands to the IRI that the shapes list"
    assert jsonld.compact(expanded, context)["action"] == "read", "and compacts back to the term"


ENUMS = """
id: https://example.org/ns/enums
name: enums
prefixes: {s: "https://example.org/ns/s#", linkml: "https://w3id.org/linkml/"}
default_prefix: s
default_range: string
imports: [linkml:types]
classes:
  Thing:
    slots: [color]
slots:
  color:
    range: Color
enums:
  Color:
    permissible_values:
      red: {%s}
      blue: {%s}
"""


def render_enums(tmp_path: Path, red: str, blue: str) -> dict:
    path = tmp_path / "enums.yaml"
    path.write_text(ENUMS % (red, blue), encoding="utf-8")
    context: dict = json.loads(render_context(path))["@context"]
    return context


def test_an_enum_without_meanings_keeps_its_plain_values(tmp_path: Path) -> None:
    color = render_enums(tmp_path, "", "")["color"]
    assert "@context" not in color, "no meaning, no term to map"
    assert "@type" not in color, "the values stay literals, as the shapes list them"


def test_an_enum_with_some_meanings_only_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SchemaGenerationError, match="every value a meaning"):
        render_enums(tmp_path, "meaning: s:Red", "")
