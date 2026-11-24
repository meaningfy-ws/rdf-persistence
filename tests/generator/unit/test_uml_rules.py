"""TC-5, TC-9: the conversion rules R-1..R-29, one table (PD-5..PD-21, D-5, D-10..D-14).

Each row builds a ``UmlModel`` directly (the reader is not involved), converts it and checks the
fragment of LinkML the rule's column promises, or the problem its failure branch gives. The last
test says every ``UmlRule`` value has a row.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import yaml
from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model.meta import UniqueKey
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence_generation.generated.rp_generation import (
    UmlAttribute,
    UmlLinkKind,
    UmlPackage,
    UmlPrefix,
    UmlRule,
)
from tests.generator.uml_model import (
    BIDIRECTIONAL,
    BOOK,
    CATALOGUE_PKG,
    CHAPTER,
    DIRECTED,
    EXTERNAL_PKG,
    GENRE,
    LIBRARY_PKG,
    MODEL_PKG,
    PREFIXES,
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
from tests.generator.unit.uml_role_rows import ROLE_ROWS
from tests.generator.unit.uml_workflow_rows import WORKFLOW_ROWS

Check = Callable[[Converted], None]


@dataclass(frozen=True)
class Row:
    """One rule, one branch: the model it is given, the settings it changes and what must hold."""

    case: str
    rule: UmlRule
    uml: object
    check: Check
    overrides: dict[str, object] = field(default_factory=dict)
    cites: str | None = None  # the R-n this row proves, as the UmlRule descriptions cite it


def _no_problems(out: Converted) -> None:
    assert out.problems == [], out.problem_texts()


def _problem(rule: UmlRule, *fragments: str) -> Check:
    """The run fails with exactly one problem, of this rule, whose text holds every fragment."""

    def check(out: Converted) -> None:
        assert [p.rule for p in out.problems] == [rule.value], out.problem_texts()
        for fragment in fragments:
            assert fragment in out.problem_texts()[0], (
                f"the problem must say {fragment!r}: {out.problem_texts()}"
            )

    return check


def _all(*checks: Check) -> Check:
    def check(out: Converted) -> None:
        for each in checks:
            each(out)

    return check


# --- R-1 package module (PD-5, D-5) ---------------------------------------------------------------


def _two_modules(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library", "app_shelves"], (
        "a module per package, a root"
    )
    library = out.schemas["app_library"]
    assert library.id == "https://example.org/ns/library/app_library", "the id is base + module"
    assert library.annotations["module_kind"].value == "domain", "the module is a domain module"
    assert library.title == "Library", "the title is the package name in words"
    assert library.description == "The library package of the app model, converted from UML.", (
        "the description is the default one"
    )
    assert library.imports[0] == "linkml:types", "the module imports the LinkML types first"
    assert out.schemas["app"].imports == ["linkml:types", "app_library", "app_shelves"], (
        "the root imports every module"
    )
    assert out.schemas["app"].version == "1", "the root carries the version"


def _main_module(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_main"], "the subtree package's classes go to main"


def _nested_names(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library__rare_books", "app_rare_books"], (
        "a nested path is joined by two underscores and never collides with a single segment"
    )


def _package_note(out: Converted) -> None:
    assert out.schemas["app_library"].description == "Everything about books.", (
        "the package note, trimmed, is the module description"
    )


def _no_empty_module(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library"], "a package with no class has no module"


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
        cites="R-1",
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
    assert out.klass("app_library", "Book").class_uri is None, "an implicit IRI is not written"


def _foreign_iri(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").class_uri == "bibo:Book", "a foreign IRI is kept"
    assert (
        out.schemas["app_library"].prefixes["bibo"].prefix_reference
        == "http://purl.org/ontology/bibo/"
    ), "the foreign prefix is declared"


def _metamodel_prefix(out: Converted) -> None:
    assert out.klass("app_library", "Thing").class_uri == "dcterms:Thing", (
        "the metamodel's prefix name is used"
    )


ROWS_R2 = [
    Row(
        "an IRI equal to the implicit one is not written",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "lib:Book")),
        _implicit_iri,
        cites="R-2",
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
        "failure: a domain class named like a toolkit class is a problem naming both (S-11)",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "lib:Activity")),
        _problem(
            UmlRule.CLASS_IRI,
            "Activity",
            "https://example.org/ns/library#Activity",
            "http://www.w3.org/ns/prov#Activity",
        ),
    ),
    Row(
        "failure: a domain class named like a toolkit mixin is a problem naming both (S-11)",
        UmlRule.CLASS_IRI,
        model(klass(BOOK, "lib:Described")),
        _problem(
            UmlRule.CLASS_IRI,
            "Described",
            "https://example.org/ns/library#Described",
            "https://meaningfy.ws/ns/rdf-persistence#Described",
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
    assert out.klass("app_library", "Book").abstract is True, "the class is abstract"
    assert not out.report_lines("ignored_stereotype"), "the Abstract stereotype is not reported"


def _concrete(out: Converted) -> None:
    assert not out.klass("app_library", "Book").abstract, "a concrete class is not abstract"


ROWS_R3 = [
    Row(
        "the abstract flag",
        UmlRule.ABSTRACT_CLASS,
        model(klass(BOOK, "lib:Book", abstract=True)),
        _abstract,
        cites="R-3",
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
    assert out.klass("app_library", "Book").is_a == "Series", "the one parent is is_a"
    assert not out.klass("app_library", "Book").mixins, "a domain parent is no mixin"


def _is_a_across(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "Book").is_a == "Series", "the parent is is_a"
    assert "app_catalogue" in out.schemas["app_library"].imports, "the parent's module is imported"


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
        cites="R-4",
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
    assert slot.slot_uri == "dcterms:title", "the slot keeps its IRI"
    assert slot.range == "string", "xsd:string is string"
    assert slot.required is True, "a lower bound of 1 is required"
    assert not slot.multivalued, "an upper bound of 1 is single-valued"
    assert out.klass("app_library", "Book").slots == ["title", "subtitle"], (
        "the class lists its slots in attribute order"
    )


def _range_is(expected: str, minimum: int | None = None) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        slot = out.slot("app_library", "pages")
        assert slot.range == expected, f"the range of the slot is {expected}"
        assert slot.minimum_value == minimum, f"the minimum value is {minimum}"

    return check


def _shape(
    required: bool, multivalued: bool, minimum: int | None, maximum: int | None, slot: str = "pages"
) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        found = out.slot("app_library", slot)
        assert (bool(found.required), bool(found.multivalued)) == (required, multivalued), (
            f"required and multivalued of {slot}"
        )
        assert (found.minimum_cardinality, found.maximum_cardinality) == (minimum, maximum), (
            f"the cardinalities of {slot}"
        )

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
        ], f"{declared} is refused, never narrowed to a string"

    return check


def _ignored_stereotype(out: Converted) -> None:
    _no_problems(out)
    assert out.report_lines("ignored_stereotype") == ["Book.pages: stereotype key is not used"], (
        "an attribute stereotype is reported, not used"
    )


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
        cites="R-5",
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
    *[
        Row(
            f"failure: an attribute written {written!r} is not a valid local name (D-29 C-1)",
            UmlRule.ATTRIBUTE_SLOT,
            model(klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, written),))),
            _problem(
                UmlRule.ATTRIBUTE_SLOT, "Book.has title", "'has title' is not a valid local name"
            ),
        )
        for written in ("has title", "lib:has title")
    ],
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
    ), "the destination role is a slot on the source"
    assert out.slot("app_library", "books").range == "Book", (
        "the source role is a slot on the target"
    )
    assert out.klass("app_library", "Book").slots == ["shelved_on"], "Book lists its role"
    assert out.klass("app_library", "Shelf").slots == ["books"], "Shelf lists its role"


def _card_shape(card: str | None, shape: tuple[bool, bool, int | None, int | None]) -> Check:
    check_shape = _shape(*shape, slot="has_chapter")

    def check(out: Converted) -> None:
        check_shape(out)
        unspecified = out.report_lines("unspecified_multiplicity")
        assert bool(unspecified) == (not card), "only a missing multiplicity is reported"

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
        cites="R-6",
    ),
    *[
        Row(
            f"failure: a role written {written!r} is not a valid local name (D-29 C-1)",
            UmlRule.ATTRIBUTE_SLOT,
            model(
                klass(BOOK, "lib:Book"),
                klass(SHELF, "lib:Shelf"),
                links=(link(1, BOOK, SHELF, target_role=written, target_card="0..1"),),
            ),
            _problem(
                UmlRule.ATTRIBUTE_SLOT, "Book.has title", "'has title' is not a valid local name"
            ),
        )
        for written in ("has title", "lib:has title")
    ],
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
    assert list(values) == ["novel", "on_loan"], "the literals are keys in snake case, in order"
    assert values["on_loan"].meaning == "lib:onLoan", "a prefixed literal is its own meaning"
    assert values["on_loan"].title == "On loan", "the title is the literal in words"
    assert values["on_loan"].description == "The lib:onLoan.", "the note is the description"
    assert values["novel"].meaning == "lib:novel", "an unprefixed literal gets the default prefix"
    assert out.report_lines("implicit_meaning") == [
        "Genre.novel: written without a prefix; meaning lib:novel"
    ], "the implicit meaning is reported"


def _empty_enum(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "pages").range == "uri", (
        "a slot to an empty enumeration is a URI"
    )
    assert "Genre" not in out.schemas["app_library"].enums, "an empty enumeration makes no enum"
    assert out.report_lines("external_list") == [
        "Genre: no literals; its list is kept outside the model, so slots range over a URI"
    ], "the empty list is reported"


def _dependency(out: Converted) -> None:
    _no_problems(out)
    slot = out.slot("app_library", "genre")
    assert (slot.range, bool(slot.required), bool(slot.multivalued)) == ("Genre", False, False), (
        "a dependency is a slot ranged by the enumeration"
    )
    assert out.klass("app_library", "Book").slots == ["genre"], "the source lists the slot"


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
        cites="R-7",
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
    *[
        Row(
            f"failure: a literal written {written!r} is not a valid local name (D-29 C-1)",
            UmlRule.CLASS_IRI,
            model(enumeration(GENRE, "lib:Genre", (written,))),
            _problem(UmlRule.CLASS_IRI, "Genre.on loan", "'on loan' is not a valid local name"),
        )
        for written in ("on loan", "lib:on loan")
    ],
]

ROWS_R8 = [
    Row(
        "a dependency on an enumeration is an enum-ranged slot",
        UmlRule.DEPENDENCY_ENUM_SLOT,
        _dependency_link("genre"),
        _dependency,
        cites="R-8",
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
    assert out.klass("app_library", "Book").description == "Line one.\nLine two.", (
        "line ends are normalised and the note is trimmed"
    )
    assert out.slot("app_library", "pages").description == "The pages.", "an attribute's note"
    assert out.slot("app_library", "shelf").description == "On a shelf.", "a connector's note"
    assert not out.report_lines("no_note"), "an element with a note has no no-note line"


def _no_note(out: Converted) -> None:
    assert out.klass("app_library", "Book").description is None, "no placeholder description"
    assert out.report_lines("no_note") == ["Book: no note, so no description"], (
        "the missing note is reported"
    )


def _titles(out: Converted) -> None:
    _no_problems(out)
    assert out.klass("app_library", "ISBNRecordFile").title == "ISBN record file", (
        "capitals stay capitals in a split name"
    )
    assert out.klass("app_library", "Book").title == "Printed book", "the alias is the title"
    assert out.slot("app_library", "has_chapter").title == "Has chapter", "a slot's title"


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
        cites="R-9",
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
        cites="R-19",
    ),
]

# --- R-10 roots, R-11 ownership (PD-12, PD-13) -----------------------------------------------------------


def _root(out: Converted) -> None:
    _no_problems(out)
    book = out.klass("app_library", "Book")
    assert book.mixins == ["AggregateRoot"], "a root has the aggregate-root mixin"
    assert book.annotations["rp_path"].value == "books", "its path is the plural in kebab case"
    assert "rdf_persistence/model/rp_core" in out.schemas["app_library"].imports, (
        "the module imports the toolkit's core"
    )


def _root_path(out: Converted) -> None:
    assert out.klass("app_library", "Book").annotations["rp_path"].value == "tomes", (
        "the tagged path wins over the derived one"
    )


def _owned(multivalued: bool) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        slot = out.slot("app_library", "has_chapter")
        assert slot.annotations["owned"].value == "true", "the slot is owned"
        assert bool(slot.inlined_as_list) is multivalued, "a many slot is inlined as a list"
        assert bool(slot.inlined) is not multivalued, "a single slot is inlined"

    return check


def _not_owned(out: Converted) -> None:
    _no_problems(out)
    assert "owned" not in out.slot("app_library", "has_chapter").annotations, (
        "a plain reference is not owned"
    )


def _book_chapter(
    card: str,
    *,
    boundaries: tuple = (),
    source_aggregate: int = 0,
    target_aggregate: int = 0,
    root: str | None = "root",
    tags: tuple = (),
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
        tags=tags,
    )


ROWS_R10 = [
    Row(
        "a root has the aggregate-root mixin and a derived path",
        UmlRule.ROOT_CLASS,
        model(klass(BOOK, "lib:Book", stereotype="root")),
        _root,
        cites="R-10",
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
        cites="R-11",
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

# --- R-20 class tagged values (PD-20, DEC-2) -------------------------------------------------------------


def _annotated(**expected: str) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        annotations = out.klass("app_library", "Book").annotations
        assert {name: annotations[name].value for name in expected} == expected, (
            "the class carries the annotations its tagged values name"
        )

    return check


def _ignored_class_tag(out: Converted) -> None:
    _no_problems(out)
    assert out.report_lines("ignored_tag") == ["Book: tagged value junctionKind is not used"], (
        "an unknown tag is reported"
    )
    assert "junctionKind" not in out.klass("app_library", "Book").annotations, (
        "an unknown tag is not written"
    )


def _tagged_root(*tags: object, stereotype: str | None = "root") -> object:
    return model(klass(BOOK, "lib:Book", stereotype=stereotype), tags=tuple(tags))


ROWS_R20 = [
    Row(
        "a tag named like a class annotation becomes that annotation",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "rp_writes", "service"), tag(BOOK, "database", "system")),
        _annotated(rp_writes="service", database="system", rp_path="books"),
        cites="R-20",
    ),
    Row(
        "the workflow tag is the workflow annotation",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "workflow", "review")),
        _annotated(workflow="review"),
    ),
    Row(
        "a part takes class annotations too",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "rp_unlabelled", "true"), stereotype=None),
        _annotated(rp_unlabelled="true"),
    ),
    Row(
        "failure: a value outside the annotation's values",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "rp_writes", "sometimes")),
        _problem(
            UmlRule.CLASS_ANNOTATION,
            "Book",
            "rp_writes: 'sometimes' is not one of ('service', 'toolkit')",
        ),
    ),
    Row(
        "failure: a path that does not follow the segment pattern",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "rp_path", "Books")),
        _problem(UmlRule.CLASS_ANNOTATION, "Book", "rp_path: 'Books' does not match"),
    ),
    Row(
        "failure: a workflow name that does not follow the segment pattern",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "workflow", "Two Words")),
        _problem(UmlRule.CLASS_ANNOTATION, "Book", "workflow: 'Two Words' does not match"),
    ),
    Row(
        "failure: a tag named like an annotation of another element",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "owned", "true")),
        _problem(UmlRule.CLASS_ANNOTATION, "Book", "owned", "is not a class annotation"),
    ),
    Row(
        "any other tag is an ignored-tag line",
        UmlRule.CLASS_ANNOTATION,
        _tagged_root(tag(BOOK, "junctionKind", "x")),
        _ignored_class_tag,
    ),
]

# --- R-21 unique keys (PD-21, DEC-3) ---------------------------------------------------------------------

_KEYED = (
    attribute(11, BOOK, "lib:title", position=0),
    attribute(12, BOOK, "lib:subtitle", position=1),
    attribute(13, BOOK, "lib:hasIsbn", position=2),
)


def _keyed(*tags: object, stereotype: str | None = "root") -> object:
    return model(
        klass(BOOK, "lib:Book", stereotype=stereotype, attributes=_KEYED), tags=tuple(tags)
    )


def _key(name: str, slots: list[str], *, scope: str | None, nulls_equal: bool) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        assert _key_names(out) == [name], "the class has the one key"
        found = out.klass("app_library", "Book").unique_keys[name]
        assert isinstance(found, UniqueKey), "the key is a unique key"
        assert [str(slot) for slot in found.unique_key_slots] == slots, "the key's slots"
        assert found.consider_nulls_inequal is (False if nulls_equal else None), "the nulls clause"
        if scope is None:
            assert "rp_unique_scope" not in found.annotations, "a part's key has no scope"
        else:
            assert found.annotations["rp_unique_scope"].value == scope, "a root's key is scoped"

    return check


def _key_names(out: Converted) -> list[str]:
    """The names of the class's keys; the runtime's key mapping also lists its own ``_if_missing`` hook."""
    return sorted(n for n in out.klass("app_library", "Book").unique_keys if not n.startswith("_"))


def _two_keys(out: Converted) -> None:
    _no_problems(out)
    assert _key_names(out) == ["by_isbn", "by_title"], "each tag gives one key"


def _key_problem(*fragments: str) -> Check:
    return _problem(UmlRule.UNIQUE_KEY, "Book", "unique_key", *fragments)


_BAD_KEY = "k title"

ROWS_R21 = [
    Row(
        "a key on a root is scoped to the tenant, nulls equal",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: title, subtitle; nulls=equal")),
        _key("k", ["title", "subtitle"], scope="tenant", nulls_equal=True),
        cites="R-21",
    ),
    Row(
        "a key on a part has no scope",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: title, subtitle; nulls=equal"), stereotype=None),
        _key("k", ["title", "subtitle"], scope=None, nulls_equal=True),
    ),
    Row(
        "a key without the nulls clause leaves the default, whitespace is free",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "  k :title ,subtitle  ")),
        _key("k", ["title", "subtitle"], scope="tenant", nulls_equal=False),
    ),
    Row(
        "an attribute is named by its slot or by its UML name",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: title, hasIsbn")),
        _key("k", ["title", "has_isbn"], scope="tenant", nulls_equal=False),
    ),
    Row(
        "an attribute named by its slot",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: has_isbn")),
        _key("k", ["has_isbn"], scope="tenant", nulls_equal=False),
    ),
    Row(
        "the tag may repeat, one key each",
        UmlRule.UNIQUE_KEY,
        _keyed(
            tag(BOOK, "unique_key", "by_title: title"), tag(BOOK, "unique_key", "by_isbn: hasIsbn")
        ),
        _two_keys,
    ),
    Row(
        "failure: no colon",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", _BAD_KEY)),
        _key_problem(repr(_BAD_KEY)),
    ),
    Row(
        "failure: no attribute after the colon",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k:")),
        _key_problem("'k:'"),
    ),
    Row(
        "failure: another clause than nulls=equal",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: title; nulls=unequal")),
        _key_problem("nulls=unequal"),
    ),
    Row(
        "failure: an attribute the class does not have",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: title, nothing")),
        _key_problem("'k: title, nothing'", "nothing"),
    ),
    Row(
        "failure: a name that is not an identifier",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "1k: title")),
        _key_problem("1k"),
    ),
    Row(
        "failure: two keys with one name",
        UmlRule.UNIQUE_KEY,
        _keyed(tag(BOOK, "unique_key", "k: title"), tag(BOOK, "unique_key", "k: subtitle")),
        _key_problem("k", "twice"),
    ),
]

# --- R-12 not generated (PD-15), R-13 shared slot (PD-16), D-5, the stage-1 limit ---------------------------


def _not_generated(out: Converted) -> None:
    _no_problems(out)
    assert "Series" not in out.schemas["app_library"].classes, "the class is not generated"
    assert out.slot("app_library", "series").range == "uri", "a slot to it is a URI"
    assert out.report_lines("not_generated") == [
        "Series: stereotype loaded graph, not generated"
    ], "the class is reported"


def _not_generated_link(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "series").range == "uri", "the slot ranges over a URI"
    assert len(out.report_lines("not_generated")) == 1, "one report line, the class's"
    assert out.report_lines("outside_link") == [], "a not-generated class is not an outside link"
    assert out.report_lines("excluded_link") == [], "a not-generated class is not an excluded link"


def _outside(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "series").range == "uri", "a link outside the subtree is a URI"
    assert [line.split(":")[0] for line in out.report_lines("outside_link")] == ["Book.series"], (
        "the outside link is reported once, naming the slot"
    )


def _excluded(out: Converted) -> None:
    _no_problems(out)
    assert "series" not in out.schemas["app_library"].slots, (
        "a link to an excluded class makes no slot"
    )
    assert [line.split(":")[0] for line in out.report_lines("excluded_link")] == [
        "Book.series -> Series"
    ], "the excluded link is reported as <Source>.<role> -> <Target>"


_EXCLUDED_MODEL = model(
    klass(BOOK, "lib:Book"),
    links=(link(1, BOOK, SERIES, target_role="series"),),
    packages=(
        UmlPackage(package_id=MODEL_PKG, name="model"),
        UmlPackage(package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG),
    ),
    outside=(klass(SERIES, "lib:Series", CATALOGUE_PKG),),
    outside_packages=(UmlPackage(package_id=CATALOGUE_PKG, name="catalogue", parent_id=MODEL_PKG),),
)


def test_a_link_end_the_model_lists_nowhere_is_an_internal_error() -> None:
    uml = model(klass(BOOK, "lib:Book"), links=(link(1, BOOK, 999, target_role="series"),))

    with pytest.raises(LookupError, match="999"):
        run(uml)


def _shared(out: Converted) -> None:
    _no_problems(out)
    isbn = out.slot("app_library", "isbn")
    assert not isbn.required, "the slot is required on one usage only, so it states no required"
    assert "isbn" in out.klass("app_library", "Book").slots, "Book has the slot"
    assert "isbn" in out.klass("app_library", "Series").slots, "Series has the slot"
    assert out.klass("app_library", "Book").slot_usage["isbn"].required is True, (
        "Book, the required usage, carries required in its slot_usage"
    )
    series = out.klass("app_library", "Series").slot_usage["isbn"]
    assert series.required is False, "Series states required: false, or it would inherit a true"
    assert series.multivalued is None, "Series has nothing else of its own"
    assert [name for name in out.schemas["app_library"].slots if name == "isbn"] == ["isbn"], (
        "the slot is defined once"
    )


def _merged(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_library"], "the two packages are one module"
    assert sorted(out.schemas["app_library"].classes) == ["Book", "Shelf"], "it holds both classes"
    assert out.schemas["app"].imports == ["linkml:types", "app_library"], "the root imports it once"
    assert out.report_lines("merged_cycle") == [
        "app_library: the packages library, shelves are written as one module"
    ], "the merge is reported"


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
        cites="R-12",
    ),
    Row(
        "a link to a class outside the subtree is a URI range and a report line (D-17)",
        UmlRule.LEFT_OUT_LINK,
        model(
            klass(BOOK, "lib:Book"),
            links=(link(1, BOOK, SERIES, target_role="series"),),
            outside=(klass(SERIES, "ext:Series", EXTERNAL_PKG),),
            outside_packages=(UmlPackage(package_id=EXTERNAL_PKG, name="external"),),
        ),
        _outside,
        cites="R-29",
    ),
    Row(
        "a link to a class in an excluded package makes no slot and a report line",
        UmlRule.LEFT_OUT_LINK,
        _EXCLUDED_MODEL,
        _excluded,
        {"exclude_packages": ["catalogue"]},
    ),
    Row(
        "a slot to a not-generated class is a URI range with the class's one line, and no link line",
        UmlRule.LEFT_OUT_LINK,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series", stereotype="loaded graph"),
            links=(link(1, BOOK, SERIES, target_role="series"),),
        ),
        _not_generated_link,
    ),
    Row(
        "the same class in a package no exclusion covers is outside, not excluded",
        UmlRule.LEFT_OUT_LINK,
        _EXCLUDED_MODEL,
        _outside,
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
        cites="R-13",
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
]


# --- R-13 again: a shared slot holds only what every usage agrees on (D-22 C-1) ------------------------

_LIMITS = (
    "range",
    "required",
    "multivalued",
    "description",
    "minimum_cardinality",
    "maximum_cardinality",
    "minimum_value",
    "inlined",
    "inlined_as_list",
)
_ATTRIBUTE_NOTE = "An attribute."
_LINK_NOTE = "A connector."


def _limits(definition: object) -> dict[str, object]:
    """The limits a slot or slot_usage states: the keywords that are set; a false ``required`` or
    ``multivalued`` counts, since a usage writes it to override the parent's true (D-5)."""
    found = {name: getattr(definition, name) for name in _LIMITS}
    return {
        name: value
        for name, value in found.items()
        if value is not None and (value is not False or name in ("required", "multivalued"))
    }


