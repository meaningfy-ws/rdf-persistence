"""TC-4: names, IRIs, titles, permissible-value keys and the root path (PD-6, PD-10, PD-12)."""

import pytest
from linkml.linter.rules import StandardNamingRule

from rdf_persistence_generation.generated.rp_generation import CheckProblem, UmlName, UmlRule
from rdf_persistence_generation.problems import format_problem
from rdf_persistence_generation.uml.naming import (
    CLASS_NAME_PATTERN,
    SLOT_NAME_PATTERN,
    check_class_name,
    check_slot_name,
    permissible_value_key,
    resolve_name,
    rp_path_for,
    slot_name,
    title_for,
)

FILE_PREFIXES = {"lib": "https://example.org/ns/library#", "dct": "http://purl.org/dc/terms/"}
METAMODEL_PREFIXES = {
    "dcterms": "http://purl.org/dc/terms/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
}


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("hasChapter", "has_chapter"),
        ("ISBNRecord", "isbn_record"),
        ("title", "title"),
        ("x2Y", "x2_y"),
    ],
)
def test_a_slot_name_is_the_local_name_in_snake_case(written: str, expected: str) -> None:
    assert slot_name(written) == expected, f"{written} is {expected} in snake case"


@pytest.mark.parametrize(
    ("literal", "expected"),
    [("ADMIN", "admin"), ("lib:onLoan", "on_loan"), ("Reader", "reader")],
)
def test_a_permissible_value_key_is_the_local_name_in_snake_case(
    literal: str, expected: str
) -> None:
    assert permissible_value_key(literal) == expected, f"{literal} keys as {expected}"


@pytest.mark.parametrize(
    ("class_name", "expected"),
    [
        ("Book", "books"),
        ("Library", "libraries"),
        ("Box", "boxes"),
        ("Class", "classes"),
        ("Buzz", "buzzes"),
        ("Match", "matches"),
        ("Dish", "dishes"),
        ("Day", "days"),
        ("ISBNRecord", "isbn-records"),
    ],
)
def test_the_root_path_is_the_kebab_case_plural(class_name: str, expected: str) -> None:
    assert rp_path_for(class_name) == expected, f"{class_name} has the path {expected}"


def test_a_title_splits_the_name_and_keeps_an_all_capital_word() -> None:
    assert title_for("ISBNRecordFile") == "ISBN record file", "an all-capital word is kept"
    assert title_for("hasChapter") == "Has chapter", "the first word is capitalised"


def test_a_title_is_the_alias_when_set() -> None:
    assert title_for("ISBNRecordFile", alias="Record file") == "Record file", "the alias wins"


def test_a_one_letter_slot_is_a_problem() -> None:
    problem = check_slot_name("x", "lib:x")
    assert isinstance(problem, CheckProblem), "a one-letter slot name is refused"
    assert problem.element == "lib:x", f"the problem names the element: {problem.element}"
    assert "[a-z][_a-z0-9]+" in problem.message, f"the message gives the pattern: {problem.message}"


def test_a_valid_slot_name_is_no_problem() -> None:
    assert check_slot_name("has_chapter", "lib:hasChapter") is None, "a valid slot name passes"


@pytest.mark.parametrize("name", ["book", "B", "Book_Copy", "1Book"])
def test_a_class_name_that_breaks_the_pattern_is_a_problem(name: str) -> None:
    problem = check_class_name(name, f"lib:{name}")
    assert isinstance(problem, CheckProblem), f"{name} is refused as a class name"
    assert "[A-Z][a-zA-Z0-9]+" in problem.message, (
        f"the message gives the pattern: {problem.message}"
    )


def test_the_name_patterns_are_the_linters() -> None:
    """The lint step's ``standard_naming`` rule (default config) is the one the checks repeat."""
    patterns = StandardNamingRule.PATTERNS
    assert patterns["uppercamel"].pattern == CLASS_NAME_PATTERN, (
        f"the class pattern is the linter's upper camel case: {CLASS_NAME_PATTERN}"
    )
    assert patterns["snake"].pattern == SLOT_NAME_PATTERN, (
        f"the slot pattern is the linter's snake case: {SLOT_NAME_PATTERN}"
    )


def test_a_valid_class_name_is_no_problem() -> None:
    assert check_class_name("ISBNRecord", "lib:ISBNRecord") is None, "a valid class name passes"


def test_a_prefixed_name_is_split_and_expanded() -> None:
    resolved = resolve_name("lib:Book", "Book", FILE_PREFIXES, METAMODEL_PREFIXES, "prefixes.yaml")
    assert resolved == UmlName(
        name="Book", iri="https://example.org/ns/library#Book", curie="lib:Book"
    ), f"the prefix is expanded with the file's namespace: {resolved}"


def test_a_namespace_the_metamodel_names_takes_the_metamodel_prefix() -> None:
    resolved = resolve_name(
        "dct:identifier", "Book.id", FILE_PREFIXES, METAMODEL_PREFIXES, "prefixes.yaml"
    )
    assert resolved == UmlName(
        name="identifier", iri="http://purl.org/dc/terms/identifier", curie="dcterms:identifier"
    ), f"the metamodel's prefix name replaces the file's: {resolved}"


def test_an_unprefixed_name_has_no_explicit_iri() -> None:
    resolved = resolve_name("Book", "Book", FILE_PREFIXES, METAMODEL_PREFIXES, "prefixes.yaml")
    assert resolved == UmlName(name="Book"), f"an unprefixed name carries no IRI: {resolved}"


def test_an_unknown_prefix_is_one_problem_naming_the_prefix_and_the_element() -> None:
    problem = resolve_name(
        "zzz:Book", "zzz:Book", FILE_PREFIXES, METAMODEL_PREFIXES, "prefixes.yaml"
    )
    assert isinstance(problem, CheckProblem), "an unknown prefix is refused"
    assert problem.rule == UmlRule.CLASS_IRI.value, f"the rule is class_iri: {problem.rule}"
    assert format_problem(problem) == "[class_iri] zzz:Book: prefix zzz is not in prefixes.yaml", (
        format_problem(problem)
    )
