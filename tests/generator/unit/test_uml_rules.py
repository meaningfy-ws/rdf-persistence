"""TC-5, TC-9 (same-package half): the plain conversion rules R-1..R-13 and R-19, one table (PD-5..PD-16, D-5, D-10..D-14).

Each row builds a ``UmlModel`` directly (the reader is not involved), converts it and checks the
fragment of LinkML the rule's column promises, or the problem its failure branch gives. The last
test says every ``UmlRule`` value has a row; the rules of stage 2 are marked as such.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from linkml_runtime.dumpers import yaml_dumper

from rdf_persistence_generation.generated.rp_generation import UmlLinkKind, UmlPackage, UmlRule
from tests.generator.uml_model import (
    BOOK,
    CATALOGUE_PKG,
    CHAPTER,
    GENRE,
    LIBRARY_PKG,
    MODEL_PKG,
    SERIES,
    SHELF,
    SHELVES_PKG,
    Converted,
    attribute,
    boundary,
    enumeration,
    generalisation,
    klass,
    link,
    model,
    run,
    tag,
)

Check = Callable[[Converted], None]


@dataclass(frozen=True)
class Row:
    """One rule, one branch: the model it is given, the settings it changes and what must hold."""

    case: str
    rule: UmlRule
    uml: object
    check: Check
    overrides: dict[str, object] = field(default_factory=dict)


def _no_problems(out: Converted) -> None:
    assert out.problems == [], out.problem_texts()


def _problem(rule: UmlRule, *fragments: str) -> Check:
    """The run fails with exactly one problem, of this rule, whose text holds every fragment."""

    def check(out: Converted) -> None:
        assert [p.rule for p in out.problems] == [rule.value], out.problem_texts()
        for fragment in fragments:
            assert fragment in out.problem_texts()[0]

    return check


def _all(*checks: Check) -> Check:
    def check(out: Converted) -> None:
        for each in checks:
            each(out)

    return check


# --- R-1 package module (PD-5, D-5) ---------------------------------------------------------------


def _two_modules(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library", "app_shelves"]
    library = out.schemas["app_library"]
    assert library.id == "https://example.org/ns/library/app_library"
    assert library.annotations["module_kind"].value == "domain"
    assert library.title == "Library"
    assert library.description == "The library package of the app model, converted from UML."
    assert library.imports[0] == "linkml:types"
    assert out.schemas["app"].imports == ["linkml:types", "app_library", "app_shelves"]
    assert out.schemas["app"].version == "1"


def _main_module(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_main"]


def _nested_names(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library__rare_books", "app_rare_books"]


def _package_note(out: Converted) -> None:
    assert out.schemas["app_library"].description == "Everything about books."


def _no_empty_module(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library"]


_RARE = UmlPackage(package_id=5, name="rare-books", parent_id=MODEL_PKG)
_NESTED = UmlPackage(package_id=6, name="rare-books", parent_id=LIBRARY_PKG)
_NOTED = UmlPackage(
    package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG, note=" Everything about books.\r\n"
)
_MAIN_PKG = UmlPackage(package_id=7, name="main", parent_id=MODEL_PKG)
_PACKAGES = (UmlPackage(package_id=MODEL_PKG, name="model"),)

ROWS_R1 = [
    Row(
        "two packages, two modules and a root",
        UmlRule.PACKAGE_MODULE,
        model(klass(BOOK, "lib:Book"), klass(SHELF, "lib:Shelf", SHELVES_PKG)),
        _two_modules,
    ),
    Row(
        "classes in the subtree package go to main",
        UmlRule.PACKAGE_MODULE,
        model(klass(BOOK, "lib:Book", MODEL_PKG)),
        _main_module,
    ),
    Row(
        "a package name is normalised and a nested path is joined by two underscores",
        UmlRule.PACKAGE_MODULE,
        model(
            klass(BOOK, "lib:Book", 5),
            klass(SHELF, "lib:Shelf", 6),
            packages=(
                *_PACKAGES,
                UmlPackage(package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG),
                _RARE,
                _NESTED,
            ),
        ),
        _nested_names,
    ),
    Row(
        "the package note is the module description",
        UmlRule.PACKAGE_MODULE,
        model(klass(BOOK, "lib:Book"), packages=(*_PACKAGES, _NOTED)),
        _package_note,
    ),
    Row(
        "a package with no class has no module",
        UmlRule.PACKAGE_MODULE,
        model(klass(BOOK, "lib:Book")),
        _no_empty_module,
    ),
    Row(
        "failure: a child package named main collides with the classes of the subtree package",
        UmlRule.PACKAGE_MODULE,
        model(
            klass(BOOK, "lib:Book", MODEL_PKG),
            klass(SHELF, "lib:Shelf", 7),
            packages=(*_PACKAGES, _MAIN_PKG),
        ),
        _problem(UmlRule.PACKAGE_MODULE, "app_main"),
    ),
]

# --- R-2 class IRI (PD-6, D-14) -------------------------------------------------------------------


def _implicit_iri(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").class_uri is None


def _foreign_iri(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").class_uri == "bibo:Book"
    assert (
        out.schemas["app_library"].prefixes["bibo"].prefix_reference
        == "http://purl.org/ontology/bibo/"
    )


def _metamodel_prefix(out: Converted) -> None:
    assert out.klass("app_library", "Thing").class_uri == "dcterms:Thing"


ROWS_R2 = [
    Row(
        "an IRI equal to the implicit one is not written",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "lib:Book")),
        _implicit_iri,
    ),
    Row(
        "an unprefixed name has no explicit IRI",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "Book")),
        _implicit_iri,
    ),
    Row(
        "a foreign prefix keeps its IRI",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "bibo:Book")),
        _foreign_iri,
    ),
    Row(
        "a namespace the metamodel names takes the metamodel's prefix",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "dct:Thing")),
        _metamodel_prefix,
    ),
    Row(
        "failure: an unknown prefix is one problem for the prefix",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "zzz:Book"), klass(SHELF, "zzz:Shelf")),
        _problem(UmlRule.CLASS_IRI, "prefix zzz is not in"),
    ),
    Row(
        "failure: one name with two IRIs",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "lib:Book"), klass(SHELF, "bibo:Book", SHELVES_PKG)),
        _problem(
            UmlRule.CLASS_IRI,
            "Book",
            "https://example.org/ns/library#Book",
            "http://purl.org/ontology/bibo/Book",
        ),
    ),
    Row(
        "failure: a name that breaks the lint pattern",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "lib:book")),
        _problem(UmlRule.CLASS_IRI, "does not match"),
    ),
]

# --- R-3 abstract class (D-13) --------------------------------------------------------------------


def _abstract(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").abstract is True
    assert not out.report_lines("ignored_stereotype")


def _concrete(out: Converted) -> None:
    assert not out.klass("app_library", "Book").abstract


ROWS_R3 = [
    Row(
        "the abstract flag",
        UmlRule.ABSTRACT_CLASS,
        model(klass(BOOK, "lib:Book", abstract=True)),
        _abstract,
    ),
    Row(
        "the Abstract stereotype in any case",
        UmlRule.ABSTRACT_CLASS,
        model(klass(BOOK, "lib:Book", stereotype="ABSTRACT")),
        _abstract,
    ),
    Row(
        "failure branch: a concrete class is not abstract",
        UmlRule.ABSTRACT_CLASS,
        model(klass(BOOK, "lib:Book")),
        _concrete,
    ),
]

# --- R-4 generalisation (PD-9) --------------------------------------------------------------------


def _is_a(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").is_a == "Series"
    assert not out.klass("app_library", "Book").mixins


def _is_a_across(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").is_a == "Series"
    assert "app_catalogue" in out.schemas["app_library"].imports


ROWS_R4 = [
    Row(
        "one parent is is_a",
        UmlRule.GENERALISATION,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series"),
            links=(generalisation(1, BOOK, SERIES),),
        ),
        _is_a,
    ),
    Row(
        "a parent in another package is imported",
        UmlRule.GENERALISATION,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series", CATALOGUE_PKG),
            links=(generalisation(1, BOOK, SERIES),),
        ),
        _is_a_across,
    ),
    Row(
        "failure: two domain parents",
        UmlRule.NO_RULE,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series"),
            klass(SHELF, "lib:Shelf"),
            links=(generalisation(1, BOOK, SERIES), generalisation(2, BOOK, SHELF)),
        ),
        _problem(UmlRule.NO_RULE, "Book", "no rule converts it"),
    ),
    Row(
        "failure: a parent outside the converted subtree",
        UmlRule.NO_RULE,
        model(klass(BOOK, "lib:Book"), links=(generalisation(1, BOOK, 999),)),
        _problem(UmlRule.NO_RULE, "Book", "no rule converts it"),
    ),
    Row(
        "failure: a parent that is not generated",
        UmlRule.NO_RULE,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series", stereotype="loaded graph"),
            links=(generalisation(1, BOOK, SERIES),),
        ),
        _problem(UmlRule.NO_RULE, "Book", "no rule converts it"),
    ),
]

# --- R-5 attribute slot (PD-7, D-11, D-12) ----------------------------------------------------------


def _title_slot(out: Converted) -> None:
    _no_problems(out)
    slot = out.slot("app_library", "title")
    assert slot.slot_uri == "dcterms:title"
    assert slot.range == "string"
    assert slot.required is True
    assert not slot.multivalued
    assert out.klass("app_library", "Book").slots == ["title", "subtitle"]


def _range_is(expected: str, minimum: int | None = None) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        slot = out.slot("app_library", "pages")
        assert slot.range == expected
        assert slot.minimum_value == minimum

    return check


def _shape(
    required: bool, multivalued: bool, minimum: int | None, maximum: int | None, slot: str = "pages"
) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        found = out.slot("app_library", slot)
        assert (bool(found.required), bool(found.multivalued)) == (required, multivalued)
        assert (found.minimum_cardinality, found.maximum_cardinality) == (minimum, maximum)

    return check


def _book_with(declared: str = "xsd:string", **bounds: str | None) -> object:
    return model(
        klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:pages", declared, **bounds),))
    )


_XSD = {
    "xsd:string": ("string", None),
    "xsd:normalizedString": ("string", None),
    "xsd:anyURI": ("uri", None),
    "xsd:boolean": ("boolean", None),
    "xsd:date": ("date", None),
    "xsd:dateTime": ("datetime", None),
    "xsd:time": ("time", None),
    "xsd:integer": ("integer", None),
    "xsd:int": ("integer", None),
    "xsd:long": ("integer", None),
    "xsd:nonNegativeInteger": ("integer", 0),
    "xsd:positiveInteger": ("integer", 1),
    "xsd:decimal": ("decimal", None),
    "xsd:double": ("double", None),
    "xsd:float": ("float", None),
}
_BOUNDS = {
    ("1", "1"): (True, False, None, None),
    ("0", "1"): (False, False, None, None),
    ("0", "*"): (False, True, None, None),
    ("1", "*"): (True, True, None, None),
    ("2", "5"): (True, True, 2, 5),
    ("3", "3"): (True, True, 3, 3),
    ("0", "3"): (False, True, None, 3),
}


def _langstring(declared: str) -> Check:
    def check(out: Converted) -> None:
        assert out.problem_texts() == [
            f"[no_rule] Book.pages: {declared} has no toolkit range yet (#209): no rule converts it"
        ]

    return check


def _ignored_stereotype(out: Converted) -> None:
    _no_problems(out)
    assert out.report_lines("ignored_stereotype") == ["Book.pages: stereotype key is not used"]


ROWS_R5 = [
    Row(
        "an attribute is a slot with its IRI, range and bounds, in position order",
        UmlRule.ATTRIBUTE_SLOT,
        model(
            klass(
                BOOK,
                "lib:Book",
                attributes=(
                    attribute(2, BOOK, "lib:subtitle", lower="0", position=2),
                    attribute(1, BOOK, "dct:title", position=1),
                ),
            )
        ),
        _title_slot,
    ),
    Row(
        "an attribute typed by an enumeration ranges over it",
        UmlRule.ATTRIBUTE_SLOT,
        model(
            enumeration(GENRE, "lib:Genre", ("lib:novel",)),
            klass(
                BOOK,
                "lib:Book",
                attributes=(attribute(1, BOOK, "lib:pages", "Genre", classifier=GENRE),),
            ),
        ),
        _range_is("Genre"),
    ),
    *[
        Row(
            f"the XSD map: {declared}",
            UmlRule.ATTRIBUTE_SLOT,
            _book_with(declared),
            _range_is(*expected),
        )
        for declared, expected in _XSD.items()
    ],
    *[
        Row(
            f"attribute bounds {lower}..{upper} as stored",
            UmlRule.ATTRIBUTE_SLOT,
            _book_with(lower=lower, upper=upper),
            _shape(*shape),
        )
        for (lower, upper), shape in _BOUNDS.items()
    ],
    Row(
        "failure: a type no rule maps",
        UmlRule.NO_RULE,
        _book_with("lib:Genre2"),
        _problem(UmlRule.NO_RULE, "Book.pages", "lib:Genre2", "no rule converts it"),
    ),
    Row(
        "failure: rdf:langString (D-12)",
        UmlRule.NO_RULE,
        _book_with("rdf:langString"),
        _langstring("rdf:langString"),
    ),
    Row(
        "failure: rdf:PlainLiteral (D-12)",
        UmlRule.NO_RULE,
        _book_with("rdf:PlainLiteral"),
        _langstring("rdf:PlainLiteral"),
    ),
    Row(
        "failure: bounds that run backwards (D-11)",
        UmlRule.NO_RULE,
        _book_with(lower="2", upper="1"),
        _problem(UmlRule.NO_RULE, "Book.pages", "2..1", "no rule converts it"),
    ),
    Row(
        "an attribute stereotype is reported, not used",
        UmlRule.ATTRIBUTE_SLOT,
        model(
            klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:pages", stereotype="key"),))
        ),
        _ignored_stereotype,
    ),
]

# --- R-6 association slot (PD-8, D-11) ----------------------------------------------------------------


def _both_ends(out: Converted) -> None:
    _no_problems(out)
    shelved = out.slot("app_library", "shelved_on")
    assert (shelved.slot_uri, shelved.range, bool(shelved.required), bool(shelved.multivalued)) == (
        "lib:shelvedOn",
        "Shelf",
        False,
        False,
    )
    assert out.slot("app_library", "books").range == "Book"
    assert out.klass("app_library", "Book").slots == ["shelved_on"]
    assert out.klass("app_library", "Shelf").slots == ["books"]


def _card_shape(card: str | None, shape: tuple[bool, bool, int | None, int | None]) -> Check:
    check_shape = _shape(*shape, slot="has_chapter")

    def check(out: Converted) -> None:
        check_shape(out)
        unspecified = out.report_lines("unspecified_multiplicity")
        assert bool(unspecified) == (not card)

    return check


def _chapter_link(card: str | None) -> object:
    return model(
        klass(BOOK, "lib:Book"),
        klass(CHAPTER, "lib:Chapter"),
        links=(link(1, BOOK, CHAPTER, target_role="lib:hasChapter", target_card=card),),
    )


_CARDS = {
    "1": (True, False, None, None),
    "1..1": (True, False, None, None),
    "0..1": (False, False, None, None),
    "*": (False, True, None, None),
    "0..*": (False, True, None, None),
    "1..*": (True, True, None, None),
    "2..5": (True, True, 2, 5),
    "3": (True, True, 3, 3),
    "0..3": (False, True, None, 3),
    None: (False, True, None, None),
    "": (False, True, None, None),
}

ROWS_R6 = [
    Row(
        "each end with a role is a slot on the other end's class",
        UmlRule.ASSOCIATION_SLOT,
        model(
            klass(BOOK, "lib:Book"),
            klass(SHELF, "lib:Shelf"),
            links=(
                link(
                    1,
                    BOOK,
                    SHELF,
                    target_role="lib:shelvedOn",
                    target_card="0..1",
                    source_role="books",
                    source_card="0..*",
                ),
            ),
        ),
        _both_ends,
    ),
    *[
        Row(
            f"connector card {card!r} (D-11)",
            UmlRule.ASSOCIATION_SLOT,
            _chapter_link(card),
            _card_shape(card, shape),
        )
        for card, shape in _CARDS.items()
    ],
    Row(
        "failure: a malformed card (D-11)",
        UmlRule.NO_RULE,
        _chapter_link("2..1"),
        _problem(UmlRule.NO_RULE, "Book.has_chapter", "2..1", "no rule converts it"),
    ),
    Row(
        "failure: an association with no role",
        UmlRule.NO_RULE,
        model(klass(BOOK, "lib:Book"), klass(SHELF, "lib:Shelf"), links=(link(1, BOOK, SHELF),)),
        _problem(UmlRule.NO_RULE, "no role", "no rule converts it"),
    ),
    Row(
        "failure: a connector stereotype",
        UmlRule.NO_RULE,
        model(
            klass(BOOK, "lib:Book"),
            klass(SHELF, "lib:Shelf"),
            links=(link(1, BOOK, SHELF, target_role="shelf", stereotype="weird"),),
        ),
        _problem(UmlRule.NO_RULE, "weird", "no rule converts it"),
    ),
    Row(
        "failure: an association class",
        UmlRule.NO_RULE,
        model(
            klass(BOOK, "lib:Book"),
            klass(SHELF, "lib:Shelf"),
            links=(
                link(1, BOOK, SHELF, target_role="shelf").model_copy(
                    update={"association_class": "Loan"}
                ),
            ),
        ),
        _problem(UmlRule.NO_RULE, "association class", "no rule converts it"),
    ),
]

# --- R-7 enumeration (PD-10, D-10), R-8 dependency (PD-8) ---------------------------------------------


def _enum(out: Converted) -> None:
    _no_problems(out)
    values = out.enum("app_library", "Genre").permissible_values
    assert list(values) == ["novel", "on_loan"]
    assert values["on_loan"].meaning == "lib:onLoan"
    assert values["on_loan"].title == "On loan"
    assert values["on_loan"].description == "The lib:onLoan."
    assert values["novel"].meaning == "lib:novel"
    assert out.report_lines("implicit_meaning") == [
        "Genre.novel: written without a prefix; meaning lib:novel"
    ]


def _empty_enum(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "pages").range == "uri"
    assert "Genre" not in out.schemas["app_library"].enums
    assert out.report_lines("external_list") == [
        "Genre: no literals; its list is kept outside the model, so slots range over a URI"
    ]


def _dependency(out: Converted) -> None:
    _no_problems(out)
    slot = out.slot("app_library", "genre")
    assert (slot.range, bool(slot.required), bool(slot.multivalued)) == ("Genre", False, False)
    assert out.klass("app_library", "Book").slots == ["genre"]


def _dependency_link(role: str | None, target: int = GENRE) -> object:
    return model(
        enumeration(GENRE, "lib:Genre", ("lib:novel",)),
        klass(BOOK, "lib:Book"),
        links=(
            link(
                1, BOOK, target, kind=UmlLinkKind.DEPENDENCY, target_role=role, target_card="0..1"
            ),
        ),
    )


ROWS_R7 = [
    Row(
        "literals are permissible values, in position order, with a meaning",
        UmlRule.ENUMERATION,
        model(enumeration(GENRE, "lib:Genre", ("novel", "lib:onLoan"))),
        _enum,
    ),
    Row(
        "failure: two literals with one key",
        UmlRule.ENUMERATION,
        model(enumeration(GENRE, "lib:Genre", ("lib:onLoan", "on_loan"))),
        _problem(UmlRule.ENUMERATION, "Genre", "on_loan"),
    ),
    Row(
        "an enumeration with no literals is an external list (D-10)",
        UmlRule.ENUMERATION,
        model(
            enumeration(GENRE, "lib:Genre", ()),
            klass(
                BOOK,
                "lib:Book",
                attributes=(attribute(1, BOOK, "lib:pages", "Genre", classifier=GENRE),),
            ),
        ),
        _empty_enum,
    ),
]

ROWS_R8 = [
    Row(
        "a dependency on an enumeration is an enum-ranged slot",
        UmlRule.DEPENDENCY_ENUM_SLOT,
        _dependency_link("genre"),
        _dependency,
    ),
    Row(
        "failure: a dependency with no role",
        UmlRule.NO_RULE,
        _dependency_link(None),
        _problem(UmlRule.NO_RULE, "no role", "no rule converts it"),
    ),
    Row(
        "failure: a dependency on a class",
        UmlRule.NO_RULE,
        model(
            klass(SERIES, "lib:Series"),
            klass(BOOK, "lib:Book"),
            links=(link(1, BOOK, SERIES, kind=UmlLinkKind.DEPENDENCY, target_role="series"),),
        ),
        _problem(UmlRule.NO_RULE, "Book.series", "no rule converts it"),
    ),
]

# --- R-9 notes, R-19 titles (PD-6, PD-11) ----------------------------------------------------------------


def _descriptions(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").description == "Line one.\nLine two."
    assert out.slot("app_library", "pages").description == "The pages."
    assert out.slot("app_library", "shelf").description == "On a shelf."
    assert not out.report_lines("no_note")


def _no_note(out: Converted) -> None:
    assert out.klass("app_library", "Book").description is None
    assert out.report_lines("no_note") == ["Book: no note, so no description"]


def _titles(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "ISBNRecordFile").title == "ISBN record file"
    assert out.klass("app_library", "Book").title == "Printed book"
    assert out.slot("app_library", "has_chapter").title == "Has chapter"


ROWS_R9 = [
    Row(
        "notes of a class, an attribute and a connector are descriptions",
        UmlRule.NOTES_DESCRIPTION,
        model(
            klass(
                BOOK,
                "lib:Book",
                note="  Line one.\r\nLine two.\n ",
                attributes=(attribute(1, BOOK, "lib:pages", note="The pages."),),
            ),
            klass(SHELF, "lib:Shelf"),
            links=(link(1, BOOK, SHELF, target_role="shelf", note="On a shelf."),),
        ),
        _descriptions,
    ),
    Row(
        "failure branch: an empty note is no description and a report line",
        UmlRule.NOTES_DESCRIPTION,
        model(klass(BOOK, "lib:Book", note=" ")),
        _no_note,
    ),
    Row(
        "a title is the alias, else the name in words",
        UmlRule.TITLE,
        model(
            klass(BOOK, "lib:Book", alias="Printed book"),
            klass(SHELF, "lib:ISBNRecordFile"),
            links=(link(1, BOOK, SHELF, target_role="lib:hasChapter"),),
        ),
        _titles,
    ),
]

# --- R-10 roots, R-11 ownership (PD-12, PD-13) -----------------------------------------------------------


def _root(out: Converted) -> None:
    _no_problems(out)
    book = out.klass("app_library", "Book")
    assert book.mixins == ["AggregateRoot"]
    assert book.annotations["rp_path"].value == "books"
    assert "rdf_persistence/model/rp_core" in out.schemas["app_library"].imports


def _root_path(out: Converted) -> None:
    assert out.klass("app_library", "Book").annotations["rp_path"].value == "tomes"


def _owned(multivalued: bool) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        slot = out.slot("app_library", "has_chapter")
        assert slot.annotations["owned"].value == "true"
        assert bool(slot.inlined_as_list) is multivalued
        assert bool(slot.inlined) is not multivalued

    return check


def _not_owned(out: Converted) -> None:
    _no_problems(out)
    assert "owned" not in out.slot("app_library", "has_chapter").annotations


def _book_chapter(
    card: str,
    *,
    boundaries: tuple = (),
    source_aggregate: int = 0,
    target_aggregate: int = 0,
    root: str | None = "root",
) -> object:
    return model(
        klass(BOOK, "lib:Book", stereotype=root),
        klass(CHAPTER, "lib:Chapter"),
        links=(
            link(
                1,
                BOOK,
                CHAPTER,
                target_role="lib:hasChapter",
                target_card=card,
                source_aggregate=source_aggregate,
                target_aggregate=target_aggregate,
            ),
        ),
        boundaries=boundaries,
    )


ROWS_R10 = [
    Row(
        "a root has the aggregate-root mixin and a derived path",
        UmlRule.ROOT_CLASS,
        model(klass(BOOK, "lib:Book", stereotype="root")),
        _root,
    ),
    Row(
        "a rp_path tagged value overrides the derived path",
        UmlRule.ROOT_CLASS,
        model(klass(BOOK, "lib:Book", stereotype="root"), tags=(tag(BOOK, "rp_path", "tomes"),)),
        _root_path,
    ),
    Row(
        "failure: two roots with one path",
        UmlRule.ROOT_CLASS,
        model(
            klass(BOOK, "lib:Book", stereotype="root"),
            klass(SERIES, "lib:Volume", stereotype="root"),
            tags=(tag(SERIES, "rp_path", "books"),),
        ),
        _problem(UmlRule.ROOT_CLASS, "books", "Book", "Volume"),
    ),
    Row(
        "a part in the root's boundary is owned, inlined as a list when many",
        UmlRule.BOUNDARY_OWNED,
        _book_chapter("1..*", boundaries=(boundary(20, BOOK, CHAPTER),)),
        _owned(True),
    ),
    Row(
        "an owned single slot is inlined",
        UmlRule.BOUNDARY_OWNED,
        _book_chapter("1..1", boundaries=(boundary(20, BOOK, CHAPTER),)),
        _owned(False),
    ),
    Row(
        "a composite association owns its destination",
        UmlRule.BOUNDARY_OWNED,
        _book_chapter("0..*", source_aggregate=2, root=None),
        _owned(True),
    ),
    Row(
        "a plain association outside a boundary is a reference",
        UmlRule.BOUNDARY_OWNED,
        _book_chapter("0..*", root=None),
        _not_owned,
    ),
    Row(
        "failure: a boundary with no root",
        UmlRule.NO_RULE,
        _book_chapter("1..*", boundaries=(boundary(20, BOOK, CHAPTER),), root=None),
        _problem(UmlRule.NO_RULE, "Aggregate", "root", "no rule converts it"),
    ),
    Row(
        "failure: the part points at its whole as a composite",
        UmlRule.NO_RULE,
        _book_chapter("1..*", target_aggregate=2, root=None),
        _problem(UmlRule.NO_RULE, "Book.has_chapter", "no rule converts it"),
    ),
]

# --- R-12 not generated (PD-15), R-13 shared slot (PD-16), D-5, the stage-1 limit ---------------------------


def _not_generated(out: Converted) -> None:
    _no_problems(out)
    assert "Series" not in out.schemas["app_library"].classes
    assert out.slot("app_library", "series").range == "uri"
    assert out.report_lines("not_generated") == ["Series: stereotype loaded graph, not generated"]


def _outside(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "series").range == "uri"
    assert [line.split(":")[0] for line in out.report_lines("outside_link")] == ["Book.series"]


def _excluded(out: Converted) -> None:
    _no_problems(out)
    assert "series" not in out.schemas["app_library"].slots
    assert [line.split(":")[0] for line in out.report_lines("excluded_link")] == [
        "Book.series -> Series"
    ]


def _shared(out: Converted) -> None:
    _no_problems(out)
    isbn = out.slot("app_library", "isbn")
    assert isbn.required is True
    assert "isbn" in out.klass("app_library", "Book").slots
    assert "isbn" in out.klass("app_library", "Series").slots
    assert not out.klass("app_library", "Book").slot_usage
    assert out.klass("app_library", "Series").slot_usage["isbn"].required is False
    assert [name for name in out.schemas["app_library"].slots if name == "isbn"] == ["isbn"]


def _merged(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library"]
    assert sorted(out.schemas["app_library"].classes) == ["Book", "Shelf"]
    assert out.schemas["app"].imports == ["linkml:types", "app_library"]
    assert out.report_lines("merged_cycle") == [
        "app_library: the packages library, shelves are written as one module"
    ]


_SHARED = (
    klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:isbn"),)),
    klass(SERIES, "lib:Series", attributes=(attribute(2, SERIES, "lib:isbn", lower="0"),)),
)

ROWS_R12 = [
    Row(
        "a not-generated stereotype makes no class, a report line and a URI range",
        UmlRule.NOT_GENERATED,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series", stereotype="loaded graph"),
            links=(link(1, BOOK, SERIES, target_role="series"),),
        ),
        _not_generated,
    ),
    Row(
        "a link to a class the model does not hold is a URI range and a report line",
        UmlRule.NOT_GENERATED,
        model(klass(BOOK, "lib:Book"), links=(link(1, BOOK, 999, target_role="series"),)),
        _outside,
    ),
    Row(
        "a link to a class in an excluded package makes no slot and a report line",
        UmlRule.NOT_GENERATED,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series", CATALOGUE_PKG),
            links=(link(1, BOOK, SERIES, target_role="series"),),
        ),
        _excluded,
        {"exclude_packages": ["catalogue"]},
    ),
    Row(
        "failure: a stereotype no rule knows",
        UmlRule.NO_RULE,
        model(klass(BOOK, "lib:Book", stereotype="gadget")),
        _problem(UmlRule.NO_RULE, "Book", "gadget", "no rule converts it"),
    ),
    Row(
        "one slot name on two classes of a module is one shared slot with a slot_usage",
        UmlRule.SHARED_SLOT,
        model(*_SHARED),
        _shared,
    ),
    Row(
        "failure: one slot name with two IRIs",
        UmlRule.CLASS_IRI,
        model(
            klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:isbn"),)),
            klass(SERIES, "lib:Series", attributes=(attribute(2, SERIES, "bibo:isbn"),)),
        ),
        _problem(
            UmlRule.CLASS_IRI,
            "isbn",
            "https://example.org/ns/library#isbn",
            "http://purl.org/ontology/bibo/isbn",
        ),
    ),
    Row(
        "two packages that refer to each other are written as one module (D-5)",
        UmlRule.PACKAGE_MODULE,
        model(
            klass(BOOK, "lib:Book"),
            klass(SHELF, "lib:Shelf", SHELVES_PKG),
            links=(link(1, BOOK, SHELF, target_role="shelf", source_role="featured"),),
        ),
        _merged,
    ),
    Row(
        "stage-1 limit: a slot used in two modules is a problem",
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        model(
            klass(
                BOOK, "lib:Book", CATALOGUE_PKG, attributes=(attribute(1, BOOK, "lib:hasParent"),)
            ),
            klass(
                SHELF, "lib:Shelf", SHELVES_PKG, attributes=(attribute(2, SHELF, "lib:hasParent"),)
            ),
        ),
        _problem(
            UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
            "has_parent: used in app_catalogue, app_shelves; slots shared across packages arrive in stage 2 (task 2.6)",
        ),
    ),
]

ROWS: list[Row] = [
    *ROWS_R1,
    *ROWS_R2,
    *ROWS_R3,
    *ROWS_R4,
    *ROWS_R5,
    *ROWS_R6,
    *ROWS_R7,
    *ROWS_R8,
    *ROWS_R9,
    *ROWS_R10,
    *ROWS_R12,
]

STAGE_2 = {
    UmlRule.TOOLKIT_SLOT,
    UmlRule.TENANT_ROOT,
    UmlRule.CLASS_ANNOTATION,
    UmlRule.UNIQUE_KEY,
    UmlRule.ABSTRACT_ROOT,
    UmlRule.TOOLKIT_MIXINS,
    UmlRule.LEFT_OUT_LINK,
    UmlRule.ACTIVITY_ROOT,
}


def test_the_schemas_dump_to_yaml_the_way_the_toolkit_writes_them() -> None:
    out = run(
        _book_chapter("1..*", boundaries=(boundary(20, BOOK, CHAPTER),)),
    )
    text = yaml_dumper.dumps(out.schemas["app_library"])
    wanted = (
        "value: domain",
        "tag: rp_path",
        "value: books",
        "tag: owned",
        "inlined_as_list: true",
    )
    for line in wanted:
        assert line in text, text


@pytest.mark.parametrize(
    "row", [pytest.param(row, id=f"{row.rule.value}: {row.case}") for row in ROWS]
)
def test_a_rule_row(row: Row) -> None:
    row.check(run(row.uml, **row.overrides))


@pytest.mark.parametrize(
    "rule",
    [
        pytest.param(rule, marks=pytest.mark.xfail(strict=True, reason="stage 2"))
        if rule in STAGE_2
        else rule
        for rule in UmlRule
    ],
)
def test_every_uml_rule_has_a_row(rule: UmlRule) -> None:
    assert rule in {row.rule for row in ROWS}