def _agreed_and_narrowed(
    slot: str, agreed: dict[str, object], book: dict[str, object], series: dict[str, object]
) -> Check:
    """The slot states ``agreed``; Book and Series each state their own ``slot_usage`` limits, or none."""

    def check(out: Converted) -> None:
        _no_problems(out)
        assert _limits(out.slot("app_library", slot)) == agreed, (
            f"the slot {slot} must state only what both usages agree on"
        )
        for holder, expected in (("Book", book), ("Series", series)):
            usages = out.klass("app_library", holder).slot_usage
            found = _limits(usages[slot]) if slot in usages else None
            assert found == (expected or None), (
                f"{holder}.{slot} must carry its own limits in slot_usage, and none when it has none"
            )
        every = [
            out.klass("app_library", holder).slot_usage[name]
            for holder in sorted(out.schemas["app_library"].classes)
            for name in out.klass("app_library", holder).slots
            if name in out.klass("app_library", holder).slot_usage
        ]
        for usage in every:
            assert _limits(usage) or usage.annotations, (
                f"the slot_usage of {usage.name} is empty and must not be written"
            )

    return check


def _isbn_pair(book: dict[str, object], series: dict[str, object]) -> object:
    return model(
        klass(BOOK, "lib:Book", attributes=(attribute(1, BOOK, "lib:isbn", **book),)),
        klass(SERIES, "lib:Series", attributes=(attribute(2, SERIES, "lib:isbn", **series),)),
    )


