"""The SPARQL term models of the technical ``templates`` group (technical-models PD-5, D-1).

TC-19 pins the text of every query the task touches against strings captured before the change
(``golden/term_models_sparql.json``, written by ``temp/capture_golden.py`` against the code as it
was): the rendered text must not change, whatever the placeholders are called inside.
"""

import ast
import json
from contextlib import suppress
from pathlib import Path
from string import Template
from types import ModuleType

import pytest
from pydantic import ValidationError
from rdflib import Literal, URIRef

from rdf_persistence.core.domain.exceptions import SparqlError
from rdf_persistence.core.domain.generated.rp_core import AggregateKey, RegistryEntry, RegistryKind
from rdf_persistence.core.domain.sparql import (
    SparqlTerm,
    count,
    match_patterns,
    order_by,
    term,
    term_list,
)
from rdf_persistence.services import listing, migrations, session, unique_keys
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.generated.service.rp_service import (
    Condition,
    ListPlan,
    Migration,
    MigrationStep,
)
from rdf_persistence.services.generated.templates.rp_templates import (
    KeyBranchTerms,
    KeyHeldTerms,
    ListingTerms,
    OwnerTerms,
    RegistryTerms,
    StampGuardTerms,
)
from rdf_persistence.services.listing import listing_query
from rdf_persistence.services.migrations import migration_request
from rdf_persistence.services.session import remove_parts, replace_parts
from rdf_persistence.services.unique_keys import KeyClaim, diagnosis, duplicates_query, guard
from rdf_persistence.services.vocabulary import (
    key_branch_terms,
    key_held_terms,
    listing_terms,
    owner_terms,
    registry_terms,
    stamp_guard_terms,
)

GOLDEN = Path(__file__).parent / "golden" / "term_models_sparql.json"
EX = "https://example.org/"
REGISTRY = URIRef(EX + "registry")
KEY = AggregateKey(
    key_name="isbn_key", root_class=EX + "Book", key_predicates=[EX + "isbn", EX + "edition"]
)
CLAIM_A = KeyClaim(KEY, EX + "a", (Literal("978"), Literal(2)))
CLAIM_B = KeyClaim(KEY, EX + "b", (Literal("979"), Literal(3)))
EXCLUDED = [URIRef(EX + "a"), URIRef(EX + "b")]
SORTED_PLAN = ListPlan(
    target=EX + "Book",
    conditions=[Condition(predicate=EX + "title", value="Dune")],
    sort_by=EX + "title",
    descending=True,
    limit=10,
    offset=20,
    hidden_graphs=[EX + "g1", EX + "g2"],
)
IRI_PLAN = ListPlan(target=EX + "Book", limit=5, offset=0)
STEP = MigrationStep(
    title="rename",
    where_pattern="?s <https://example.org/old> ?o",
    delete_pattern="?s <https://example.org/old> ?o",
    insert_pattern="?s <https://example.org/new> ?o",
)
STAMPS = URIRef(EX + "stamps")
GRAPH, ROOT, MARKER = URIRef(EX + "graph"), URIRef(EX + "root"), URIRef(EX + "marker")
ENTRIES = [
    RegistryEntry(graph=EX + "graph", kind=RegistryKind.AGGREGATE, owned_by=EX + "root"),
    RegistryEntry(graph=EX + "loaded", kind=RegistryKind.LOADED_GRAPH, owned_by=EX + "root"),
]
DEPENDENTS = [(URIRef(EX + "Comment"), URIRef(EX + "target"))]


