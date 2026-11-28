"""Steps of ``dependent_aggregates_generation.feature``: a bad dependent class is refused (dependent-aggregates PD-12, PD-14).

Each scenario copies the toy library, breaks its ``audits`` module in one way and calls ``cli.main``
there, as the command line does. The toy's own ``AuditResult`` is the dependent class under attack.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence_generation.generated.rp_generation import UmlLink
from tests.generator.uml_accept import generator_problems
from tests.generator.uml_model import Converted, composition, klass, link, model
from tests.generator.uml_model import run as convert

from .toy_run import copy_toy, edit, generate, tree

scenarios("dependent_aggregates_generation.feature")

AUDITS = "audits.yaml"
POINTER_USAGE = "    slot_usage:\n      of_audit:\n        required: true\n"
POINTER_RANGE = "    slot_uri: lib:ofAudit\n    range: Audit\n"
RESULT_SLOTS = "    slots: [of_audit]\n"
IMPORTS = "  - rdf_persistence/model/rp_annotations\n"


@dataclass(frozen=True)
class Defect:
    """One way to break the pointer slot of ``AuditResult``: the text it replaces, and what replaces it."""

    words: str
    old: str
    new: str
    imports: str = ""


DEFECTS = (
    Defect(
        "optional", POINTER_USAGE, "    slot_usage:\n      of_audit:\n        required: false\n"
    ),
    Defect(
        "multivalued",
        POINTER_USAGE,
        POINTER_USAGE + "        multivalued: true\n",
    ),
    Defect(
        "ranging over a class that is not a root",
        POINTER_RANGE,
        "    slot_uri: lib:ofAudit\n    range: Chapter\n",
        "  - books\n",
    ),
    Defect(
        "ranging over the tenant root",
        POINTER_RANGE,
        "    slot_uri: lib:ofAudit\n    range: Library\n",
        "  - library_tenant\n",
    ),
    Defect(
        'not a slot of "AuditResult"',
        RESULT_SLOTS + POINTER_USAGE,
        "",
    ),
)


class Run:
    """What one scenario has built and seen so far."""

    def __init__(self, tmp_path: Path) -> None:
        self.tmp = tmp_path
        self.folder = tmp_path / "library"
        self.drawn: list[UmlLink] = []
        self.converted: Converted | None = None
        self.before: dict[str, bytes] = {}
        self.code: int | None = None
        self.error = ""


@pytest.fixture
def run(tmp_path: Path) -> Run:
    return Run(tmp_path)


def audits(run: Run) -> Path:
    return run.folder / AUDITS


@given(
    parsers.parse('a schema in which "{part}" depends on "{whole}" through "{slot}"'),
)
def a_dependent_class(run: Run, part: str, whole: str, slot: str) -> None:
    copy_toy(run.folder)
    text = audits(run).read_text(encoding="utf-8")
    assert f"  {part}:\n" in text, f"the toy has no class {part}"
    assert f"rp_dependent_on: {slot}" in text, f"the toy's {part} does not depend through {slot}"
    assert f"  {slot}:\n" in text, f"the toy has no slot {slot}"
    assert f"range: {whole}\n" in text, f"{slot} does not range over {whole}"


@given(
    parsers.parse(
        'a schema in which "{first}" depends on "{second}" and "{other}" depends on "{third}"'
    )
)
def a_cycle(run: Run, first: str, second: str, other: str, third: str) -> None:
    assert (first, second, other, third) == (
        "AuditResult",
        "AuditFinding",
        "AuditFinding",
        "AuditResult",
    ), "the step knows the result and finding pair only"
    copy_toy(run.folder)
    # The finding already depends on its result; the result now depends on the finding.
    edit(audits(run), POINTER_RANGE, "    slot_uri: lib:ofAudit\n    range: AuditFinding\n")


@given(parsers.parse('"{slot}" is {defect}'))
def the_pointer_is_defective(run: Run, slot: str, defect: str) -> None:
    assert slot == "of_audit", "the step knows the pointer of_audit only"
    chosen = next((d for d in DEFECTS if d.words == defect), None)
    assert chosen is not None, f"no defect named {defect!r}"
    edit(audits(run), chosen.old, chosen.new)
    if chosen.imports:
        edit(audits(run), IMPORTS, IMPORTS + chosen.imports)


@when("the developer generates the schema")
def generated(run: Run, capsys: pytest.CaptureFixture[str]) -> None:
    run.before = tree(run.folder)
    run.code, run.error = generate(run.folder / "pyproject.toml", capsys)


@then(parsers.parse('generation fails naming "{first}" and "{second}"'))
def fails_naming(run: Run, first: str, second: str) -> None:
    assert run.code == 1, f"expected exit 1, got {run.code}: {run.error}"
    assert first in run.error, f"{first} is not named in {run.error!r}"
    assert second in run.error, f"{second} is not named in {run.error!r}"


@then("no generated file changes")
def nothing_changed(run: Run) -> None:
    after = tree(run.folder)
    assert after == run.before, f"files changed: {sorted(set(after) ^ set(run.before))}"


# Scenario 12: the converter, a drawn model with an «own graph» composition to a generated class.

AUDIT, RESULT = 20, 21
MODULE = "app_library"


@given(
    parsers.parse(
        'a UML model in which "{whole}" is composed «own graph» of the generated class "{part}"'
    )
)
def an_own_graph_part(run: Run, whole: str, part: str) -> None:
    assert (whole, part) == ("Audit", "AuditResult"), "the step knows the audit and its result only"


@given(
    parsers.parse(
        'the association between them names the role "{role}" on the audit\'s end, exactly one'
    )
)
def the_whole_end_role(run: Run, role: str) -> None:
    assert role == "of_audit", "the step knows the role of_audit only"
    run.drawn.append(link(1, RESULT, AUDIT, target_role="lib:ofAudit", target_card="1"))


@when("the modeller converts the model")
def converted(run: Run) -> None:
    uml = model(
        klass(AUDIT, "lib:Audit"),
        klass(RESULT, "lib:AuditResult"),
        links=tuple(run.drawn),
        compositions=(composition(2, AUDIT, RESULT, own_graph=True, stereotype="own graph"),),
    )
    run.converted = convert(uml)


def converted_run(run: Run) -> Converted:
    assert run.converted is not None, "the model was not converted"
    return run.converted


@then(parsers.parse('"{part}" is a root that depends on "{whole}" through "{slot}"'))
def depends_through(run: Run, part: str, whole: str, slot: str) -> None:
    out = converted_run(run)
    assert out.problems == [], out.problem_texts()
    definition = out.klass(MODULE, part)
    assert definition.mixins == ["AggregateRoot"], f"{part} is not a root"
    assert definition.annotations["rp_dependent_on"].value == slot, (
        f"{part} does not depend on {slot}"
    )
    assert out.slot(MODULE, slot).range == whole, f"{slot} does not range over {whole}"


@then(parsers.parse('"{slot}" is required and holds one audit'))
def required_and_single(run: Run, slot: str) -> None:
    pointer = converted_run(run).slot(MODULE, slot)
    assert pointer.required is True, f"{slot} is not required"
    assert not pointer.multivalued, f"{slot} holds many"


@then(parsers.parse('"{whole}" has no slot listing its results'))
def no_listing(run: Run, whole: str) -> None:
    out = converted_run(run)
    held = out.klass(MODULE, whole).slots
    assert list(held) == [], f"{whole} holds slots {list(held)}"


@then("the generator accepts the converted schema")
def generator_accepts(run: Run) -> None:
    found = generator_problems(converted_run(run), run.tmp)
    assert found == [], f"the generator refused: {found}"