def _owned_on_one_class() -> object:
    """Book owns its parts through a boundary; Series refers to the same slot name as a plain reference."""
    return model(
        klass(BOOK, "lib:Book", stereotype="root"),
        klass(CHAPTER, "lib:Chapter"),
        klass(SERIES, "lib:Series"),
        links=(
            link(1, BOOK, CHAPTER, target_role="lib:hasPart", target_card="0..*"),
            link(2, SERIES, CHAPTER, target_role="lib:hasPart", target_card="0..*"),
        ),
        boundaries=(boundary(20, BOOK, CHAPTER),),
    )


def _owned_on_book_only(out: Converted) -> None:
    _agreed_and_narrowed(
        "has_part",
        {"range": "Chapter", "multivalued": True, "description": _LINK_NOTE},
        {"inlined_as_list": True},
        {},
    )(out)
    assert "owned" not in out.slot("app_library", "has_part").annotations, (
        "the owned annotation must not leak from Book to the shared slot"
    )
    book_usage = out.klass("app_library", "Book").slot_usage["has_part"]
    assert book_usage.annotations["owned"].value == "true", "Book's own usage carries owned"


_TEXT = {"range": "string", "description": _ATTRIBUTE_NOTE}

ROWS_R13 = [
    Row(
        "a limit one usage has and the other has not stays on that usage (maximum_cardinality)",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"lower": "0", "upper": "5"}, {"lower": "0", "upper": None}),
        _agreed_and_narrowed(
            "isbn", {**_TEXT, "multivalued": True}, {"maximum_cardinality": 5}, {}
        ),
    ),
    Row(
        "a minimum_value on the defining usage does not leak to the other",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"declared_type": "xsd:nonNegativeInteger"}, {"declared_type": "xsd:integer"}),
        _agreed_and_narrowed(
            "isbn",
            {"range": "integer", "required": True, "description": _ATTRIBUTE_NOTE},
            {"minimum_value": 0},
            {},
        ),
    ),
    Row(
        "a minimum_value on the second usage is its own",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"declared_type": "xsd:integer"}, {"declared_type": "xsd:nonNegativeInteger"}),
        _agreed_and_narrowed(
            "isbn",
            {"range": "integer", "required": True, "description": _ATTRIBUTE_NOTE},
            {},
            {"minimum_value": 0},
        ),
    ),
    Row(
        "ownership on one class does not leak inlined to the other",
        UmlRule.SHARED_SLOT,
        _owned_on_one_class(),
        _owned_on_book_only,
    ),
    Row(
        "a description on the first usage only is the slot's, and the other usage inherits it",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"note": "The isbn."}, {"note": None}),
        _agreed_and_narrowed(
            "isbn", {"range": "string", "required": True, "description": "The isbn."}, {}, {}
        ),
    ),
    Row(
        "the slot takes the first non-empty description, in class order",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"note": None}, {"note": "The isbn."}),
        _agreed_and_narrowed(
            "isbn", {"range": "string", "required": True, "description": "The isbn."}, {}, {}
        ),
    ),
    Row(
        "a usage whose description differs carries its own, the first one is the slot's",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"note": "The isbn."}, {"note": "The code."}),
        _agreed_and_narrowed(
            "isbn",
            {"range": "string", "required": True, "description": "The isbn."},
            {},
            {"description": "The code."},
        ),
    ),
    Row(
        "a required on one usage only stays on it",
        UmlRule.SHARED_SLOT,
        _isbn_pair({}, {"lower": "0"}),
        _agreed_and_narrowed("isbn", _TEXT, {"required": True}, {"required": False}),
    ),
    Row(
        "the slot takes the first usage's range, a usage with another range carries its own",
        UmlRule.SHARED_SLOT,
        _isbn_pair({"declared_type": "xsd:string"}, {"declared_type": "xsd:integer"}),
        _agreed_and_narrowed(
            "isbn",
            {"range": "string", "required": True, "description": _ATTRIBUTE_NOTE},
            {},
            {"range": "integer"},
        ),
    ),
    Row(
        "two identical usages write the full slot and no slot_usage",
        UmlRule.SHARED_SLOT,
        _isbn_pair({}, {}),
        _agreed_and_narrowed("isbn", {**_TEXT, "required": True}, {}, {}),
    ),
]

_ABSTRACT_PARENT, _CHILD, _VALUE, _NARROWER_VALUE = 51, 52, 53, 54


def _narrowed_role(parent_card: str, child_card: str, *, root: bool = False) -> object:
    """``A.p`` to ``V`` and ``B.p`` to ``W is_a V``, B being A's child, the two roles' cardinalities given."""
    return model(
        klass(_ABSTRACT_PARENT, "lib:Base", abstract=True),
        klass(_CHILD, "lib:Derived", stereotype="root" if root else None),
        klass(_VALUE, "lib:Value"),
        klass(_NARROWER_VALUE, "lib:Narrower"),
        links=(
            generalisation(1, _CHILD, _ABSTRACT_PARENT),
            generalisation(2, _NARROWER_VALUE, _VALUE),
            link(3, _ABSTRACT_PARENT, _VALUE, target_role="lib:part", target_card=parent_card),
            link(4, _CHILD, _NARROWER_VALUE, target_role="lib:part", target_card=child_card),
        ),
        tags=(tag(_CHILD, "unique_key", "k: part"),) if root else (),
    )


def _usage_is(expected: dict[str, object], *, single_valued: bool = False) -> Check:
    """Derived's ``slot_usage`` for ``part`` states exactly ``expected``, explicit flags included."""

    def check(out: Converted) -> None:
        _no_problems(out)
        usage = out.klass("app_library", "Derived").slot_usage["part"]
        found = {name: getattr(usage, name) for name in _LIMITS if getattr(usage, name) is not None}
        assert found == expected, f"Derived.part must state {expected}, and it states {found}"
        if single_valued:
            view = SchemaView(yaml_dumper.dumps(out.schemas["app_library"]))
            assert not view.induced_slot("part", "Derived").multivalued, (
                "the induced slot of Derived.part must be single-valued"
            )

    return check


ROWS_NARROWED = [
    Row(
        "a root narrowing an inherited 0..* role to 1 writes multivalued: false and the key is accepted",
        UmlRule.SHARED_SLOT,
        _narrowed_role("0..*", "1", root=True),
        _usage_is(
            {"range": "Narrower", "required": True, "multivalued": False}, single_valued=True
        ),
    ),
    Row(
        "a 0..1 role under a 1..1 role writes required: false",
        UmlRule.SHARED_SLOT,
        _narrowed_role("1..1", "0..1"),
        _usage_is({"range": "Narrower", "required": False}),
    ),
    Row(
        "agreeing usages write no limit in the slot_usage",
        UmlRule.SHARED_SLOT,
        _narrowed_role("0..1", "0..1"),
        _usage_is({"range": "Narrower"}),
    ),
]

# --- W-3: elements no rule maps are problems, not silence (D-22) ----------------------------------------

_NOVEL = ("lib:novel",)

