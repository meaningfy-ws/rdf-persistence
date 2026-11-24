"""Spec rp-aggregate-store, SPARQL is never built by concatenating input (PD-3)."""

import re

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import BaseModel, ValidationError
from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql import prepareQuery, prepareUpdate

from rdf_persistence.core.domain.base import RpModel
from rdf_persistence.core.domain.exceptions import SparqlError
from rdf_persistence.core.domain.sparql import (
    SparqlTerm,
    absent_patterns,
    checked_group,
    contains_patterns,
    count,
    fill,
    fill_terms,
    fragment,
    fragment_terms,
    join,
    match_patterns,
    no_value_patterns,
    optional_value_patterns,
    order_by,
    term,
    term_list,
    triples_block,
    union,
    value_patterns,
    value_variables,
)

EX = "http://example.org/"
HOSTILE = [
    '"} ; DROP ALL ; #',
    '"""',
    "\\",
    "line1\nline2",
    "a\r\nb",
    "}>{<",
    "tab\there",
    "\x00\x07\x1f\x7f",
    "'single' and \"double\"",
    "$name ${name} $$",
    "é中\U0001f600",
]


def parsed_object(rendered: str) -> object:
    """Parse ``rendered`` as the object of one triple and return the term rdflib reads."""
    graph = Graph()
    graph.update(f"INSERT DATA {{ <{EX}s> <{EX}p> {rendered} }}")
    return next(iter(graph))[2]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (URIRef(f"{EX}a"), f"<{EX}a>"),
        (Literal("plain"), '"plain"'),
        (Literal("hola", lang="es"), '"hola"@es'),
        (Literal("hi", lang="en-GB"), '"hi"@en-GB'),
        (Literal(5), f'"5"^^<{XSD.integer}>'),
        (BNode("b1"), "_:b1"),
    ],
    ids=["iri", "plain", "lang", "lang-region", "integer", "blank"],
)
# Typed literals are one class (the datatype branch), so integer stands for date. "lang-region" stays:
# it is the hyphen sub-rule of the language-tag pattern, a different class from "lang".
def test_term_renders_each_kind(value, expected):
    assert term(value) == expected, "each kind of term renders to its SPARQL form"


@pytest.mark.parametrize("text", HOSTILE)
def test_a_literal_with_hostile_characters_parses_back_to_itself(text):
    assert parsed_object(term(Literal(text))) == Literal(text), "the literal survives"


@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_literals_with_a_language_or_datatype_parse_back(text):
    assert parsed_object(term(Literal(text, lang="en"))) == Literal(text, lang="en"), (
        "a literal with a language parses back unchanged"
    )
    assert parsed_object(term(Literal(text, datatype=URIRef(f"{EX}dt")))) == Literal(
        text, datatype=URIRef(f"{EX}dt")
    ), "a literal with a datatype parses back unchanged"


@given(st.text())
def test_any_string_literal_round_trips(text):
    assert parsed_object(term(Literal(text))) == Literal(text), (
        "any string literal parses back unchanged"
    )


@pytest.mark.parametrize(
    "iri", [f"{EX}a>b", f"{EX}a b", f"{EX}{{x}}", f'{EX}a"b', f"{EX}a\nb", f"{EX}a\\b", f"{EX}a|b"]
)
def test_an_iri_that_could_break_out_is_refused(iri):
    with pytest.raises(SparqlError, match="IRI"):
        term(URIRef(iri))


def test_a_datatype_iri_that_could_break_out_is_refused():
    with pytest.raises(SparqlError, match="IRI"):
        term(Literal("x", datatype=URIRef(f"{EX}a>b")))


@pytest.mark.parametrize("label", ["a b", "a;DROP", "", "a}", "a\n", "a.", "b1.."])
def test_a_blank_node_label_that_is_not_a_label_is_refused(label):
    with pytest.raises(SparqlError, match="blank node"):
        term(BNode(label))


def test_a_raw_string_is_not_a_term():
    with pytest.raises(SparqlError, match="rdflib"):
        term("http://example.org/a")


