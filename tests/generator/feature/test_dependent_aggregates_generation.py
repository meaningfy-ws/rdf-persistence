"""Steps of ``dependent_aggregates_generation.feature``: a bad dependent class is refused (dependent-aggregates PD-12, PD-14).

Each scenario copies the toy library, breaks its ``audits`` module in one way and calls ``cli.main``
there, as the command line does. The toy's own ``AuditResult`` is the dependent class under attack.
"""

from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

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
        self.folder = tmp_path / "library"
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
