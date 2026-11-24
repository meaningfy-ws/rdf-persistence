"""Helpers the writer's tests share: a drawn loan model, two schemas, a report and ``write`` over them."""

from pathlib import Path

from linkml_runtime.linkml_model.meta import SchemaDefinition

from rdf_persistence_generation.generated.rp_generation import ReportKind, ReportLine, UmlPrefix
from rdf_persistence_generation.uml.write import write
from tests.generator.uml_model import (
    BOOK,
    PREFIXES,
    Converted,
    initial,
    klass,
    model,
    object_,
    run,
    state,
    state_flow,
    statechart,
)

ROOT = "lib"
ROLE_DEFINITION = 30  # the drawn toolkit class rp:RoleDefinition
LIBRARY = "https://example.org/ns/library/"
INITIAL, REQUESTED, APPROVED, REFUSED, RETURNED, CHART = 50, 51, 52, 53, 54, 70


def _schemas() -> list[SchemaDefinition]:
    return [
        SchemaDefinition(id="https://example.org/ns/library", name="lib_books"),
        SchemaDefinition(id="https://example.org/ns/shelves", name="lib_shelves"),
    ]


def _report() -> list[ReportLine]:
    return [
        ReportLine(report_kind=ReportKind.NOT_GENERATED, element="lib:Shelf", message="stereotype"),
        ReportLine(report_kind=ReportKind.NO_NOTE, element="lib:Book", message="no note"),
    ]


def _write(converted: Converted, out: Path, report: list[ReportLine] | None = None):
    return write(
        list(converted.schemas.values()),
        converted.report if report is None else report,
        out,
        ROOT,
        files=converted.files,
    )


def _loan() -> Converted:
    """The design's concrete example: the diagram ``lib:loan`` and the roles it names."""
    roles = tuple(
        object_(
            40 + n, name, ROLE_DEFINITION, ("role", name), ("level", "tenant"), ("actions", "read")
        )
        for n, name in enumerate(("librarian", "reader"))
    )
    nodes = (
        initial(INITIAL),
        state(REQUESTED, "requested"),
        state(APPROVED, "approved"),
        state(REFUSED, "refused"),
        state(RETURNED, "returned"),
    )
    flows = (
        state_flow(100, INITIAL, REQUESTED),
        state_flow(101, REQUESTED, APPROVED, roles="librarian"),
        state_flow(102, REQUESTED, REFUSED, roles="librarian", comment_required="true"),
        state_flow(103, APPROVED, RETURNED, roles="librarian,reader"),
        state_flow(104, REFUSED, REQUESTED, roles="reader"),
    )
    uml = model(
        klass(BOOK, "lib:Book"),
        klass(ROLE_DEFINITION, "rp:RoleDefinition"),
        objects=roles,
        state_nodes=nodes,
        state_flows=flows,
        statecharts=(statechart(CHART, "lib:loan", *(each.object_id for each in nodes)),),
    )
    converted = run(
        uml,
        root_name=ROOT,
        prefixes=[
            UmlPrefix(prefix_name=name, namespace=namespace)
            for name, namespace in {**PREFIXES, "lib": LIBRARY}.items()
        ],
    )
    assert converted.problems == [], converted.problem_texts()
    return converted
