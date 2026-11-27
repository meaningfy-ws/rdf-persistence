"""Step 5 (PD-12, PD-25): the JSON-LD context and one frame per aggregate type, on the toy library."""

import json
from pathlib import Path

import pytest
from pyld import jsonld

from rdf_persistence.schema.services.schema import PACKAGE_DIR
from rdf_persistence_generation.config import GENERATOR_DIR
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.extensions.jsonld_context import render, render_context
from rdf_persistence_generation.steps import CONTEXT_STEP

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
    assert_matches_toy(
        rendered, "domain/generated/context.jsonld", "domain/generated/*.frame.jsonld"
    )


ACTIVITY_FRAMES = [
    "Activity.frame.jsonld",
    "Add.frame.jsonld",
    "Assignment.frame.jsonld",
    "DeleteFile.frame.jsonld",
    "PostComment.frame.jsonld",
    "PostReply.frame.jsonld",
    "Remove.frame.jsonld",
    "Replace.frame.jsonld",
    "Transition.frame.jsonld",
]


def test_one_frame_per_aggregate_type_the_tenant_root_and_each_activity(staged: Path) -> None:
    frames = sorted(p.name for p in staged.glob("*.frame.jsonld"))
    assert frames == sorted(
        [
            "Author.frame.jsonld",
            "Book.frame.jsonld",
            "BookCollection.frame.jsonld",
            "Display.frame.jsonld",
            "Library.frame.jsonld",
            "LibraryAccess.frame.jsonld",
            "Loan.frame.jsonld",
            "Magazine.frame.jsonld",
            "Pamphlet.frame.jsonld",
            "Review.frame.jsonld",
            "Scan.frame.jsonld",
            "Shelf.frame.jsonld",
            "Template.frame.jsonld",
            "ApproveBook.frame.jsonld",
            "ShelveBooks.frame.jsonld",
            *ACTIVITY_FRAMES,
        ]
    ), "a frame per root, the tenant root, and Activity with every descendant of the closure"


def test_the_metamodel_has_a_frame_per_activity_class_and_its_root_frames_stay() -> None:
    names = sorted(f.name for f in render(PACKAGE_DIR / "model" / "rp.yaml") if "frame" in f.name)
    assert names == sorted(
        ["Comment.frame.jsonld", "TenantAccess.frame.jsonld"] + ACTIVITY_FRAMES
    ), "one frame for each activity class of the toolkit beside the two root frames"


def test_the_replace_frame_nests_the_generations_and_invalidations(staged: Path) -> None:
    frame = read(staged, "Replace.frame.jsonld")
    assert frame["@type"] == "Replace", "a Replace has no subclass"
    assert frame["generations"]["@type"] == "Generation", "generations nest"
    assert frame["invalidations"]["@type"] == "Invalidation", "invalidations nest"
    assert frame["was_associated_with"]["@embed"] == "@never", "principals stay IRIs"


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