SUBJECT, PREDICATE, GRAPH = (URIRef(f"{EX}{n}") for n in ("s", "p", "g"))
# One template per kind of SPARQL text the adapters send, each with the names it takes.
TEMPLATES = {
    "select": ("SELECT ?p ?o WHERE { $subject ?p ?o } LIMIT 5", ["subject"]),
    "ask": (
        "ASK { GRAPH $graph { $subject $predicate $object } }",
        ["graph", "subject", "predicate", "object"],
    ),
    "filter": ("SELECT ?s WHERE { ?s ?p ?o FILTER(?o = $object) }", ["object"]),
    "update": (
        "DELETE { GRAPH $graph { $subject $predicate ?o } } "
        "INSERT { GRAPH $graph { $subject $predicate $object } } "
        "WHERE { OPTIONAL { GRAPH $graph { $subject $predicate ?o } } }",
        ["graph", "subject", "predicate", "object"],
    ),
}
VALUES = {"subject": SUBJECT, "predicate": PREDICATE, "graph": GRAPH}


def filled(kind: str, text: str) -> str:
    template, names = TEMPLATES[kind]
    terms = {n: term(Literal(text) if n == "object" else VALUES[n]) for n in names}
    return fill(template, **terms)


@pytest.mark.parametrize("kind", TEMPLATES)
@pytest.mark.parametrize("text", HOSTILE)
def test_every_template_kind_stays_valid_with_a_hostile_literal(kind, text):
    (prepareUpdate if kind == "update" else prepareQuery)(filled(kind, text))


def test_an_injection_attempt_matches_nothing_and_changes_nothing():
    dataset = Dataset()
    dataset.graph(GRAPH).add((SUBJECT, PREDICATE, Literal("kept")))
    attack = '"} ; DROP ALL ; #'
    assert list(dataset.query(filled("filter", attack))) == [], "the attack matches no row"
    dataset.update(filled("update", attack))
    stored = {o for _, _, o in dataset.graph(GRAPH)}
    assert stored == {Literal(attack)}, (
        "the attack is stored as a plain value and nothing is dropped"
    )


def test_a_rendered_term_is_not_substituted_again():
    out = fill("SELECT * WHERE { $a $b ?o }", a=term(Literal("$b")), b=term(URIRef(f"{EX}b")))
    assert out == f'SELECT * WHERE {{ "$b" <{EX}b> ?o }}', (
        "a rendered term is not substituted a second time"
    )


def test_fill_refuses_a_raw_string():
    with pytest.raises(SparqlError, match="term"):
        fill("ASK { $s ?p ?o }", s="<http://example.org/a>")


def test_fill_refuses_a_missing_name():
    with pytest.raises(SparqlError, match="missing"):
        fill("ASK { $s ?p $o }", s=term(SUBJECT))


def test_fill_refuses_an_extra_name():
    with pytest.raises(SparqlError, match="unused"):
        fill("ASK { $s ?p ?o }", s=term(SUBJECT), o=term(SUBJECT))


def test_term_returns_the_type_fill_accepts():
    assert isinstance(term(SUBJECT), SparqlTerm), "a rendered term is the type that fill accepts"


def test_a_triples_block_renders_each_triple_through_term():
    triples = [(SUBJECT, PREDICATE, Literal('"} ; DROP ALL ; #')), (SUBJECT, PREDICATE, GRAPH)]
    block = triples_block(triples)
    assert isinstance(block, SparqlTerm), "fill() accepts it"
    graph = Graph()
    graph.update(f"INSERT DATA {{ {block} }}")
    assert set(graph) == set(triples), "the block parses back to the triples"


def test_an_empty_triples_block_is_valid_in_a_template():
    prepareUpdate(
        fill(
            "INSERT DATA { GRAPH $graph { $triples } }",
            graph=term(GRAPH),
            triples=triples_block([]),
        )
    )


def test_a_triples_block_refuses_a_raw_string():
    with pytest.raises(SparqlError, match="rdflib"):
        triples_block([(SUBJECT, PREDICATE, "raw")])  # type: ignore[list-item]