ROWS_W3 = [
    Row(
        "failure: a directed association held by an enumeration",
        UmlRule.NO_RULE,
        model(
            enumeration(GENRE, "lib:Genre", _NOVEL),
            klass(BOOK, "lib:Book"),
            links=(link(1, GENRE, BOOK, target_role="lib:books", target_card="0..*"),),
        ),
        _problem(UmlRule.NO_RULE, "Genre.books", "enumeration", "no rule converts it"),
    ),
    Row(
        "failure: the source role of an association points back at an enumeration",
        UmlRule.NO_RULE,
        model(
            enumeration(GENRE, "lib:Genre", _NOVEL),
            klass(BOOK, "lib:Book"),
            links=(link(1, BOOK, GENRE, target_role="genre", source_role="lib:books"),),
        ),
        _problem(UmlRule.NO_RULE, "Genre.books", "enumeration"),
    ),
    Row(
        "failure: a dependency held by an enumeration",
        UmlRule.NO_RULE,
        model(
            enumeration(GENRE, "lib:Genre", _NOVEL),
            enumeration(SERIES, "lib:Format", ("lib:paper",)),
            links=(link(1, GENRE, SERIES, kind=UmlLinkKind.DEPENDENCY, target_role="format"),),
        ),
        _problem(UmlRule.NO_RULE, "Genre.format", "enumeration"),
    ),
    Row(
        "failure: a dependency with a source role only needs a destination role",
        UmlRule.NO_RULE,
        model(
            enumeration(GENRE, "lib:Genre", _NOVEL),
            klass(BOOK, "lib:Book"),
            links=(link(1, BOOK, GENRE, kind=UmlLinkKind.DEPENDENCY, source_role="lib:genre"),),
        ),
        _problem(UmlRule.NO_RULE, "Book.genre", "destination role", "no rule converts it"),
    ),
    Row(
        "failure: a generalisation from an enumeration",
        UmlRule.NO_RULE,
        model(
            enumeration(GENRE, "lib:Genre", _NOVEL),
            klass(BOOK, "lib:Book"),
            links=(generalisation(1, GENRE, BOOK),),
        ),
        _problem(UmlRule.NO_RULE, "Genre", "generalisation from an enumeration"),
    ),
    Row(
        "failure: a generalisation from an empty enumeration is a problem, not a crash",
        UmlRule.NO_RULE,
        model(
            enumeration(GENRE, "lib:Genre", ()),
            klass(BOOK, "lib:Book"),
            links=(generalisation(1, GENRE, BOOK),),
        ),
        _problem(UmlRule.NO_RULE, "Genre", "generalisation from an enumeration"),
    ),
]


def _both_roles(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas["app_library"].slots) == ["has_chapter", "in_book"], (
        "each role of the association is a slot"
    )


def _directed_pair(direction: str, source_role: str | None = "lib:inBook") -> object:
    return model(
        klass(BOOK, "lib:Book"),
        klass(CHAPTER, "lib:Chapter"),
        links=(
            link(
                1,
                BOOK,
                CHAPTER,
                target_role="lib:hasChapter",
                target_card="0..*",
                source_role=source_role,
                source_card="1..1",
                direction=direction,
            ),
        ),
    )


_RARE_BOOKS = 5


def _from_library(**overrides: object) -> Converted:
    """The model as the reader gives it: the subtree root first, its ancestor ``MODEL`` not listed."""
    uml = model(
        klass(BOOK, "lib:Book", stereotype="root"),
        klass(CHAPTER, "lib:Chapter", _RARE_BOOKS),
        packages=(
            UmlPackage(package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG),
            UmlPackage(package_id=_RARE_BOOKS, name="rare-books", parent_id=LIBRARY_PKG),
        ),
    )
    return run(uml, **overrides)


def test_the_path_form_and_the_name_form_of_the_package_give_the_same_modules() -> None:
    by_name = _from_library(subtree_package="library")
    by_path = _from_library(subtree_package="MODEL/library")

    assert by_name.problems == by_path.problems == [], "both forms convert without a problem"
    assert sorted(by_path.schemas) == ["app", "app_main", "app_rare_books"], (
        "the path form gives the modules of the subtree, not none"
    )
    for name, schema in by_name.schemas.items():
        assert yaml_dumper.dumps(by_path.schemas[name]) == yaml_dumper.dumps(schema), (
            f"the module {name} is the same by name and by path"
        )


def test_a_subtree_with_no_class_or_enumeration_is_a_problem() -> None:
    out = run(model(), subtree_package="model")

    assert out.schemas == {}, "nothing is written for an empty subtree"
    assert out.problem_texts() == [
        "[package_module] model: the package holds no class or enumeration to convert"
    ], "an empty subtree is a problem, never a silent success"


def _no_direction() -> object:
    """The reader gives ``direction`` None when the connector row has none; the helper fills one in."""
    uml = _directed_pair(DIRECTED, None)
    uml.uml_links[0].direction = None
    return uml


ROWS_D14 = [
    Row(
        "a bi-directional association gives a slot at each end (D-14)",
        UmlRule.NO_RULE,
        _directed_pair(BIDIRECTIONAL),
        _both_roles,
    ),
    Row(
        "failure: a direction of Unspecified names the connector and the direction",
        UmlRule.NO_RULE,
        _directed_pair("Unspecified", None),
        _problem(
            UmlRule.NO_RULE, "Book.has_chapter", "direction Unspecified", "no rule converts it"
        ),
    ),
    Row(
        "failure: a direction of Destination -> Source",
        UmlRule.NO_RULE,
        _directed_pair("Destination -> Source", None),
        _problem(UmlRule.NO_RULE, "Book.has_chapter", "direction Destination -> Source"),
    ),
    Row(
        "failure: no direction at all",
        UmlRule.NO_RULE,
        _no_direction(),
        _problem(UmlRule.NO_RULE, "Book.has_chapter", "no direction"),
    ),
    Row(
        "failure: a source role on a Source -> Destination association asks for Bi-Directional",
        UmlRule.NO_RULE,
        _directed_pair(DIRECTED),
        _problem(UmlRule.NO_RULE, "Book.has_chapter", "Source -> Destination", "Bi-Directional"),
    ),
]

# --- R-25..R-28 toolkit mixins (PD-17, PD-29), DEC-4 (D-7) -------------------------------------------

_RP_CORE = "rdf_persistence/model/rp_core"
_RP_ANNOTATIONS = "rdf_persistence/model/rp_annotations"
_RP_PROVENANCE = "rdf_persistence/model/rp_provenance"
_RP_WORKFLOW = "rdf_persistence/model/rp_workflow"
_RP_COLLECTIONS = "rdf_persistence/model/rp_collections"
_DEFAULTS = {"default_mixins": ["Described", "Tracked"]}
_ACTIVITY, _COLLECTION = 15, 16
_EXTERNAL = (UmlPackage(package_id=EXTERNAL_PKG, name="external"),)


def _drawn(*classes: tuple[int, str]) -> dict[str, object]:
    """The model keywords that put drawn classes outside the subtree, as the reader reports them."""
    return {
        "outside": tuple(klass(each, name, EXTERNAL_PKG) for each, name in classes),
        "outside_packages": _EXTERNAL,
    }


def _book(*tags: tuple[str, str], **drawn: object) -> object:
    """A root Book with tagged values; ``links`` and drawn classes go in through ``drawn``."""
    return model(
        klass(BOOK, "lib:Book", stereotype="root"),
        tags=tuple(tag(BOOK, name, value) for name, value in tags),
        **drawn,
    )


def _mixed(
    expected: list[str],
    *,
    is_a: str | None = None,
    imports: tuple[str, ...] = (),
    name: str = "Book",
) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        definition = out.klass("app_library", name)
        assert list(definition.mixins) == expected, f"mixins of {name}"
        assert definition.is_a == is_a, f"is_a of {name}"
        for module in imports:
            assert module in out.schemas["app_library"].imports, f"{module} is imported"

    return check


def _imports_sorted(out: Converted) -> None:
    toolkit = [i for i in out.schemas["app_library"].imports if i.startswith("rdf_persistence/")]
    assert toolkit == sorted(toolkit), "the toolkit imports are sorted"
    assert len(toolkit) == len(set(toolkit)), "each toolkit module is imported once"


def _drawn_not_generated(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas["app_library"].classes) == ["Book"], (
        "the drawn class is not generated"
    )
    assert out.report_lines("outside_link") == [], "a drawn toolkit parent is not an outside link"


_NOT_TOOLKIT = "Nope"
_ONE_SOURCE = "no rule converts it"

ROWS_R25 = [
    Row(
        "a root has the default mixins after the aggregate-root mixin",
        UmlRule.TOOLKIT_MIXINS,
        _book(),
        _mixed(["AggregateRoot", "Described", "Tracked"], imports=(_RP_CORE, _RP_ANNOTATIONS)),
        _DEFAULTS,
        cites="R-25",
    ),
    Row(
        "the default mixins are the ones the command line gives",
        UmlRule.TOOLKIT_MIXINS,
        _book(),
        _mixed(["AggregateRoot", "Tracked"]),
        {"default_mixins": ["Tracked"]},
    ),
    Row(
        "an owned part has the default mixins and no aggregate-root mixin",
        UmlRule.TOOLKIT_MIXINS,
        _book_chapter("1..*", boundaries=(boundary(20, BOOK, CHAPTER),)),
        _mixed(["Described", "Tracked"], name="Chapter"),
        _DEFAULTS,
    ),
    Row(
        "a part tagged rp_unlabelled has Described only (PD-29)",
        UmlRule.TOOLKIT_MIXINS,
        _book_chapter(
            "1..*",
            boundaries=(boundary(20, BOOK, CHAPTER),),
            tags=(tag(CHAPTER, "rp_unlabelled", "true"),),
        ),
        _mixed(["Described"], name="Chapter"),
        _DEFAULTS,
    ),
    Row(
        "a class that is neither a root nor owned has no default mixin",
        UmlRule.TOOLKIT_MIXINS,
        model(klass(BOOK, "lib:Book")),
        _mixed([]),
        _DEFAULTS,
    ),
    Row(
        "failure: a default mixin that is not a toolkit class lists the toolkit classes",
        UmlRule.TOOLKIT_MIXINS,
        _book(),
        _problem(UmlRule.TOOLKIT_MIXINS, "--default-mixins", _NOT_TOOLKIT, "Described", "Tracked"),
        {"default_mixins": ["Described", _NOT_TOOLKIT]},
    ),
]