@pytest.mark.parametrize(
    ("scope", "container"),
    [("Display", "@set"), (None, None)],
    ids=["made-multivalued-by-the-class", "single-valued-where-declared"],
)
def test_a_slot_made_multivalued_by_a_class_is_a_set_in_that_class_only(
    staged: Path, scope: str | None, container: str | None
) -> None:
    """#302: `features` is single-valued at module level; Display's slot_usage makes it a list."""
    context = read(staged, "context.jsonld")["@context"]
    terms = context[scope].get("@context", {}) if scope else context
    assert terms["features"].get("@container") == container, (
        f"features in {scope or 'the global context'} has container {terms['features'].get('@container')}"
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
        "annotate": "http://www.w3.org/ns/odrl/2/annotate",
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


FIELD_NAME_SCHEMA = """id: https://example.org/ns/tiny
name: tiny
title: Tiny
description: A module with a slot that keeps its name.
prefixes: {tiny: "https://example.org/ns/tiny#", schema: "https://schema.org/", linkml: "https://w3id.org/linkml/"}
default_prefix: tiny
default_range: string
imports: [linkml:types]
classes:
  Target:
    title: Target
    description: A target.
    slots: [schema_file, plain]
slots:
  schema_file:
    title: Schema file
    description: The schema file, wired as `schema`.
    alias: schema
    annotations:
      field_name: slot
  plain:
    title: Plain
    description: A slot with an alias and no opt-in.
    alias: other
"""


def test_a_slot_annotated_field_name_slot_keeps_its_slot_name_as_its_term(tmp_path: Path) -> None:
    """D-55 (9): `schema_file` (alias `schema`) is the term `schema_file`; no term `schema` shadows the prefix."""
    schema = tmp_path / "tiny.yaml"
    schema.write_text(FIELD_NAME_SCHEMA, encoding="utf-8")
    context = json.loads(render_context(schema))["@context"]
    assert "schema_file" in context, f"the slot keeps its name: {sorted(context)}"
    assert context.get("schema") == "https://schema.org/", f"`schema` is the prefix: {context}"
    assert "other" in context, "a slot with an alias and no opt-in keeps its alias as its term"


def test_the_generated_context_of_the_generation_model_keeps_its_prefix_and_kind_terms() -> None:
    """D-55 (9): in `rp_generation`, `schema` is not a term over `schema_file`; `kind` is the slot over `ConstraintKind`."""
    context_file = GENERATOR_DIR / "generated" / "context.jsonld"
    context = json.loads(context_file.read_text(encoding="utf-8"))["@context"]
    assert not isinstance(context.get("schema"), dict), f"`schema` shadows the prefix: {context}"
    assert "schema_file" in context, "the slot's name is its term"
    assert context["kind"]["@id"] == "constraintKind", (
        f"`kind` is not the slot `kind`'s: {context['kind']}"
    )


USAGE_SCHEMA = """id: https://example.org/ns/usage
name: usage
title: Usage
description: Classes that narrow a slot in different ways.
prefixes: {usage: "https://example.org/ns/usage#", linkml: "https://w3id.org/linkml/"}
default_prefix: usage
default_range: string
imports: [linkml:types]
classes:
  Both:
    title: Both
    description: Narrows the range of `single` and makes it multivalued.
    slots: [single]
    slot_usage:
      single: {range: integer, multivalued: true}
  Parent:
    title: Parent
    description: Makes `single` multivalued.
    slots: [single]
    slot_usage:
      single: {multivalued: true}
  Child:
    title: Child
    description: Inherits the usage of its parent.
    is_a: Parent
  Reverse:
    title: Reverse
    description: Makes `many` single-valued.
    slots: [many]
    slot_usage:
      many: {multivalued: false}
  Plain:
    title: Plain
    description: Uses both slots as declared.
    slots: [single, many]
  Abstract:
    title: Abstract
    description: An abstract class that makes `single` multivalued; it has no node.
    abstract: true
    slots: [single]
    slot_usage:
      single: {multivalued: true}
  Mixed:
    title: Mixed
    description: A mixin that makes `single` multivalued; it has no node.
    mixin: true
    slots: [single]
    slot_usage:
      single: {multivalued: true}
slots:
  single:
    title: Single
    description: A single-valued slot.
  many:
    title: Many
    description: A multivalued slot.
    multivalued: true
"""


def usage_context(tmp_path: Path) -> dict:
    schema = tmp_path / "usage.yaml"
    schema.write_text(USAGE_SCHEMA, encoding="utf-8")
    context: dict = json.loads(render_context(schema))["@context"]
    return context


def scoped_terms(context: dict, scope: str) -> dict:
    """The type-scoped terms of the class ``scope``; empty when it has none."""
    class_term = context.get(scope)
    return class_term.get("@context", {}) if isinstance(class_term, dict) else {}


@pytest.mark.parametrize(
    ("scope", "term", "scoped", "container"),
    [
        ("Both", "single", True, "@set"),
        ("Parent", "single", True, "@set"),
        ("Child", "single", True, "@set"),
        ("Reverse", "many", True, None),
        ("Plain", "single", False, None),
        ("Plain", "many", False, None),
    ],
    ids=[
        "both-usages",
        "own-usage",
        "inherited-usage",
        "multivalued-to-single",
        "single-as-declared",
        "multivalued-as-declared",
    ],
)
def test_a_class_scopes_a_slot_by_how_it_uses_it(
    tmp_path: Path, scope: str, term: str, scoped: bool, container: str | None
) -> None:
    entry = scoped_terms(usage_context(tmp_path), scope).get(term)
    assert (entry is not None) == scoped, f"{scope} scoped term for {term}: {entry}"
    assert (entry or {}).get("@container") == container, f"{term} in {scope}: {entry}"


@pytest.mark.parametrize(
    ("term", "container"), [("single", None), ("many", "@set")], ids=["single", "multivalued"]
)
def test_the_global_term_keeps_the_slot_as_declared(
    tmp_path: Path, term: str, container: str | None
) -> None:
    entry = usage_context(tmp_path)[term]
    assert entry.get("@container") == container, f"global {term}: {entry}"


def test_a_range_narrowing_and_a_multivalued_usage_keep_both_terms(tmp_path: Path) -> None:
    entry = scoped_terms(usage_context(tmp_path), "Both").get("single", {})
    assert entry.get("@type") == "xsd:integer", f"the narrowed range is lost: {entry}"
    assert entry.get("@container") == "@set", f"the multivalued usage is lost: {entry}"


@pytest.mark.parametrize("name", ["Abstract", "Mixed"])
def test_a_class_without_a_node_gets_no_scoped_term(tmp_path: Path, name: str) -> None:
    assert scoped_terms(usage_context(tmp_path), name) == {}, f"{name} has no node type"