def test_a_term_list_is_comma_separated_terms_that_parse_in_an_in_filter():
    values = [SUBJECT, GRAPH, Literal('"} ; #')]
    block = term_list(values)
    assert isinstance(block, SparqlTerm), "fill() accepts it"
    prepareQuery(fill("SELECT * WHERE { ?s ?p ?o FILTER (?s IN ($values)) }", values=block))
    assert block == ", ".join(term(v) for v in values), "one rendered term per value, in order"


def test_an_empty_term_list_is_valid_in_an_in_filter():
    prepareQuery(
        fill("SELECT * WHERE { ?s ?p ?o FILTER (?s NOT IN ($values)) }", values=term_list([]))
    )


def test_a_term_list_refuses_a_raw_string():
    with pytest.raises(SparqlError, match="rdflib"):
        term_list(["raw"])  # type: ignore[list-item]


def test_match_patterns_render_one_pattern_per_pair_through_term():
    pairs = [(URIRef(f"{EX}p"), Literal('"} ; DROP ALL ; #')), (URIRef(f"{EX}q"), URIRef(f"{EX}o"))]
    text = fill("ASK { $patterns }", patterns=match_patterns("root", pairs))
    prepareQuery(text)  # parses as one query: the hostile value stayed inside its literal
    assert text.count("?root") == 2, "one pattern per pair, on the named variable"


def test_empty_match_patterns_are_valid_in_a_template():
    prepareQuery(fill("ASK { ?root a ?type . $patterns }", patterns=match_patterns("root", [])))


@pytest.mark.parametrize("variable", ["", "1x", "a b", "x } ; DROP ALL ; {", "?x"])
def test_match_patterns_refuse_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        match_patterns(variable, [])


def test_match_patterns_refuse_a_raw_string():
    with pytest.raises(SparqlError):
        match_patterns("root", [(URIRef(f"{EX}p"), "raw")])  # type: ignore[list-item]


CONTAINS_INJECTIONS = ['"} ; DROP ALL ; #', '"', "\\", "}", "a\nb", "\\u0022"]


@pytest.mark.parametrize("text", CONTAINS_INJECTIONS)
def test_contains_patterns_keep_the_text_inside_one_literal(text):
    """TC-04: the text is matched exactly as given, and nothing else in the query changes."""
    hit, miss = URIRef(f"{EX}hit"), URIRef(f"{EX}miss")
    name, kind = URIRef(f"{EX}name"), URIRef(f"{EX}Thing")
    graph = Graph()
    for subject, value in ((hit, f"xx{text}yy"), (miss, "zzz")):
        graph.add((subject, URIRef(f"{EX}type"), kind))
        graph.add((subject, name, Literal(value)))
    patterns = contains_patterns("root", [(name, Literal(text))])
    query = fill(
        f"SELECT ?root WHERE {{ ?root <{EX}type> <{EX}Thing> . $patterns }}", patterns=patterns
    )
    assert {row[0] for row in graph.query(query)} == {hit}, (
        "only the value holding the text matches"
    )
    assert patterns.count("CONTAINS(") == 1, "one CONTAINS, whatever the text holds"


def test_contains_patterns_render_each_pair_as_its_own_exists_on_its_own_variable():
    pairs = [(URIRef(f"{EX}p"), Literal("a")), (URIRef(f"{EX}q"), Literal("b"))]
    patterns = contains_patterns("root", pairs)
    assert patterns == (
        f"FILTER EXISTS {{ ?root <{EX}p> ?root_c0 . "
        f'FILTER (CONTAINS(LCASE(STR(?root_c0)), LCASE("a"))) }} '
        f"FILTER EXISTS {{ ?root <{EX}q> ?root_c1 . "
        f'FILTER (CONTAINS(LCASE(STR(?root_c1)), LCASE("b"))) }}'
    )
    prepareQuery(fill("ASK { ?root a ?type . $patterns }", patterns=patterns))