ROWS_R26 = [
    Row(
        "an rp_mixins name is a mixin, after the aggregate-root one and before the defaults",
        UmlRule.TOOLKIT_MIXINS,
        _book(("rp_mixins", "Provenanced")),
        _mixed(
            ["AggregateRoot", "Provenanced", "Described", "Tracked"],
            imports=(_RP_PROVENANCE, _RP_CORE, _RP_ANNOTATIONS),
        ),
        _DEFAULTS,
        cites="R-26",
    ),
    Row(
        "rp_mixins names keep the tag order, spaces ignored, and no mixin is repeated",
        UmlRule.TOOLKIT_MIXINS,
        _book(("rp_mixins", "Tracked, Described")),
        _mixed(["AggregateRoot", "Tracked", "Described"]),
        _DEFAULTS,
    ),
    Row(
        "a toolkit module is imported once, with the other toolkit imports sorted",
        UmlRule.TOOLKIT_MIXINS,
        _book(("rp_mixins", "Provenanced,Described")),
        _all(
            _mixed(
                ["AggregateRoot", "Provenanced", "Described", "Tracked"],
                imports=(_RP_PROVENANCE,),
            ),
            _imports_sorted,
        ),
        _DEFAULTS,
    ),
    Row(
        "a non-mixin in rp_mixins is the is_a (Activity)",
        UmlRule.TOOLKIT_MIXINS,
        _book(("rp_mixins", "Activity")),
        _mixed(
            ["AggregateRoot", "Described", "Tracked"], is_a="Activity", imports=(_RP_PROVENANCE,)
        ),
        _DEFAULTS,
    ),
    Row(
        "failure: an rp_mixins name that is not a toolkit class lists the toolkit classes",
        UmlRule.TOOLKIT_MIXINS,
        _book(("rp_mixins", _NOT_TOOLKIT)),
        _problem(UmlRule.TOOLKIT_MIXINS, "Book", _NOT_TOOLKIT, "Described", "Activity"),
    ),
    Row(
        "failure: two non-mixin toolkit classes are two is_a sources",
        UmlRule.NO_RULE,
        _book(("rp_mixins", "Activity,Principal")),
        _problem(UmlRule.NO_RULE, "Book", "Activity", "Principal", _ONE_SOURCE),
    ),
]

ROWS_R27 = [
    Row(
        "a workflow tag adds the workflow mixin after the defaults",
        UmlRule.TOOLKIT_MIXINS,
        _book(("workflow", "review")),
        _mixed(["AggregateRoot", "Described", "Tracked", "UnderWorkflow"], imports=(_RP_WORKFLOW,)),
        _DEFAULTS,
        cites="R-27",
    ),
]

ROWS_R28 = [
    Row(
        "a drawn mixin parent is a mixin and is not generated",
        UmlRule.TOOLKIT_MIXINS,
        _book(
            links=(generalisation(1, BOOK, _COLLECTION),),
            **_drawn((_COLLECTION, "rp:ReferenceCollection")),
        ),
        _all(
            _drawn_not_generated,
            _mixed(
                ["AggregateRoot", "ReferenceCollection", "Described", "Tracked"],
                imports=(_RP_COLLECTIONS,),
            ),
        ),
        _DEFAULTS,
        cites="R-28",
    ),
    Row(
        "a drawn parent comes after the rp_mixins names",
        UmlRule.TOOLKIT_MIXINS,
        _book(
            ("rp_mixins", "Provenanced"),
            links=(generalisation(1, BOOK, _COLLECTION),),
            **_drawn((_COLLECTION, "rp:ReferenceCollection")),
        ),
        _mixed(["AggregateRoot", "Provenanced", "ReferenceCollection"]),
    ),
    Row(
        "a drawn mixin parent beside a domain parent: the domain parent is the is_a",
        UmlRule.TOOLKIT_MIXINS,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series"),
            links=(generalisation(1, BOOK, SERIES), generalisation(2, BOOK, _COLLECTION)),
            **_drawn((_COLLECTION, "rp:ReferenceCollection")),
        ),
        _mixed(["ReferenceCollection"], is_a="Series"),
    ),
    Row(
        "failure: a domain parent and a drawn Activity are two is_a sources",
        UmlRule.NO_RULE,
        model(
            klass(BOOK, "lib:Book"),
            klass(SERIES, "lib:Series"),
            links=(generalisation(1, BOOK, SERIES), generalisation(2, BOOK, _ACTIVITY)),
            **_drawn((_ACTIVITY, "prov:Activity")),
        ),
        _problem(UmlRule.NO_RULE, "Book", "Series", "Activity", _ONE_SOURCE),
    ),
    Row(
        "failure: a drawn class that is not a toolkit class stays a class that is not converted",
        UmlRule.NO_RULE,
        model(
            klass(BOOK, "lib:Book"),
            links=(generalisation(1, BOOK, _ACTIVITY),),
            **_drawn((_ACTIVITY, "prov:Entity")),
        ),
        _problem(UmlRule.NO_RULE, "Book", "not converted", _ONE_SOURCE),
    ),
]

# SPIKE-1 passed (D-7): an application root may be an Activity, so the activity_root refusal is inactive.
ROWS_ACTIVITY_ROOT = [
    Row(
        "inactive since SPIKE-1 passed: a root drawn as a prov:Activity is accepted, is_a Activity",
        UmlRule.ACTIVITY_ROOT,
        _book(links=(generalisation(1, BOOK, _ACTIVITY),), **_drawn((_ACTIVITY, "prov:Activity"))),
        _all(
            _drawn_not_generated,
            _mixed(
                ["AggregateRoot", "Described", "Tracked"],
                is_a="Activity",
                imports=(_RP_PROVENANCE,),
            ),
        ),
        _DEFAULTS,
    ),
    Row(
        "inactive since SPIKE-1 passed: a root tagged rp_mixins=Activity is accepted",
        UmlRule.ACTIVITY_ROOT,
        _book(("rp_mixins", "Activity")),
        _mixed(["AggregateRoot"], is_a="Activity"),
    ),
]

# --- R-15, R-22 toolkit slots (PD-18, PD-26, F-3) -----------------------------------------------------

_SKOS = "http://www.w3.org/2004/02/skos/core#"
_WITH_SKOS = {
    "prefixes": [
        UmlPrefix(prefix_name=name, namespace=namespace)
        for name, namespace in {**PREFIXES, "skos": _SKOS}.items()
    ]
}
_DESCRIBED = {**_WITH_SKOS, **_DEFAULTS}
_TOOLKIT_SLOTS = ("label", "started_at_time", "generated_at_time", "identifier")


def _with(
    *attributes: UmlAttribute, tags: tuple[tuple[str, str], ...] = (), root: bool = True
) -> object:
    """A Book (a root unless told otherwise) with these attributes and tagged values."""
    return model(
        klass(BOOK, "lib:Book", stereotype="root" if root else None, attributes=attributes),
        tags=tuple(tag(BOOK, name, value) for name, value in tags),
    )


def _pref_label(declared: str = "xsd:string", **bounds: str | None) -> UmlAttribute:
    return attribute(1, BOOK, "skos:prefLabel", declared, **bounds)


def _book_uses(
    slots: list[str], usage: dict[str, object] | None = None, imports: tuple[str, ...] = ()
) -> Check:
    """No new slot; the Book lists these slots and carries this ``slot_usage``."""

    def check(out: Converted) -> None:
        _no_problems(out)
        module = out.schemas["app_library"]
        assert not module.slots, "a toolkit slot is not defined again"
        book = out.klass("app_library", "Book")
        assert list(book.slots) == slots, "the slots the Book lists"
        carried = {
            name: _limits(book.slot_usage[name])
            for name in _TOOLKIT_SLOTS
            if name in book.slot_usage
        }
        assert carried == (usage or {}), "the limits the slot_usage of a toolkit slot carries"
        assert bool(book.slot_usage) == bool(usage), "no slot_usage of another slot"
        for imported in imports:
            assert imported in module.imports, f"{imported} is imported"

    return check


def _line(kind: str, *lines: str) -> Check:
    def check(out: Converted) -> None:
        assert out.report_lines(kind) == list(lines), f"the {kind} lines of the report"

    return check


def _identifier_slot(out: Converted) -> None:
    _no_problems(out)
    slot = out.slot("app_library", "identifier")
    assert slot.slot_uri == "dcterms:identifier", "the identifier has the Dublin Core IRI"
    assert slot.range == "string", "the identifier is a string"
    assert slot.required is True, "the identifier is required"
    assert list(out.klass("app_library", "Book").slots) == ["identifier"], "the Book lists it"
    assert "id" not in out.schemas["app_library"].slots, "id stays the IRI and is not redefined"


_KEPT = "the toolkit's label is kept; {} is not carried"

ROWS_R22 = [
    Row(
        "an attribute dct:identifier is a new slot identifier, never the toolkit's id",
        UmlRule.TOOLKIT_SLOT,
        _with(attribute(1, BOOK, "dct:identifier")),
        _all(_identifier_slot, _line("toolkit_slot_kept")),
        cites="R-22",
    ),
]

ROWS_R15 = [
    Row(
        "a toolkit-filled slot gets no slot, no slot_usage and a toolkit-filled line",
        UmlRule.TOOLKIT_SLOT,
        _with(
            attribute(1, BOOK, "prov:startedAtTime", "xsd:dateTime"),
            tags=(("rp_mixins", "Activity"),),
        ),
        _all(
            _book_uses([], imports=(_RP_PROVENANCE,)),
            _line(
                "toolkit_filled",
                "Book.started_at_time: the toolkit fills started_at_time; [1..1] is not carried",
            ),
        ),
        cites="R-15",
    ),
    Row(
        "a toolkit slot the class inherits, with an optional bound, adds nothing",
        UmlRule.TOOLKIT_SLOT,
        _with(_pref_label(lower="0")),
        _all(_book_uses([]), _line("toolkit_slot_kept"), _line("toolkit_filled")),
        _DESCRIBED,
    ),
    Row(
        "a required bound the inherited slot already has (Described requires label) adds nothing",
        UmlRule.TOOLKIT_SLOT,
        _with(_pref_label()),
        _book_uses([]),
        _DESCRIBED,
    ),
    Row(
        "a class that does not inherit the slot lists it; its required is a slot_usage, the module is imported",
        UmlRule.TOOLKIT_SLOT,
        _with(_pref_label(), root=False),
        _book_uses(["label"], {"label": {"required": True}}, (_RP_ANNOTATIONS,)),
        _WITH_SKOS,
    ),
    Row(
        "a slot of a module no toolkit class of the class brings is imported",
        UmlRule.TOOLKIT_SLOT,
        _with(attribute(1, BOOK, "prov:generatedAtTime", "xsd:dateTime", lower="0"), root=False),
        _book_uses(["generated_at_time"], imports=(_RP_PROVENANCE,)),
    ),
    Row(
        "a multivalued difference keeps the toolkit's slot and says so",
        UmlRule.TOOLKIT_SLOT,
        _with(_pref_label(lower="0", upper="*")),
        _all(
            _book_uses([]),
            _line("toolkit_slot_kept", "Book.label: " + _KEPT.format("multivalued true")),
        ),
        _DESCRIBED,
    ),
    Row(
        "a range difference keeps the toolkit's slot and says so",
        UmlRule.TOOLKIT_SLOT,
        _with(_pref_label("xsd:integer", lower="0")),
        _all(
            _book_uses([]),
            _line("toolkit_slot_kept", "Book.label: " + _KEPT.format("range integer")),
        ),
        _DESCRIBED,
    ),
]

# --- R-30 an enumeration that is not generated (PD-15, D-23) --------------------------------------------

_STATES = "workflow states"
_LISTED = {"not_generated_stereotypes": ["loaded graph", _STATES]}


def _states_enum() -> object:
    states = enumeration(GENRE, "lib:Genre", ("lib:open", "lib:closed"))
    states.uml_stereotype = _STATES
    return states


def _enum_left_out(out: Converted) -> None:
    _no_problems(out)
    assert "Genre" not in out.schemas["app_library"].enums, "a listed enumeration makes no enum"
    assert "Genre: stereotype workflow states, not generated" in out.report_lines(
        "not_generated"
    ), "the enumeration has its not-generated line"