def rendered() -> dict[str, str]:
    """The query text of each template the task touches, for the fixed inputs above."""
    schema = Migration(schema_id=EX + "schema", from_version="1", to_version="2", steps=[STEP])
    stamp_only = Migration(schema_id=EX + "schema", from_version="1", to_version="2")
    return {
        "GUARD": str(guard(CLAIM_A, REGISTRY, EXCLUDED)),
        "DIAGNOSIS": diagnosis([CLAIM_A, CLAIM_B], REGISTRY, EXCLUDED),
        "DUPLICATES": duplicates_query(KEY, REGISTRY),
        "LISTING_BY_SLOT": listing_query(REGISTRY, SORTED_PLAN),
        "LISTING_BY_IRI": listing_query(REGISTRY, IRI_PLAN),
        "MIGRATION_WITH_STEP": migration_request(schema, STAMPS),
        "MIGRATION_STAMP_ONLY": migration_request(stamp_only, STAMPS),
        "REPLACE": replace_parts(GRAPH, REGISTRY, ROOT, MARKER, "v1", [], ENTRIES)[1],
        "REMOVE": remove_parts(GRAPH, REGISTRY, ROOT, MARKER, "v1")[1],
        "REMOVE_WITH_DEPENDENTS": remove_parts(GRAPH, REGISTRY, ROOT, MARKER, "v1", DEPENDENTS)[1],
    }


def old_key_held_dict(values: SparqlTerm) -> dict[str, SparqlTerm]:
    """What ``unique_keys._held_around`` built before the change, written out from the vocabulary."""
    return {
        "values": values,
        "registry": term(REGISTRY),
        "p_kind": term(v.REGISTRY_KIND),
        "aggregate": term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE]),
        "p_owned_by": term(v.REGISTRY_OWNED_BY),
        "excluded": term_list(EXCLUDED),
    }


def test_key_held_terms_hold_the_values_of_the_old_dict_key_for_key():
    """TC-18: ``key_held_terms(R, values=v, excluded=[a, b])`` is a ``KeyHeldTerms`` of those values."""
    values = match_patterns("key_root", [(URIRef(EX + "isbn"), Literal("978"))])

    bundle = key_held_terms(REGISTRY, values=values, excluded=EXCLUDED)

    assert isinstance(bundle, KeyHeldTerms)
    assert dict(bundle) == old_key_held_dict(values)
    assert all(isinstance(value, SparqlTerm) for _, value in bundle)


def test_key_branch_terms_add_the_index_to_the_key_held_terms():
    """TC-18: a branch of the diagnosis is a ``KeyHeldTerms`` with the claim's ``index``."""
    values = match_patterns("key_root", [(URIRef(EX + "isbn"), Literal("978"))])

    branch = key_branch_terms(REGISTRY, values=values, excluded=EXCLUDED, index=count(3))

    assert isinstance(branch, KeyBranchTerms)
    assert isinstance(branch, KeyHeldTerms)
    assert dict(branch) == {**old_key_held_dict(values), "index": count(3)}


def test_owner_terms_hold_the_root_and_the_fixed_vocabulary():
    """TC-18: the owner patterns' bundle is the four terms ``session._owner_terms`` built."""
    bundle = owner_terms(ROOT)

    assert isinstance(bundle, OwnerTerms)
    assert dict(bundle) == {
        "root": term(ROOT),
        "p_owned_by": term(v.REGISTRY_OWNED_BY),
        "p_kind": term(v.REGISTRY_KIND),
        "loaded": term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
    }


def test_owner_terms_are_no_registry_terms():
    """TC-18: the owner bundle has no ``registry`` (PD-5), so it is not a ``RegistryTerms``."""
    assert not isinstance(owner_terms(ROOT), RegistryTerms)
    assert isinstance(registry_terms(REGISTRY), RegistryTerms)