def test_contains_patterns_are_case_insensitive():
    graph = Graph()
    graph.add((URIRef(f"{EX}s"), URIRef(f"{EX}p"), Literal("Hello World")))
    patterns = contains_patterns("root", [(URIRef(f"{EX}p"), Literal("LO wo"))])
    assert graph.query(fill("ASK { ?root ?x ?y . $patterns }", patterns=patterns)).askAnswer


def test_empty_contains_patterns_are_empty():
    assert contains_patterns("root", []) == ""


@pytest.mark.parametrize("variable", ["r o", "", "?x"])
def test_contains_patterns_refuse_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        contains_patterns(variable, [])


def test_no_value_patterns_render_one_not_exists_per_predicate_counting_blank_nodes_as_values():
    predicates = [URIRef(f"{EX}p"), URIRef(f"{EX}q")]
    patterns = no_value_patterns("root", predicates)
    assert patterns == (
        f"FILTER NOT EXISTS {{ ?root <{EX}p> ?root_a0 . }} "
        f"FILTER NOT EXISTS {{ ?root <{EX}q> ?root_a1 . }}"
    ), "one NOT EXISTS per predicate, on its own variable, with no blank-node filter"
    prepareQuery(fill("ASK { ?root a ?type . $patterns }", patterns=patterns))
    graph = Graph()
    graph.add((URIRef(f"{EX}s"), URIRef(f"{EX}p"), BNode()))
    asked = fill(
        "ASK { ?root ?x ?y . $patterns }", patterns=no_value_patterns("root", predicates[:1])
    )
    assert not graph.query(asked).askAnswer, "a blank node is a value: the subject is not matched"


def test_no_value_patterns_are_empty_without_predicates():
    assert no_value_patterns("root", []) == ""


@pytest.mark.parametrize("variable", ["r o", "", "?x", "x } ; DROP ALL ; {"])
def test_no_value_patterns_refuse_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        no_value_patterns(variable, [])


def test_no_value_patterns_refuse_an_iri_that_could_break_out():
    with pytest.raises(SparqlError, match="IRI"):
        no_value_patterns("root", [URIRef(f"{EX}a>b")])


def test_contains_patterns_refuse_a_raw_string():
    with pytest.raises(SparqlError):
        contains_patterns("root", [(URIRef(f"{EX}p"), "raw")])  # type: ignore[list-item]


def test_value_patterns_refuse_a_raw_string():
    with pytest.raises(SparqlError):
        value_patterns("root", ["http://example.org/p"])  # type: ignore[list-item]


def test_value_patterns_and_variables_name_one_variable_per_predicate():
    predicates = [URIRef(f"{EX}p"), URIRef(f"{EX}q")]
    patterns = value_patterns("root", predicates)
    assert patterns == f"?root <{EX}p> ?v0 . ?root <{EX}q> ?v1 .", "one pattern per predicate"
    assert value_variables(2) == "?v0 ?v1", "the variables the patterns bind, in order"
    prepareQuery(
        fill("SELECT $vars WHERE { $patterns }", vars=value_variables(2), patterns=patterns)
    )


def test_no_value_patterns_and_no_variables_are_empty():
    assert value_patterns("root", []) == "", "no predicate, no pattern"
    assert value_variables(0) == "", "no predicate, no variable"


@pytest.mark.parametrize("variable", ["", "1x", "a b", "x } ; DROP ALL ; {", "?x"])
def test_value_patterns_refuse_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        value_patterns(variable, [])


def test_absent_patterns_render_one_not_exists_per_predicate_ignoring_blank_nodes():
    predicates = [URIRef(f"{EX}p"), URIRef(f"{EX}q")]
    patterns = absent_patterns("root", predicates)
    assert patterns == (
        f"FILTER NOT EXISTS {{ ?root <{EX}p> ?key_absent_0 . FILTER (!isBlank(?key_absent_0)) }} "
        f"FILTER NOT EXISTS {{ ?root <{EX}q> ?key_absent_1 . FILTER (!isBlank(?key_absent_1)) }}"
    )
    prepareQuery(fill("ASK { ?root a ?type . $patterns }", patterns=patterns))


def test_no_absent_patterns_are_empty():
    assert absent_patterns("root", []) == ""