def _no_slot_for_states(out: Converted) -> None:
    _enum_left_out(out)
    assert "genre" not in out.schemas["app_library"].slots, "no slot for the listed enumeration"
    assert out.klass("app_library", "Book").slots == [], "the Book lists no slot"
    assert [line.split(":")[0] for line in out.report_lines("not_generated")] == [
        "Book.genre -> Genre",
        "Genre",
    ], "the dependency and the enumeration have one line each"


def _no_slot_for_typed_attribute(out: Converted) -> None:
    _enum_left_out(out)
    assert "status" not in out.schemas["app_library"].slots, "no slot for the typed attribute"
    assert out.klass("app_library", "Book").slots == [], "the Book lists no slot"
    assert [line.split(":")[0] for line in out.report_lines("not_generated")] == [
        "Book.status",
        "Genre",
    ], "the attribute and the enumeration have one line each"


def _class_dependency_stays_a_uri(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "series").range == "uri", "the dependency is a URI slot"
    assert out.report_lines("not_generated") == [
        "Series: stereotype loaded graph, not generated"
    ], "the class has its one line and the dependency adds none"


ROWS_R30 = [
    Row(
        "a dependency to a not-generated class is as before: a URI slot, no extra line",
        UmlRule.NOT_GENERATED,
        model(
            klass(SERIES, "lib:Series", stereotype="loaded graph"),
            klass(BOOK, "lib:Book"),
            links=(
                link(
                    1,
                    BOOK,
                    SERIES,
                    kind=UmlLinkKind.DEPENDENCY,
                    target_role="series",
                    target_card="0..1",
                ),
            ),
        ),
        _class_dependency_stays_a_uri,
    ),
    Row(
        "an attribute typed by a not-generated class is still no rule",
        UmlRule.NOT_GENERATED,
        model(
            klass(SERIES, "lib:Series", stereotype="loaded graph"),
            klass(
                BOOK,
                "lib:Book",
                attributes=(attribute(1, BOOK, "lib:series", "Series", classifier=SERIES),),
            ),
        ),
        _problem(UmlRule.NO_RULE, "Book.series", "type Series"),
    ),
    Row(
        "a listed enumeration makes no enum and one not-generated line",
        UmlRule.NOT_GENERATED,
        model(_states_enum(), klass(BOOK, "lib:Book")),
        _enum_left_out,
        _LISTED,
    ),
    Row(
        "a dependency to a listed enumeration makes no slot and one not-generated line",
        UmlRule.NOT_GENERATED,
        model(
            _states_enum(),
            klass(BOOK, "lib:Book"),
            links=(
                link(
                    1,
                    BOOK,
                    GENRE,
                    kind=UmlLinkKind.DEPENDENCY,
                    target_role="genre",
                    target_card="0..1",
                ),
            ),
        ),
        _no_slot_for_states,
        _LISTED,
    ),
    Row(
        "an attribute typed by a listed enumeration makes no slot and one not-generated line",
        UmlRule.NOT_GENERATED,
        model(
            _states_enum(),
            klass(
                BOOK,
                "lib:Book",
                attributes=(attribute(1, BOOK, "lib:status", "Genre", classifier=GENRE),),
            ),
        ),
        _no_slot_for_typed_attribute,
        _LISTED,
    ),
]

# --- R-18 tenant root (PD-19, PD-13) ---------------------------------------------------------------------


def _tenant(out: Converted) -> None:
    _no_problems(out)
    book = out.klass("app_library", "Book")
    assert book.annotations["graph"].value == "meta", "a tenant root lives in the meta graph"
    assert "rp_path" not in book.annotations, "a tenant root has no path"
    assert "AggregateRoot" not in book.mixins, "a tenant root is not an aggregate root"
    assert list(book.mixins) == ["Described", "Tracked"], "it has the default mixins as a root has"


def _tenant_with_part(out: Converted) -> None:
    _no_problems(out)
    assert out.slot("app_library", "has_chapter").annotations["owned"].value == "true", (
        "the part of a tenant root's boundary is owned"
    )
    assert list(out.klass("app_library", "Chapter").mixins) == ["Described", "Tracked"], (
        "the part has the default mixins"
    )


ROWS_R18 = [
    Row(
        "a tenant root is graph meta, with no aggregate-root mixin and no path",
        UmlRule.TENANT_ROOT,
        model(klass(BOOK, "lib:Book", stereotype="tenant root")),
        _tenant,
        _DEFAULTS,
        cites="R-18",
    ),
    Row(
        "a graph tag of meta on a tenant root is the same annotation",
        UmlRule.TENANT_ROOT,
        model(
            klass(BOOK, "lib:Book", stereotype="Tenant Root"), tags=(tag(BOOK, "graph", "meta"),)
        ),
        _tenant,
        _DEFAULTS,
    ),
    Row(
        "a boundary holding a tenant root has its one root, and owns the parts",
        UmlRule.TENANT_ROOT,
        model(
            klass(BOOK, "lib:Book", stereotype="tenant root"),
            klass(CHAPTER, "lib:Chapter"),
            links=(link(1, BOOK, CHAPTER, target_role="lib:hasChapter", target_card="0..*"),),
            boundaries=(boundary(20, BOOK, CHAPTER),),
        ),
        _tenant_with_part,
        _DEFAULTS,
    ),
    Row(
        "failure: a graph tag of another value on a tenant root",
        UmlRule.TENANT_ROOT,
        model(
            klass(BOOK, "lib:Book", stereotype="tenant root"), tags=(tag(BOOK, "graph", "data"),)
        ),
        _problem(UmlRule.TENANT_ROOT, "Book", "graph", "data", "meta"),
    ),
]

# --- R-23 abstract roots (PD-19, PD-21) -----------------------------------------------------------------

WORK = SERIES  # the abstract class the roots specialise
MID = 17


def _work_model(
    *,
    book: str | None = "root",
    ranged: bool = True,
    work_attributes: tuple[UmlAttribute, ...] = (),
    tags: tuple[object, ...] = (),
) -> object:
    """An abstract Work, specialised by a Book; a root Shelf points at the Work when ``ranged``."""
    return model(
        klass(WORK, "lib:Work", abstract=True, attributes=work_attributes),
        klass(BOOK, "lib:Book", stereotype=book),
        klass(SHELF, "lib:Shelf", stereotype="root"),
        links=(
            generalisation(1, BOOK, WORK),
            *(
                (link(2, SHELF, WORK, target_role="lib:holds", target_card="0..*"),)
                if ranged
                else ()
            ),
        ),
        tags=tags,
    )


def _work_is_root(out: Converted) -> None:
    _no_problems(out)
    work = out.klass("app_library", "Work")
    assert list(work.mixins) == ["AggregateRoot"], (
        "the abstract root has the aggregate-root mixin only"
    )
    assert "rp_path" not in (work.annotations or {}), "an abstract root has no path"
    book = out.klass("app_library", "Book")
    assert book.is_a == "Work", "the root keeps its parent"
    assert list(book.mixins) == ["AggregateRoot", "Described", "Tracked"], (
        "a root subclass still lists the aggregate-root mixin"
    )
    assert "rdf_persistence/model/rp_core" in out.schemas["app_library"].imports, "rp_core imported"


def _work_is_plain(out: Converted) -> None:
    _no_problems(out)
    assert list(out.klass("app_library", "Work").mixins) == [], "the abstract class stays plain"


def _work_key(out: Converted) -> None:
    _no_problems(out)
    key = out.klass("app_library", "Work").unique_keys["k"]
    assert key.annotations["rp_unique_scope"].value == "tenant", (
        "a key of an abstract root is tenant-wide"
    )


def _assert_mixins(out: Converted, name: str, expected: list[str]) -> None:
    assert list(out.klass("app_library", name).mixins) == expected, f"mixins of {name}"


def _through_middle(out: Converted) -> None:
    _no_problems(out)
    _assert_mixins(out, "Work", ["AggregateRoot"])
    _assert_mixins(out, "Middle", [])


ROWS_R23 = [
    Row(
        "an abstract class whose concrete subclasses are all roots and that is a range is a root",
        UmlRule.ABSTRACT_ROOT,
        _work_model(),
        _work_is_root,
        _DEFAULTS,
        cites="R-23",
    ),
    Row(
        "an abstract class that no slot ranges over is not a root",
        UmlRule.ABSTRACT_ROOT,
        _work_model(ranged=False),
        _work_is_plain,
        _DEFAULTS,
    ),
    Row(
        "an abstract class with a concrete subclass that is not a root is not a root",
        UmlRule.ABSTRACT_ROOT,
        _work_model(book=None),
        _work_is_plain,
        _DEFAULTS,
    ),
    Row(
        "an abstract class with no concrete subclass is not a root",
        UmlRule.ABSTRACT_ROOT,
        model(
            klass(WORK, "lib:Work", abstract=True),
            klass(SHELF, "lib:Shelf", stereotype="root"),
            links=(link(2, SHELF, WORK, target_role="lib:holds", target_card="0..*"),),
        ),
        _work_is_plain,
        _DEFAULTS,
    ),
    Row(
        "the concrete descendants are taken through an abstract middle class",
        UmlRule.ABSTRACT_ROOT,
        model(
            klass(WORK, "lib:Work", abstract=True),
            klass(MID, "lib:Middle", abstract=True),
            klass(BOOK, "lib:Book", stereotype="root"),
            klass(SHELF, "lib:Shelf", stereotype="root"),
            links=(
                generalisation(1, MID, WORK),
                generalisation(2, BOOK, MID),
                link(3, SHELF, WORK, target_role="lib:holds", target_card="0..*"),
            ),
        ),
        _through_middle,
        _DEFAULTS,
    ),
    Row(
        "a unique key of an abstract root is scoped to the tenant",
        UmlRule.ABSTRACT_ROOT,
        _work_model(
            work_attributes=(attribute(11, WORK, "lib:title"),),
            tags=(tag(WORK, "unique_key", "k: title"),),
        ),
        _work_key,
        _DEFAULTS,
    ),
]


# --- R-24 a slot shared across packages (PD-16, D-22 C-1, D-5) ---------------------------------------------

AFIRST_PKG, BHOME_PKG, ZED_PKG = 21, 22, 23
CLASS_A, CLASS_B, CLASS_Z = 30, 31, 32
_THREE = (
    UmlPackage(package_id=MODEL_PKG, name="model"),
    UmlPackage(package_id=AFIRST_PKG, name="afirst", parent_id=MODEL_PKG),
    UmlPackage(package_id=BHOME_PKG, name="bhome", parent_id=MODEL_PKG),
    UmlPackage(package_id=ZED_PKG, name="zed", parent_id=MODEL_PKG),
)


def _parent_slot(owner: int, attribute_id: int, **bounds: str | None) -> UmlAttribute:
    return attribute(attribute_id, owner, "lib:hasParent", **bounds)


Usage = tuple[str, dict[str, object]]  # the module of a class and the limits its slot_usage carries


