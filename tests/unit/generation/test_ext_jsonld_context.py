"""Step 5 (PD-12, PD-25): the JSON-LD context and one frame per aggregate type, on the toy library."""

import json
from pathlib import Path

import pytest
from pyld import jsonld  # type: ignore[import-untyped]

from rdf_persistence.generation.extensions.jsonld_context import CONTEXT_STEP

from .step_runner import assert_json_golden, run_toy

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
def staged(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return run_toy(CONTEXT_STEP, tmp_path_factory.mktemp("context")) / "python"


def read(staged: Path, name: str) -> dict:
    document: dict = json.loads((staged / name).read_text(encoding="utf-8"))
    return document


def test_the_output_equals_the_golden(staged: Path) -> None:
    assert_json_golden("jsonld_context", staged)


def test_one_frame_per_aggregate_type_and_the_tenant_root(staged: Path) -> None:
    frames = sorted(p.name for p in staged.glob("*.frame.jsonld"))
    assert frames == [
        "Book.frame.jsonld",
        "Library.frame.jsonld",
        "LibraryAccess.frame.jsonld",
        "Scan.frame.jsonld",
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
    again = run_toy(CONTEXT_STEP, tmp_path) / "python"
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