@pytest.mark.parametrize("variable", ["", "1x", "a b", "x } ; DROP ALL ; {", "?x"])
def test_absent_patterns_refuse_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        absent_patterns(variable, [])


def test_absent_patterns_refuse_an_iri_that_could_break_out():
    with pytest.raises(SparqlError, match="IRI"):
        absent_patterns("root", [URIRef(f"{EX}a>b")])


def test_optional_value_patterns_bind_each_value_or_the_default_in_the_value_variables():
    predicates = [URIRef(f"{EX}p"), URIRef(f"{EX}q")]
    default = URIRef(f"{EX}none")
    patterns = optional_value_patterns("root", predicates, default)
    assert patterns == (
        f"OPTIONAL {{ ?root <{EX}p> ?key_raw_0 . FILTER (!isBlank(?key_raw_0)) }} "
        f"BIND (COALESCE(?key_raw_0, <{EX}none>) AS ?v0) "
        f"OPTIONAL {{ ?root <{EX}q> ?key_raw_1 . FILTER (!isBlank(?key_raw_1)) }} "
        f"BIND (COALESCE(?key_raw_1, <{EX}none>) AS ?v1)"
    )
    prepareQuery(
        fill(
            "SELECT $vars WHERE { ?root a ?type . $patterns }",
            vars=value_variables(2),
            patterns=patterns,
        )
    )


def test_no_optional_value_patterns_are_empty():
    assert optional_value_patterns("root", [], URIRef(f"{EX}none")) == ""


@pytest.mark.parametrize("variable", ["", "1x", "a b", "x } ; DROP ALL ; {", "?x"])
def test_optional_value_patterns_refuse_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        optional_value_patterns(variable, [], URIRef(f"{EX}none"))


def test_optional_value_patterns_refuse_a_predicate_or_default_that_could_break_out():
    with pytest.raises(SparqlError, match="IRI"):
        optional_value_patterns("root", [URIRef(f"{EX}a>b")], URIRef(f"{EX}none"))
    with pytest.raises(SparqlError, match="IRI"):
        optional_value_patterns("root", [URIRef(f"{EX}p")], URIRef(f"{EX}n>one"))


# -1 (negative), True (a bool) and 1.5 (any non-int type) are three classes.
@pytest.mark.parametrize("number", [-1, True, 1.5])
def test_value_variables_refuse_anything_but_a_non_negative_integer(number):
    with pytest.raises(SparqlError):
        value_variables(number)  # type: ignore[arg-type]


# The boundaries 0 and 10**6; interior values are one class with them.
@pytest.mark.parametrize("value", [0, 10**6])
def test_a_count_renders_as_the_digits_of_a_non_negative_integer(value):
    assert fill("LIMIT $n", n=count(value)) == f"LIMIT {value}", "a count renders as its digits"


# -1 (negative), True (a bool) and 1.5 (any non-int type) are three classes.
@pytest.mark.parametrize("value", [-1, True, 1.5])
def test_a_count_refuses_anything_but_a_non_negative_integer(value):
    with pytest.raises(SparqlError):
        count(value)  # type: ignore[arg-type]


def test_an_order_by_renders_the_keys_in_order_and_parses():
    text = fill(
        "SELECT * { ?key ?root ?x } ORDER BY $order", order=order_by(("key", True), ("root", False))
    )
    assert text.endswith("DESC(?key) ASC(?root)"), "direction per key, in the order given"
    prepareQuery(text)


@pytest.mark.parametrize("variable", ["", "a b", "x) ; DROP ALL ; (", "?x"])
def test_an_order_by_refuses_a_variable_that_is_not_a_plain_name(variable):
    with pytest.raises(SparqlError):
        order_by((variable, False))


def test_join_makes_one_term_of_several_in_order_that_fill_accepts():
    joined = join([term(SUBJECT), term(GRAPH), term(Literal("x"))])
    assert isinstance(joined, SparqlTerm), "fill() accepts it"
    assert joined == f"{term(SUBJECT)} {term(GRAPH)} {term(Literal('x'))}", (
        "in order, one space apart"
    )