def _home_in(home: str, others: list[str], *, usage_in: dict[str, Usage]) -> Check:
    """The slot is defined in ``home`` only; each other module imports it and carries its own limits."""

    def check(out: Converted) -> None:
        _no_problems(out)
        for module, schema in out.schemas.items():
            if module != "app":
                defined = "has_parent" in schema.slots
                assert defined is (module == home), (
                    f"has_parent is defined in {home} only, not {module}"
                )
        for module in others:
            assert home in out.schemas[module].imports, f"{module} imports the home {home}"
        for holder, (module, expected) in usage_in.items():
            usages = out.klass(module, holder).slot_usage
            found = _limits(usages["has_parent"]) if "has_parent" in usages else {}
            assert found == expected, f"the slot_usage limits of {holder}.has_parent"

    return check


def _usage(module: str, **limits: object) -> Usage:
    return module, limits


def _cross_model(
    *, book_imports_shelf: bool = False, shelf_imports_book: bool = False, book: dict | None = None
) -> object:
    links = []
    if shelf_imports_book:
        links.append(link(1, SHELF, BOOK, target_role="lib:book", target_card="0..1"))
    if book_imports_shelf:
        links.append(link(2, BOOK, SHELF, target_role="lib:shelf", target_card="0..1"))
    return model(
        klass(BOOK, "lib:Book", CATALOGUE_PKG, attributes=(_parent_slot(BOOK, 1, **(book or {})),)),
        klass(SHELF, "lib:Shelf", SHELVES_PKG, attributes=(_parent_slot(SHELF, 2),)),
        links=tuple(links),
    )


def _by_three() -> object:
    """``afirst`` imports ``bhome`` (A -> B); A.has_parent ranges over Z of ``zed``, B's over B itself."""
    return model(
        klass(CLASS_A, "lib:Alpha", AFIRST_PKG),
        klass(CLASS_B, "lib:Beta", BHOME_PKG),
        klass(CLASS_Z, "lib:Zed", ZED_PKG),
        links=(
            link(1, CLASS_A, CLASS_B, target_role="lib:beta", target_card="0..1"),
            link(2, CLASS_A, CLASS_Z, target_role="lib:hasParent", target_card="0..1"),
            link(3, CLASS_B, CLASS_B, target_role="lib:hasParent", target_card="0..1"),
        ),
        packages=_THREE,
    )


def _range_module_imported(out: Converted) -> None:
    _no_problems(out)
    assert "has_parent" in out.schemas["app_bhome"].slots, (
        "the others import bhome, so it is the home"
    )
    assert out.slot("app_bhome", "has_parent").range == "Zed", (
        "the slot takes the first usage's range"
    )
    assert "app_zed" in out.schemas["app_bhome"].imports, (
        "the home imports the module of its slot's range"
    )
    assert sorted(out.schemas) == ["app", "app_afirst", "app_bhome", "app_zed"], (
        "no module is merged"
    )


def _cycle_by_sharing(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas) == ["app", "app_afirst", "app_bhome"], "bhome and zed are one module"
    assert sorted(out.schemas["app_bhome"].classes) == ["Beta", "Zed"], (
        "the merged module holds both"
    )
    assert out.report_lines("merged_cycle") == [
        "app_bhome: the packages bhome, zed are written as one module"
    ], "the merge from the final imports is reported once, naming the packages"
    assert "has_parent" in out.schemas["app_bhome"].slots, (
        "the slot is defined in the merged module"
    )


ROWS_R24 = [
    Row(
        "the slot is defined in the module the other imports, with the other's own limits",
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        _cross_model(shelf_imports_book=True, book={"lower": "0"}),
        _home_in(
            "app_catalogue",
            ["app_shelves"],
            usage_in={
                "Book": _usage("app_catalogue", required=False),
                "Shelf": _usage("app_shelves", required=True),
            },
        ),
        cites="R-24",
    ),
    Row(
        "the home is the module every other reaches, not the first in path order",
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        _cross_model(book_imports_shelf=True),
        _home_in(
            "app_shelves",
            ["app_catalogue"],
            usage_in={"Book": _usage("app_catalogue"), "Shelf": _usage("app_shelves")},
        ),
    ),
    Row(
        "failure: no module of the usages is imported by the others",
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        _cross_model(),
        _problem(
            UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
            "has_parent: used in app_catalogue, app_shelves and no one of them is imported by the others",
        ),
    ),
    Row(
        "failure: one slot name with two IRIs in two packages",
        UmlRule.CLASS_IRI,
        model(
            klass(BOOK, "lib:Book", CATALOGUE_PKG, attributes=(_parent_slot(BOOK, 1),)),
            klass(
                SHELF,
                "lib:Shelf",
                SHELVES_PKG,
                attributes=(attribute(2, SHELF, "bibo:hasParent"),),
            ),
            links=(link(1, SHELF, BOOK, target_role="lib:book", target_card="0..1"),),
        ),
        _problem(UmlRule.CLASS_IRI, "has_parent", "https://example.org/ns/library#hasParent"),
    ),
    Row(
        "the home also imports the module of its slot's range, which the first usage chose",
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        _by_three(),
        _range_module_imported,
    ),
    Row(
        "a cycle that sharing creates is merged into one module, from the final imports (D-5)",
        UmlRule.SHARED_SLOT_ACROSS_PACKAGES,
        model(
            klass(CLASS_A, "lib:Alpha", AFIRST_PKG),
            klass(CLASS_B, "lib:Beta", BHOME_PKG),
            klass(CLASS_Z, "lib:Zed", ZED_PKG),
            links=(
                link(1, CLASS_A, CLASS_B, target_role="lib:beta", target_card="0..1"),
                link(2, CLASS_A, CLASS_Z, target_role="lib:hasParent", target_card="0..1"),
                link(3, CLASS_B, CLASS_B, target_role="lib:hasParent", target_card="0..1"),
                link(4, CLASS_Z, CLASS_B, target_role="lib:beta", target_card="0..1"),
            ),
            packages=_THREE,
        ),
        _cycle_by_sharing,
    ),
]

# --- carried from 2.5: a unique key may name a role or a reused toolkit slot (PD-21) -----------------------


def _keys_of(name: str, slots: list[str]) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        found = out.klass("app_library", "Book").unique_keys[name]
        assert [str(slot) for slot in found.unique_key_slots] == slots, (
            f"the slots of the key {name}"
        )

    return check


def _keyed_with_role(*tags: object) -> object:
    return model(
        klass(BOOK, "lib:Book", stereotype="root", attributes=_KEYED[:1]),
        klass(CHAPTER, "lib:Chapter"),
        links=(link(1, BOOK, CHAPTER, target_role="lib:hasChapter", target_card="0..*"),),
        tags=tuple(tags),
    )


def _keyed_with_toolkit_slot(*tags: object) -> object:
    return model(
        klass(
            BOOK,
            "lib:Book",
            stereotype="root",
            attributes=(attribute(1, BOOK, "skos:prefLabel"), attribute(2, BOOK, "lib:subtitle")),
        ),
        tags=tuple(tags),
    )


ROWS_KEYS_OF_ROLES = [
    Row(
        "a key names a role slot by its slot name",
        UmlRule.UNIQUE_KEY,
        _keyed_with_role(tag(BOOK, "unique_key", "k: title, has_chapter")),
        _keys_of("k", ["title", "has_chapter"]),
    ),
    Row(
        "a key names a role slot by its UML name",
        UmlRule.UNIQUE_KEY,
        _keyed_with_role(tag(BOOK, "unique_key", "k: hasChapter")),
        _keys_of("k", ["has_chapter"]),
    ),
    Row(
        "a key names a reused toolkit slot by the toolkit's name",
        UmlRule.UNIQUE_KEY,
        _keyed_with_toolkit_slot(tag(BOOK, "unique_key", "k: label, subtitle")),
        _keys_of("k", ["label", "subtitle"]),
        _DESCRIBED,
    ),
    Row(
        "a key names a reused toolkit slot by the attribute's UML name",
        UmlRule.UNIQUE_KEY,
        _keyed_with_toolkit_slot(tag(BOOK, "unique_key", "k: prefLabel")),
        _keys_of("k", ["label"]),
        _DESCRIBED,
    ),
    Row(
        "failure: a role the class does not have",
        UmlRule.UNIQUE_KEY,
        _keyed_with_role(tag(BOOK, "unique_key", "k: has_page")),
        _problem(UmlRule.UNIQUE_KEY, "Book", "unique_key", "has_page"),
    ),
]

# --- carried from 2.4: a toolkit class drawn inside the subtree is the toolkit's (PD-17, R-28) -----------


def _inside_toolkit(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas["app_library"].classes) == ["Book"], (
        "the drawn class is not generated"
    )
    assert out.klass("app_library", "Book").is_a == "Activity", "Book is the toolkit's Activity"
    assert _RP_PROVENANCE in out.schemas["app_library"].imports, "the toolkit module is imported"
    assert out.report_lines("not_generated") == [
        "Activity: drawn as the toolkit's Activity, not generated"
    ], "the left-out class is in the report"


def _inside_mixin(out: Converted) -> None:
    _no_problems(out)
    assert sorted(out.schemas["app_library"].classes) == ["Book"], (
        "the drawn class is not generated"
    )
    assert "ReferenceCollection" in out.klass("app_library", "Book").mixins, (
        "the toolkit mixin is used"
    )


ROWS_DRAWN_INSIDE = [
    Row(
        "a prov:Activity drawn in a converted package is not generated and is the is_a",
        UmlRule.TOOLKIT_MIXINS,
        model(
            klass(BOOK, "lib:Book", stereotype="root"),
            klass(_ACTIVITY, "prov:Activity"),
            links=(generalisation(1, BOOK, _ACTIVITY),),
        ),
        _inside_toolkit,
    ),
    Row(
        "an rp:ReferenceCollection drawn in a converted package is a mixin, not generated",
        UmlRule.TOOLKIT_MIXINS,
        model(
            klass(BOOK, "lib:Book", stereotype="root"),
            klass(_COLLECTION, "rp:ReferenceCollection", abstract=True),
            links=(generalisation(1, BOOK, _COLLECTION),),
        ),
        _inside_mixin,
    ),
]

# --- a reference collection's dct:hasPart role fixes its member class (#241) ------------------------------

_HAS_PART = "dct:hasPart"
_COLLECTION_ROOT = 17  # lib:Collection, the abstract class the collections generalise
_RESOURCE = 18  # lib:Resource, the abstract class Book generalises (#274)


