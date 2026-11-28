"""Steps of ``decimal_numbers.feature``: a measure's decimal, float and double values in one form (langstring-support DEC-8, PD-9).

The scenarios drive ``Documents`` on a context generated from the measures fixture.
"""

import asyncio
import json
import re
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when
from rdflib import XSD, Graph, URIRef

from rdf_persistence.api.services.documents import Documents
from rdf_persistence.core.domain.exceptions import InvalidBody
from rdf_persistence.core.domain.media import JSON, JSON_LD
from rdf_persistence.iris.domain.layout import graph_iri
from rdf_persistence.schema.services.schema import load_schema
from tests.measures import MEASURE, generate_measures

scenarios("decimal_numbers.feature")

TENANT = "https://example.org/libraries/t1"
MEDIA_TYPES = {"plain JSON": JSON, "JSON-LD": JSON_LD}
SLOTS = {"decimal": "dec", "float": "flt", "double": "dbl"}
TEXT = re.compile(r'^the text "?(?P<text>[^"]*)"?$')
NUMBER = re.compile(r"^the number (?P<number>[0-9.]+)$")
DOUBLE = URIRef("https://example.org/ns/measures#dbl")


class Run:
    """One measure's documents and what the scenario has seen of it so far."""

    def __init__(self, documents: Documents, generated: Path) -> None:
        self.documents = documents
        self.generated = generated
        self.cls = documents.aggregates["measures"]
        self.stored = Graph()
        self.shown: dict = {}
        self.written: Graph | None = None
        self.refusal: InvalidBody | None = None


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Documents, Path]:
    schema, folder = generate_measures(tmp_path_factory.mktemp("decimal_numbers"))
    return Documents(load_schema(schema), folder), folder


@pytest.fixture
def run(generated: tuple[Documents, Path]) -> Run:
    return Run(*generated)


def _form_of(form: str) -> object:
    """The JSON value a form names: the text or the number."""
    if text := TEXT.match(form):
        return text["text"]
    number = NUMBER.match(form)
    assert number, f"a form is a text or a number: {form}"
    return float(number["number"])


def _written_value(value: str) -> object:
    """The JSON value the scenario's wording names."""
    if value.startswith("the text "):
        return value.removeprefix("the text ")
    return {"true": True}.get(value) or (float(value) if "." in value else int(value))


@given(parsers.parse("a measure whose {kind} value is 1.5"))
def _measure(run: Run, kind: str) -> None:
    body = {"id": MEASURE, "label": "m", SLOTS[kind]: "1.5" if kind != "double" else 1.5}
    run.stored = run.documents.expand(body, run.cls)


@when(parsers.parse("Ada reads the measure as {representation}"))
def _read(run: Run, representation: str) -> None:
    text = asyncio.run(
        run.documents.render(run.stored, graph_iri(MEASURE), run.cls, MEDIA_TYPES[representation])
    )
    run.shown = json.loads(text)


@then(parsers.parse("the {kind} value is shown as {form}"))
def _shown(run: Run, kind: str, form: str) -> None:
    shown = run.shown[SLOTS[kind]]
    assert shown == _form_of(form), f"the {kind} value is shown as {shown!r}"
    assert type(shown) is type(_form_of(form)), f"the {kind} value is shown as {shown!r}"


@then(parsers.parse("the generated type of the {kind} value is {form}"))
def _typed(run: Run, kind: str, form: str) -> None:
    source = (run.generated.parents[1] / "web/src/domain/generated/measures.ts").read_text(
        encoding="utf-8"
    )
    found = re.search(rf"\b{SLOTS[kind]}\??: (\w+);", source)
    assert found, f"the generated types name {SLOTS[kind]}"
    expected = "string" if isinstance(_form_of(form), str) else "number"
    assert found[1] == expected, f"the generated type of the {kind} value is {found[1]}"


@when(parsers.parse("Ada writes a measure whose double value is {value}, in {format}"))
def _write(run: Run, value: str, format: str) -> None:
    media_type = MEDIA_TYPES[format]
    body: dict = {"id": MEASURE, "label": "m", "dbl": _written_value(value)}
    if media_type == JSON_LD:
        body = {"@context": run.documents.context, "type": "Measure", **body}
    try:
        graph, _ = asyncio.run(
            run.documents.parse(
                json.dumps(body).encode(),
                media_type,
                run.cls,
                MEASURE,
                creating=False,
                tenant=TENANT,
            )
        )
        asyncio.run(run.documents.validate(graph))
        run.written = graph
    except InvalidBody as refusal:
        run.refusal = refusal


@then("the write is accepted")
def _accepted(run: Run) -> None:
    assert run.refusal is None, f"the write was refused: {run.refusal}"
    assert run.written is not None, "the write gave triples"


@then("the measure's double value is stored as a double")
def _stored_as_double(run: Run) -> None:
    assert run.written is not None, "the write gave triples"
    values = list(run.written.objects(URIRef(MEASURE), DOUBLE))
    assert [(o.datatype, float(o)) for o in values] == [(XSD.double, 3.0)], (
        "the double value is stored with the double datatype"
    )


@then("the answer is 422 with a problem response naming the double value")
def _refused(run: Run) -> None:
    assert run.refusal is not None, (
        "the write was refused (InvalidBody, which the service answers 422)"
    )
    assert "dbl" in str(run.refusal), f"the refusal names the double value: {run.refusal}"
