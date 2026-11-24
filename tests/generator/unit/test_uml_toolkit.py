"""The toolkit index the converter looks names, IRIs and slots up in (PD-17, PD-18, PD-20; F-1, F-3, F-11).

The index is read from the toolkit's own metamodel, so each test names a fact of it that a hard-coded
table would get wrong the day the metamodel changes.
"""

import pytest

from rdf_persistence_generation.uml.toolkit import Toolkit, load_toolkit

PROV = "http://www.w3.org/ns/prov#"
SKOS = "http://www.w3.org/2004/02/skos/core#"
DCTERMS = "http://purl.org/dc/terms/"
RP = "https://meaningfy.ws/ns/rdf-persistence#"
CLASS_ANNOTATIONS = {
    "graph",
    "database",
    "rp_path",
    "rp_iri_type",
    "rp_unlabelled",
    "rp_writes",
    "rp_on_referenced_delete",
    "workflow",
}


@pytest.fixture(scope="module")
def toolkit() -> Toolkit:
    return load_toolkit()


def test_the_class_annotations_are_those_the_metamodel_describes_as_class_annotations(
    toolkit: Toolkit,
) -> None:
    assert set(toolkit.class_annotations) == CLASS_ANNOTATIONS, toolkit.class_annotations


def test_a_class_annotation_is_not_one_that_goes_on_a_module_or_a_slot(toolkit: Toolkit) -> None:
    others = {"owned", "module_kind", "toolkit_filled", "bookkeeping"}
    assert not others & set(toolkit.class_annotations), toolkit.class_annotations


def test_a_toolkit_class_is_found_by_its_expanded_class_uri(toolkit: Toolkit) -> None:
    found = toolkit.class_by_uri(PROV + "Activity")
    assert found is not None, "prov:Activity is not found"
    assert found.name == "Activity", found.name


def test_activity_is_not_a_mixin(toolkit: Toolkit) -> None:
    assert toolkit.class_by_name("Activity").mixin is not True, "Activity is a class, not a mixin"


def test_described_is_a_mixin(toolkit: Toolkit) -> None:
    assert toolkit.class_by_name("Described").mixin is True, "Described is a mixin"


def test_a_toolkit_class_is_found_by_its_name(toolkit: Toolkit) -> None:
    assert toolkit.class_by_name("Tracked") is not None, "Tracked is not found"


def test_a_name_that_is_no_toolkit_class_finds_nothing(toolkit: Toolkit) -> None:
    assert toolkit.class_by_name("Book") is None, "Book is not a toolkit class"
    assert toolkit.class_by_uri("https://example.org/ns/library#Book") is None, "no such IRI"


def test_a_toolkit_class_has_the_module_it_is_imported_by(toolkit: Toolkit) -> None:
    assert toolkit.module_of("Activity") == "rdf_persistence/model/rp_provenance"
    assert toolkit.module_of("Described") == "rdf_persistence/model/rp_annotations"


def test_a_toolkit_slot_is_found_by_its_expanded_slot_uri(toolkit: Toolkit) -> None:
    found = toolkit.slot_by_uri(SKOS + "prefLabel")
    assert found is not None, "skos:prefLabel is not found"
    assert found.name == "label", found.name


def test_the_identifier_slot_is_not_offered_for_reuse(toolkit: Toolkit) -> None:
    assert toolkit.slot_by_uri(DCTERMS + "identifier") is None, (
        "dcterms:identifier is `id` (identifier: true), which a drawn attribute must not reuse"
    )


def test_a_slot_that_no_toolkit_slot_has_the_uri_of_finds_nothing(toolkit: Toolkit) -> None:
    assert toolkit.slot_by_uri("https://example.org/ns/library#isbn") is None, "no such IRI"


def test_started_at_time_is_filled_by_the_toolkit(toolkit: Toolkit) -> None:
    assert toolkit.is_filled("started_at_time"), "started_at_time carries toolkit_filled: true"


def test_generated_at_time_is_not_filled_by_the_toolkit(toolkit: Toolkit) -> None:
    assert not toolkit.is_filled("generated_at_time"), (
        "the application writes generated_at_time (F-3)"
    )


def test_the_segment_pattern_of_the_hard_check_is_public_for_the_converter() -> None:
    from rdf_persistence_generation.checks.hard import segment_pattern

    assert segment_pattern().startswith("^"), "the url_segment pattern of the metamodel"


def test_a_slot_the_toolkit_does_not_have_is_not_filled(toolkit: Toolkit) -> None:
    assert not toolkit.is_filled("isbn"), "isbn is no toolkit slot"


def test_convert_uses_the_toolkit_it_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    from rdf_persistence.schema.services.schema import PACKAGE_DIR, load_schema
    from rdf_persistence_generation.config import METAMODEL_ROOT
    from rdf_persistence_generation.uml import toolkit as toolkit_module
    from rdf_persistence_generation.uml.convert import convert
    from tests.generator.uml_model import BOOK, klass, model, settings

    given = Toolkit(load_schema(PACKAGE_DIR / "model" / METAMODEL_ROOT))
    load_toolkit.cache_clear()
    loads: list[object] = []
    real = toolkit_module.load_schema

    def spy(*args: object, **kwargs: object) -> object:
        loads.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(toolkit_module, "load_schema", spy)  # X2

    convert(model(klass(BOOK, "Book")), settings(), given)

    assert loads == [], "convert read the metamodel again instead of using the toolkit it was given"