def test_join_of_nothing_is_an_empty_term():
    assert join([]) == "", "an empty list joins to nothing"


def test_join_refuses_a_raw_string():
    with pytest.raises(SparqlError, match="SparqlTerm"):
        join([term(SUBJECT), "raw"])  # type: ignore[list-item]


def test_union_makes_one_term_of_the_alternatives_that_fill_accepts():
    one, two = fragment("{ $s ?p ?o }", s=term(SUBJECT)), fragment("{ $s ?q ?o }", s=term(SUBJECT))
    united = union([one, two])
    assert isinstance(united, SparqlTerm), "fill() accepts it"
    assert united == f"{one} UNION {two}", "in order, joined by UNION"
    prepareQuery(fill("SELECT * WHERE { $alternatives }", alternatives=united))


def test_union_of_one_part_is_that_part():
    only = fragment("{ $s ?p ?o }", s=term(SUBJECT))
    assert union([only]) == only, "nothing to join"


def test_union_refuses_a_raw_string():
    with pytest.raises(SparqlError, match="SparqlTerm"):
        union([term(SUBJECT), "raw"])  # type: ignore[list-item]


def test_a_fragment_is_a_filled_template_that_can_be_joined_and_filled_again():
    guard = fragment("GRAPH $graph { $graph $p ?o }", graph=term(GRAPH), p=term(PREDICATE))
    assert isinstance(guard, SparqlTerm), "join() and fill() accept it"
    both = fill("ASK { $guards }", guards=join([guard, guard]))
    prepareQuery(both)
    assert both.count(f"GRAPH {term(GRAPH)}") == 2, "both fragments are in the text"


# -- checked_group: the one place a migration pattern's text becomes a SparqlTerm (PD-6, PD-21, PD-22) --

RP_VERSION = URIRef("https://example.org/rp#version")
STAMP = URIRef("https://example.org/rp#dataSchemaVersion")
OWN = (RP_VERSION, STAMP)
FINE = '?s <urn:p> ?o . OPTIONAL { ?s <urn:q> ?r } FILTER (?o != "GRAPH") # SERVICE\n'
SPLIT = "?s ?p ?o } ; CLEAR ALL ; ASK { ?s ?p ?o"

# Refused in a where and in a template alike: the text and the reason the error gives.
REFUSED_ANYWHERE = {
    "a prefixed name": ("?s rdf:type ?o .", "prefixed name"),
    "an empty prefix": ("?s :p ?o .", "prefixed name"),
    "GRAPH": ("GRAPH <urn:g> { ?s ?p ?o }", "GRAPH or SERVICE"),
    "a reserved variable": ("?rp_x <urn:p> ?o .", "reserved variable"),
    "a dollar reserved variable": ("$rp_x <urn:p> ?o .", "reserved variable"),
    "a codepoint escape": ('?s <urn:p> "\\u0041" .', "codepoint escape"),
    "a pattern that does not parse": ("?s <urn:p>", "does not parse"),
    "a pattern that closes its group": (SPLIT, "does not parse"),
}
# Only a where has a filter or a service.
REFUSED_IN_A_WHERE = {
    "a prefixed name read by a text scan as an IRI": (
        "?s ?p ?o FILTER(?o<rdf:x||?p>1)",
        "prefixed name",
    ),
    "SERVICE": ("SERVICE <urn:g> { ?s ?p ?o }", "GRAPH or SERVICE"),
    "GRAPH in a filter": (
        "?s ?p ?o FILTER EXISTS { GRAPH <urn:g> { ?s ?p ?o } }",
        "GRAPH or SERVICE",
    ),
}


@pytest.mark.parametrize("template", [False, True], ids=["where", "template"])
def test_a_pattern_that_is_fine_comes_back_as_a_term(template):
    text = "?s <urn:p> ?o ." if template else FINE
    assert isinstance(checked_group(text, template=template), SparqlTerm), "what fill() accepts"


@pytest.mark.parametrize("template", [False, True], ids=["where", "template"])
def test_a_pattern_that_is_fine_is_not_changed(template):
    text = "?s <urn:p> ?o ." if template else FINE
    assert str(checked_group(text, template=template)) == text, "the same text"