def _shelf(
    *targets: int,
    generalised: bool = False,
    collection: bool = True,
    drawn: bool = False,
    parent_role: int | None = None,
) -> object:
    """Shelf (a root, a reference collection when ``collection``) with a ``dct:hasPart`` role to each target.

    ``generalised`` makes Shelf a collection through an abstract ``lib:Collection`` that mixes it in;
    ``drawn`` through a generalisation to ``rp:ReferenceCollection`` drawn outside the subtree. The
    series is drawn outside too, a target that is not converted. ``parent_role`` (implies
    ``generalised``) draws the abstract parent's own ``dct:hasPart`` role to that target, Book
    generalising an abstract ``lib:Resource``.
    """
    generalised = generalised or parent_role is not None
    holder = _COLLECTION_ROOT if generalised else SHELF
    tagged = collection and not drawn
    tags = (tag(holder, "rp_mixins", "ReferenceCollection"),) if tagged else ()
    parent = (klass(_COLLECTION_ROOT, "lib:Collection", abstract=True),) if generalised else ()
    roles = tuple(
        link(n, SHELF, target, target_role=_HAS_PART, target_card="0..*")
        for n, target in enumerate(targets, start=1)
    )
    is_a = (generalisation(9, SHELF, _COLLECTION_ROOT),) if generalised else ()
    is_a += (generalisation(10, SHELF, _COLLECTION),) if drawn else ()
    if parent_role is not None:
        parent += (klass(_RESOURCE, "lib:Resource", abstract=True),)
        roles += (
            link(7, _COLLECTION_ROOT, parent_role, target_role=_HAS_PART, target_card="0..*"),
        )
        is_a += (generalisation(8, BOOK, _RESOURCE),)
    return model(
        klass(SHELF, "lib:Shelf", stereotype="root"),
        klass(BOOK, "lib:Book", stereotype="root"),
        klass(CHAPTER, "lib:Chapter", stereotype="root"),
        *parent,
        links=(*roles, *is_a),
        tags=tags,
        **_drawn((_COLLECTION, "rp:ReferenceCollection"), (SERIES, "lib:Series")),
    )


def _member_class(expected: str | None, *kept: str) -> Check:
    """Shelf's ``member_class`` is fixed to ``expected`` (or not at all), with these kept lines only."""

    def check(out: Converted) -> None:
        _no_problems(out)
        usage = out.klass("app_library", "Shelf").slot_usage
        fixed = usage["member_class"].equals_string if "member_class" in usage else None
        assert fixed == expected, "the member class the hasPart role fixes"
        assert out.report_lines("toolkit_slot_kept") == list(kept), "the toolkit_slot_kept lines"

    return check


def _parent_member_class(expected: str | None, shelf: str | None, kept: str | None = None) -> Check:
    """The abstract Collection's ``member_class`` is fixed to ``expected``, Shelf's to ``shelf`` (#274).

    ``kept`` is the holder.slot whose role stays the toolkit's ``has_part``, reported.
    """

    def check(out: Converted) -> None:
        _no_problems(out)
        for name, want in (("Collection", expected), ("Shelf", shelf)):
            usage = out.klass("app_library", name).slot_usage
            fixed = usage["member_class"].equals_string if "member_class" in usage else None
            assert fixed == want, f"the member class {name}'s hasPart role fixes"
        if kept is not None:
            lines = out.report_lines("toolkit_slot_kept")
            assert any(
                each.startswith(f"{kept}: the toolkit's has_part is kept") for each in lines
            ), f"{kept} is reported as kept"

    return check


_RANGE_KEPT = "Shelf.has_part: the toolkit's has_part is kept; range {} is not carried"

ROWS_MEMBER_CLASS = [
    Row(
        "a reference collection's hasPart role to a converted class fixes its member class",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK),
        _member_class("Book"),
    ),
    Row(
        "a class that is a reference collection by its domain parent gets the member class too",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK, generalised=True),
        _member_class("Book"),
    ),
    Row(
        "a class that generalises a drawn rp:ReferenceCollection gets the member class too",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK, drawn=True),
        _member_class("Book"),
    ),
    Row(
        "a hasPart role to a class that is not converted is a URI, the toolkit's own range",
        UmlRule.TOOLKIT_SLOT,
        _shelf(SERIES),
        _member_class(None),
    ),
    Row(
        "a lone role to its own class fixes member_class",
        UmlRule.TOOLKIT_SLOT,
        _shelf(SHELF),
        _member_class("Shelf"),
    ),
    Row(
        "a role to its own class beside one to Book stays nesting",
        UmlRule.TOOLKIT_SLOT,
        _shelf(SHELF, BOOK),
        _member_class("Book", _RANGE_KEPT.format("shelf")),
    ),
    Row(
        "a self-role on an abstract collection whose subclass draws its own role stays nesting",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK, parent_role=_COLLECTION_ROOT),
        _parent_member_class(None, "Book", kept="Collection.has_part"),
    ),
    Row(
        "a subclass's self-role under a parent that fixes a member class stays nesting",
        UmlRule.TOOLKIT_SLOT,
        _shelf(SHELF, parent_role=_RESOURCE),
        _parent_member_class("Resource", None, kept="Shelf.has_part"),
    ),
    Row(
        "a hasPart role on a class that is not a reference collection changes nothing",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK, collection=False),
        _member_class(None, _RANGE_KEPT.format("book")),
    ),
    Row(
        "failure: hasPart roles to two different classes on one collection name the class",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK, CHAPTER),
        _problem(UmlRule.TOOLKIT_SLOT, "Shelf", "Book", "Chapter"),
    ),
    Row(
        "an abstract collection whose subclass draws its own member role fixes none; the subclass does",
        UmlRule.TOOLKIT_SLOT,
        _shelf(BOOK, parent_role=_RESOURCE),
        _parent_member_class(None, "Book", kept="Collection.has_part"),
    ),
    Row(
        "an abstract collection whose subclasses draw no member role keeps its member class",
        UmlRule.TOOLKIT_SLOT,
        _shelf(parent_role=_RESOURCE),
        _parent_member_class("Resource", None),
    ),
    Row(
        "failure: a subclass's member class that does not descend from the parent's names both",
        UmlRule.TOOLKIT_SLOT,
        _shelf(CHAPTER, parent_role=_RESOURCE),
        _problem(UmlRule.TOOLKIT_SLOT, "Shelf", "Chapter", "Collection", "Resource"),
    ),
]

# --- a package's module_kind tagged value (#245 part 1) ---------------------------------------------------

_LIBRARY_ELEMENT, _SHELVES_ELEMENT = (
    30,
    31,
)  # the packages' own objects, which own their tagged values


def _kinded(*tags: tuple[int, str], cycle: bool = False) -> object:
    """Book in library and Shelf in shelves, each package with its own object; ``cycle`` links them both ways."""
    packages = (
        UmlPackage(package_id=MODEL_PKG, name="model"),
        UmlPackage(
            package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG, object_id=_LIBRARY_ELEMENT
        ),
        UmlPackage(
            package_id=SHELVES_PKG, name="shelves", parent_id=MODEL_PKG, object_id=_SHELVES_ELEMENT
        ),
    )
    links = (
        (
            link(1, BOOK, SHELF, target_role="lib:onShelf", target_card="0..1"),
            link(2, SHELF, BOOK, target_role="lib:holds", target_card="0..*"),
        )
        if cycle
        else ()
    )
    return model(
        klass(BOOK, "lib:Book", stereotype="root"),
        klass(SHELF, "lib:Shelf", SHELVES_PKG, stereotype="root"),
        packages=packages,
        links=links,
        tags=tuple(tag(owner, "module_kind", value) for owner, value in tags),
    )


def _kinds(**expected: str) -> Check:
    def check(out: Converted) -> None:
        _no_problems(out)
        found = {name: out.schemas[name].annotations["module_kind"].value for name in expected}
        assert found == expected, "the module_kind of each module"

    return check


ROWS_MODULE_KIND = [
    Row(
        "a package's module_kind tagged value is its module's annotation, the others stay domain",
        UmlRule.PACKAGE_MODULE,
        _kinded((_LIBRARY_ELEMENT, "access")),
        _kinds(app_library="access", app_shelves="domain"),
    ),
    Row(
        "a module_kind tagged value is read case-blind, as a class annotation's is",
        UmlRule.PACKAGE_MODULE,
        _kinded((_LIBRARY_ELEMENT, "Access")),
        _kinds(app_library="access"),
    ),
    Row(
        "a package with no module_kind tagged value is a domain module",
        UmlRule.PACKAGE_MODULE,
        _kinded(),
        _kinds(app_library="domain", app_shelves="domain"),
    ),
    Row(
        "failure: a module_kind the metamodel does not know names the package and the value",
        UmlRule.PACKAGE_MODULE,
        _kinded((_LIBRARY_ELEMENT, "planet")),
        _problem(UmlRule.PACKAGE_MODULE, "library", "planet"),
    ),
    Row(
        "failure: packages written as one module with different kinds name the module",
        UmlRule.PACKAGE_MODULE,
        _kinded((_LIBRARY_ELEMENT, "access"), cycle=True),
        _problem(UmlRule.PACKAGE_MODULE, "app_library", "access", "domain"),
    ),
]

ROWS: list[Row] = [
    *ROWS_MEMBER_CLASS,
    *ROWS_MODULE_KIND,
    *ROWS_KEYS_OF_ROLES,
    *ROWS_DRAWN_INSIDE,
    *ROWS_R24,
    *ROWS_R23,
    *ROWS_R18,
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
    *ROWS_R20,
    *ROWS_R21,
    *ROWS_R12,
    *ROWS_R13,
    *ROWS_NARROWED,
    *ROWS_W3,
    *ROWS_D14,
    *ROWS_R25,
    *ROWS_R26,
    *ROWS_R27,
    *ROWS_R28,
    *ROWS_ACTIVITY_ROOT,
    *ROWS_R15,
    *ROWS_R22,
    *ROWS_R30,
]


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


def test_a_unique_key_dumps_to_yaml_with_its_scope_and_nulls() -> None:
    out = run(_keyed(tag(BOOK, "unique_key", "k: title; nulls=equal")))
    text = yaml_dumper.dumps(out.schemas["app_library"])
    for line in ("unique_keys:", "unique_key_name: k", "- title", "consider_nulls_inequal: false"):
        assert line in text, text
    assert "tag: rp_unique_scope" in text, text
    assert "value: tenant" in text, text


@pytest.mark.parametrize(
    "row", [pytest.param(row, id=f"{row.rule.value}: {row.case}") for row in ROWS]
)
def test_a_rule_row(row: Row) -> None:
    row.check(run(row.uml, **row.overrides))  # each check states its own failure messages


_GENERATION_MODEL = (
    Path(__file__).parents[3] / "rdf_persistence_generation" / "model" / "rp_generation.yaml"
)
_CITATION = re.compile(r"R-(\d+)(?:\s*(?:to|\.\.)\s*R-(\d+))?")


def _cited_rules() -> list[str]:
    """The ``R-n`` the ``UmlRule`` descriptions cite, a range (``R-25 to R-28``) expanded."""
    values = yaml.safe_load(_GENERATION_MODEL.read_text())["enums"]["UmlRule"]["permissible_values"]
    cited: set[int] = set()
    for value in values.values():
        for first, last in _CITATION.findall(value.get("description") or ""):
            cited.update(range(int(first), int(last or first) + 1))
    return [f"R-{number}" for number in sorted(cited)]


@pytest.mark.parametrize("cited", _cited_rules())
def test_every_cited_rule_has_a_row(cited: str) -> None:
    rows = [*ROWS, *ROLE_ROWS, *WORKFLOW_ROWS]  # the role and workflow rules keep their own tables
    assert cited in {getattr(row, "cites", None) for row in rows}, (
        f"the rule {cited} has no row that cites it"
    )


def test_the_cited_rules_are_read_from_the_descriptions() -> None:
    cited = _cited_rules()
    assert {"R-1", "R-15", "R-22", "R-25", "R-26", "R-27", "R-28", "R-29"} <= set(cited), (
        f"a range and a pair are expanded: {cited}"
    )