def test_listing_terms_hold_the_fixed_vocabulary_and_the_varying_fields():
    """TC-18: the listing's bundle names the class ``target``; the sort predicate is optional."""
    page = {"order": order_by(("root", False)), "limit": count(5), "offset": count(0)}
    unsorted = listing_terms(
        REGISTRY, target=URIRef(EX + "Book"), patterns=term_list([]), hidden=term_list([]), **page
    )
    by_slot = listing_terms(
        REGISTRY,
        target=URIRef(EX + "Book"),
        patterns=term_list([]),
        hidden=term_list([]),
        sort=URIRef(EX + "title"),
        **page,
    )

    assert isinstance(unsorted, ListingTerms)
    assert unsorted.p_sort is None
    assert by_slot.p_sort == term(URIRef(EX + "title"))
    assert unsorted.target == term(URIRef(EX + "Book"))
    assert unsorted.aggregate == term(v.REGISTRY_KIND_IRIS[RegistryKind.AGGREGATE])
    assert unsorted.p_listed_in == term(v.LISTED_IN)
    assert unsorted.p_total == term(v.TOTAL)


def test_stamp_guard_terms_hold_the_stamps_the_schema_and_the_version_stamped():
    """TC-18: the migration operations' shared guard, with ``from_version`` for the old ``from``."""
    bundle = stamp_guard_terms(STAMPS, schema_id=URIRef(EX + "schema"), from_version="1")

    assert isinstance(bundle, StampGuardTerms)
    assert dict(bundle) == {
        "stamps": term(STAMPS),
        "schema_id": term(URIRef(EX + "schema")),
        "p_stamp": term(v.DATA_SCHEMA_VERSION),
        "from_version": term(Literal("1")),
    }


@pytest.mark.parametrize("field", ["values", "registry", "p_kind", "aggregate", "excluded"])
def test_a_term_model_refuses_a_raw_string(field):
    """TC-20: ``KeyHeldTerms(values="raw", ...)`` is a ``ValidationError``, for every field."""
    good = dict(key_held_terms(REGISTRY, values=term(URIRef(EX + "x")), excluded=EXCLUDED))

    with pytest.raises(ValidationError):
        KeyHeldTerms(**{**good, field: "raw"})


def _placeholders(module: ModuleType) -> set[str]:
    """The names of every ``$placeholder`` of every string constant of the module."""
    found: set[str] = set()
    for value in vars(module).values():
        if isinstance(value, str) and "$" in value:
            with suppress(ValueError):
                found |= set(Template(value).get_identifiers())
    return found


def _placeholder_dicts(module: ModuleType) -> list[int]:
    """The line of each dict literal of the module that is keyed by a template's placeholder."""
    names = _placeholders(module)
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Dict)
        and any(isinstance(k, ast.Constant) and k.value in names for k in node.keys)
    ]


@pytest.mark.parametrize("module", [unique_keys, session, listing, migrations])
def test_no_dict_literal_is_keyed_by_a_templates_placeholders(module):
    """TC-21: a template's terms are a model, never a dict literal keyed by its placeholders."""
    assert _placeholder_dicts(module) == []


def test_the_placeholder_check_finds_a_dict_it_should(tmp_path):
    """TC-21: the check is not blind: it flags a dict keyed by a placeholder of the module's own."""
    source = tmp_path / "probe.py"
    source.write_text("terms = {'registry': 1}\nother = {'k': 2}\n", encoding="utf-8")
    probe = ModuleType("probe")
    probe.__file__ = str(source)
    probe.TEMPLATE = "FILTER $registry"

    assert _placeholder_dicts(probe) == [1]


def test_the_query_text_is_what_it_was_before_the_term_models():
    """TC-19: guard, diagnosis, duplicates, listing, migration and owner patterns, as captured.

    Passes on the code before the change by design: it is the golden the change must not move.
    """
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    now = rendered()

    assert now.keys() == golden.keys()
    assert {name: text for name, text in now.items() if text != golden[name]} == {}


# -- the tester's invariants over the factories and templates (kept: one property each) --------------

HARMFUL_IRIS = [EX + "a>b", EX + "a b", EX + "a> } DROP ALL { <x", "", EX + 'a"b', EX + "a\nb"]
SOME_VALUES = term(URIRef(EX + "v"))