def test_the_graph_variable_is_open_to_a_pattern():
    assert checked_group("?rp_graph <urn:p> ?o .", template=False), "?rp_graph is allowed"


@pytest.mark.parametrize("template", [False, True], ids=["where", "template"])
@pytest.mark.parametrize(("text", "reason"), REFUSED_ANYWHERE.values(), ids=REFUSED_ANYWHERE)
def test_a_pattern_the_parser_does_not_accept_as_a_group_is_refused(text, reason, template):
    with pytest.raises(SparqlError, match=reason):
        checked_group(text, template=template)


@pytest.mark.parametrize(("text", "reason"), REFUSED_IN_A_WHERE.values(), ids=REFUSED_IN_A_WHERE)
def test_a_where_with_a_filter_or_service_is_refused_for_what_the_parser_read(text, reason):
    with pytest.raises(SparqlError, match=reason):
        checked_group(text, template=False)


@pytest.mark.parametrize(
    "text",
    ["?s <urn:p> _:b .", "?s <urn:p> [ <urn:q> 1 ] .", "?s <urn:p> ( 1 2 ) .", "?s <urn:p> () ."],
    ids=["labelled", "bracketed", "collection", "empty collection"],
)
def test_a_blank_node_or_a_collection_is_refused_in_a_template(text):
    with pytest.raises(SparqlError, match="blank node"):
        checked_group(text, template=True)


@pytest.mark.parametrize("text", ["?s <urn:p> [ <urn:q> ?o ] .", "?s <urn:p> ( 1 ) ."])
def test_a_blank_node_or_a_collection_is_allowed_in_a_where(text):
    assert checked_group(text, template=False), "a where only matches"


# Every member of the forbidden list is one class (list membership); one stands for them.
@pytest.mark.parametrize("own", [RP_VERSION])
def test_a_template_that_names_a_forbidden_predicate_is_refused(own):
    with pytest.raises(SparqlError, match="the toolkit's own"):
        checked_group(f"?s <{own}> ?o .", template=True, forbidden=OWN)


@pytest.mark.parametrize("own", [RP_VERSION])
def test_a_where_may_read_a_forbidden_predicate(own):
    assert checked_group(f"?s <{own}> ?o .", template=False, forbidden=OWN), "reading is fine"


def test_a_template_may_name_a_predicate_that_is_not_forbidden():
    assert checked_group("?s <urn:p> ?o .", template=True, forbidden=OWN), (
        "only the list is refused"
    )


def test_a_template_with_a_filter_is_refused_because_a_template_is_read_as_one():
    text = "?s <urn:p> ?o . FILTER (?o > 1)"
    assert checked_group(text, template=False), "a where takes a filter"
    with pytest.raises(SparqlError):
        checked_group(text, template=True)


def test_a_pattern_too_long_for_the_parser_is_refused_with_the_advice_to_split():
    text = " ".join(f"?s <urn:p{n}> ?o{n} ." for n in range(400))
    with pytest.raises(SparqlError, match="too long to check"):
        checked_group(text, template=False)


# -- term models: a bundle of SparqlTerm fields (PD-4, DEC-7) ---------------------------------------


class Pair(BaseModel):
    a: SparqlTerm
    b: SparqlTerm | None = None


T1 = term(URIRef("urn:x"))
T2 = term(URIRef("urn:y"))


def test_a_term_field_keeps_the_sparql_term_it_is_given():
    """TC-14."""
    assert type(Pair(a=T1).a) is SparqlTerm, "the field must stay a SparqlTerm, not become a str"


def test_a_term_field_of_a_model_built_now_takes_a_term_and_refuses_a_raw_string():
    """The model is built inside the test: the field's schema comes from ``SparqlTerm`` at build time."""

    class Built(BaseModel):
        a: SparqlTerm

    assert type(Built(a=T1).a) is SparqlTerm, "a SparqlTerm is taken as it is"
    with pytest.raises(ValidationError):
        Built(a="<urn:x>")  # type: ignore[arg-type]


