"""Spec rp-aggregate-store, SPARQL is never built by concatenating input (PD-3)."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from rdflib import BNode, Dataset, Graph, Literal, URIRef
from rdflib.namespace import XSD
from rdflib.plugins.sparql import prepareQuery, prepareUpdate

from rdf_persistence.domain.exceptions import SparqlError
from rdf_persistence.domain.sparql import (
    SparqlTerm,
    count,
    fill,
    fragment,
    join,
    match_patterns,
    order_by,
    term,
    term_list,
    triples_block,
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
        (Literal("2020-01-01", datatype=XSD.date), f'"2020-01-01"^^<{XSD.date}>'),
        (BNode("b1"), "_:b1"),
    ],
    ids=["iri", "plain", "lang", "lang-region", "integer", "date", "blank"],
)
def test_term_renders_each_kind(value, expected):
    assert term(value) == expected


@pytest.mark.parametrize("text", HOSTILE)
def test_a_literal_with_hostile_characters_parses_back_to_itself(text):
    assert parsed_object(term(Literal(text))) == Literal(text), "the literal survives"


@pytest.mark.parametrize("text", HOSTILE)
def test_hostile_literals_with_a_language_or_datatype_parse_back(text):
    assert parsed_object(term(Literal(text, lang="en"))) == Literal(text, lang="en")
    assert parsed_object(term(Literal(text, datatype=URIRef(f"{EX}dt")))) == Literal(
        text, datatype=URIRef(f"{EX}dt")
    )


@given(st.text())
def test_any_string_literal_round_trips(text):
    assert parsed_object(term(Literal(text))) == Literal(text)


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
    assert out == f'SELECT * WHERE {{ "$b" <{EX}b> ?o }}'


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
    assert isinstance(term(SUBJECT), SparqlTerm)


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


@pytest.mark.parametrize("value", [0, 1, 50, 10**6])
def test_a_count_renders_as_the_digits_of_a_non_negative_integer(value):
    assert fill("LIMIT $n", n=count(value)) == f"LIMIT {value}"


@pytest.mark.parametrize("value", [-1, True, 1.5, "5", None])
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


def test_a_fragment_is_a_filled_template_that_can_be_joined_and_filled_again():
    guard = fragment("GRAPH $graph { $graph $p ?o }", graph=term(GRAPH), p=term(PREDICATE))
    assert isinstance(guard, SparqlTerm), "join() and fill() accept it"
    both = fill("ASK { $guards }", guards=join([guard, guard]))
    prepareQuery(both)
    assert both.count(f"GRAPH {term(GRAPH)}") == 2, "both fragments are in the text"