def _a_listing(registry: URIRef = REGISTRY, **changes: object) -> ListingTerms:
    kwargs: dict[str, object] = {
        "target": URIRef(EX + "T"),
        "patterns": SOME_VALUES,
        "hidden": SOME_VALUES,
        "order": SOME_VALUES,
        "limit": count(1),
        "offset": count(0),
    }
    return listing_terms(registry, **(kwargs | changes))  # type: ignore[arg-type]


FACTORIES_BY_THE_IRI_THEY_TAKE = {
    "registry-of-registry_terms": lambda bad: registry_terms(URIRef(bad)),
    "registry-of-key_held_terms": lambda bad: key_held_terms(
        URIRef(bad), values=SOME_VALUES, excluded=[]
    ),
    "registry-of-key_branch_terms": lambda bad: key_branch_terms(
        URIRef(bad), values=SOME_VALUES, excluded=[], index=count(0)
    ),
    "registry-of-listing_terms": lambda bad: _a_listing(URIRef(bad)),
    "an-excluded-root": lambda bad: key_held_terms(
        REGISTRY, values=SOME_VALUES, excluded=[URIRef(EX + "ok"), URIRef(bad)]
    ),
    "the-root-of-owner_terms": lambda bad: owner_terms(URIRef(bad)),
    "the-stamps-of-stamp_guard_terms": lambda bad: stamp_guard_terms(
        URIRef(bad), schema_id=URIRef(EX + "s"), from_version="1"
    ),
    "the-schema-of-stamp_guard_terms": lambda bad: stamp_guard_terms(
        URIRef(EX + "st"), schema_id=URIRef(bad), from_version="1"
    ),
    "the-target-of-a-listing": lambda bad: _a_listing(target=URIRef(bad)),
    "the-sort-of-a-listing": lambda bad: _a_listing(sort=URIRef(bad)),
}


@pytest.mark.parametrize("bad", HARMFUL_IRIS)
@pytest.mark.parametrize(
    "make", FACTORIES_BY_THE_IRI_THEY_TAKE.values(), ids=list(FACTORIES_BY_THE_IRI_THEY_TAKE)
)
def test_an_iri_that_could_change_the_querys_meaning_is_refused_before_a_model_exists(make, bad):
    """Attacks the factories: an IRI that breaks out of its brackets is a ``SparqlError``, whichever field takes it."""
    with pytest.raises(SparqlError):
        make(bad)


def test_no_stale_class_from_or_schema_placeholder_remains_in_a_migrated_template():
    """Attacks the renames ``$class`` to ``$target``, ``$from`` to ``$from_version``, ``$schema`` to ``$schema_id``."""
    migrated = {
        "listing._MATCHING": listing._MATCHING,
        "listing._LISTING": listing._LISTING,
        "listing._COUNT": listing._COUNT,
        "listing._PAGE_BY_IRI": listing._PAGE_BY_IRI,
        "listing._PAGE_BY_SLOT": listing._PAGE_BY_SLOT,
        "migrations._STEP": migrations._STEP,
        "migrations._ROTATION": migrations._ROTATION,
        "migrations._STAMP_MOVE": migrations._STAMP_MOVE,
        "session.REPLACE": session.REPLACE,
        "session.REMOVE": session.REMOVE,
        "session._DROP_DEPENDENTS": session._DROP_DEPENDENTS,
        "unique_keys.KEY_HELD": unique_keys.KEY_HELD,
        "unique_keys._GUARD": unique_keys._GUARD,
        "unique_keys._BRANCH": unique_keys._BRANCH,
        "unique_keys._DIAGNOSIS": unique_keys._DIAGNOSIS,
        "unique_keys._DUPLICATES": unique_keys._DUPLICATES,
    }
    stale = {"class", "from", "schema"}
    leftovers = {
        name: sorted(stale & set(Template(text.replace("%s", "")).get_identifiers()))
        for name, text in migrated.items()
    }
    assert {name: found for name, found in leftovers.items() if found} == {}