def test_a_term_field_refuses_a_raw_string():
    """TC-15."""
    with pytest.raises(ValidationError, match="SparqlTerm"):
        Pair(a="<urn:x>")  # type: ignore[arg-type]


def test_a_none_field_is_left_out_so_fill_reports_it_missing():
    """TC-17."""
    with pytest.raises(SparqlError, match=r"missing terms for \['b'\]"):
        fill_terms("$a $b", Pair(a=T1, b=None))


def test_fill_terms_takes_the_model_fields_and_the_extra_terms():
    """TC-55."""
    assert fill_terms("$a $b", Pair(a=T1), b=T2) == "<urn:x> <urn:y>", "model plus extra"


def test_a_name_in_both_the_model_and_the_extra_terms_is_refused():
    """TC-55."""
    with pytest.raises(SparqlError, match=r"term given twice: \['a'\]"):
        fill_terms("$a", Pair(a=T1), a=T2)


def test_fragment_terms_gives_a_sparql_term_and_refuses_a_name_given_twice():
    """TC-55, for fragment_terms."""
    piece = fragment_terms("$a", Pair(a=T1))
    assert type(piece) is SparqlTerm, "a fragment is a term again"
    with pytest.raises(SparqlError, match="term given twice"):
        fragment_terms("$a", Pair(a=T1), a=T2)


# -- the tester's invariants over term models (kept: one property each) ------------------------------


class RawStr(str):
    """A ``str`` subclass that is not a ``SparqlTerm``."""


class Assigned(RpModel):
    a: SparqlTerm


def _assign_a_raw_string() -> object:
    bundle = Assigned(a=T1)
    bundle.a = "<x> } DROP ALL {"  # type: ignore[assignment]
    return bundle


@pytest.mark.parametrize(
    "way_in",
    [
        pytest.param(lambda: Pair(a=RawStr("<x> } DROP ALL {")), id="a-str-subclass"),
        pytest.param(lambda: Pair.model_validate_json('{"a": "<x>"}'), id="json-text"),
        pytest.param(
            lambda: Pair.model_validate(Pair(a=T1).model_dump(mode="json")), id="a-dumped-model"
        ),
        pytest.param(_assign_a_raw_string, id="assignment-on-the-toolkit-base"),
    ],
)
def test_a_sparql_term_field_holds_a_sparql_term_and_nothing_else(way_in):
    """Attacks the field type: no way in (subclass, JSON, a dump, assignment) turns text into a term."""
    with pytest.raises(ValidationError):
        way_in()


@pytest.mark.parametrize("clashing", [["a"], ["a", "b"]])
def test_every_name_in_both_the_model_and_the_extra_terms_is_named_as_given_twice(clashing):
    """Attacks the clash check: the same term given twice is still a clash, and all clashes are named."""
    more = {name: T1 for name in clashing}
    with pytest.raises(SparqlError, match=re.escape(f"term given twice: {clashing!r}")):
        fill_terms("$a $b", Pair(a=T1, b=T2), **more)


class Loose(BaseModel):
    a: SparqlTerm
    n: str = "raw"
    k: int = 3


@pytest.mark.parametrize(
    ("template", "bundle", "more"),
    [
        pytest.param("$a", Pair(a=T1).model_copy(update={"a": "<x>"}), {}, id="copied-raw-value"),
        pytest.param("$a $n", Loose(a=T1), {}, id="a-string-field"),
        pytest.param("$a $k", Loose(a=T1), {}, id="an-int-field"),
        pytest.param("$a", Pair(a=T1, b=T2), {}, id="an-unused-term"),
        pytest.param("$a $zzz", Pair(a=T1), {}, id="a-missing-term"),
        pytest.param("$a $c", Pair(a=T1), {"c": "<x>"}, id="a-raw-value-in-more"),
    ],
)
def test_every_refusal_of_fill_terms_is_a_sparql_error(template, bundle, more):
    """Attacks the error type: no refusal of ``fill_terms`` escapes as a ``TypeError`` or a pydantic error."""
    with pytest.raises(SparqlError):
        fill_terms(template, bundle, **more)
