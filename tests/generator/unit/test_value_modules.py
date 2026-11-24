"""Value modules (domain-values-and-fixes, #301): rows E1 to E14 of the error matrix, over scratch projects.

A module annotated ``module_kind: value`` holds never-stored domain values. Each row is a project
written to ``tmp_path``; the checks run as ``rp-generate`` runs them (boundary, hard, target kind).
"""

from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.schema.services.schema_structure import own_schemas
from rdf_persistence_generation.checks.boundary import (
    boundary_problems,
    derived_kind,
    kind_folder_problems,
    mixed_kind_problems,
)
from rdf_persistence_generation.checks.hard import hard_problems
from rdf_persistence_generation.generated.rp_generation import BoundaryRule, HardRule, TargetKind
from rdf_persistence_generation.problems import format_problem

VALUE_PACKAGE = "scratch.domain.generated.values"
HEADER = """id: https://example.org/ns/{name}
name: {name}
title: {name}
description: A scratch module.
prefixes: {{x: "https://example.org/ns/x#", linkml: "https://w3id.org/linkml/"}}
default_prefix: x
default_range: string
imports:
  - linkml:types
  - rdf_persistence/model/rp_core
  - rdf_persistence/model/rp_annotations
{imports}{annotations}
"""
VALUE_BODY = """enums:
  Status:
    title: Status
    description: A status.
    permissible_values:
      ok: {title: Ok, description: Fine., meaning: "x:Ok"}
classes:
  Finding:
    title: Finding
    description: A finding of a check.
    slots: [code]
  Check:
    title: Check
    description: The outcome of a check.
    slots: [status, findings]
slots:
  code:
    title: Code
    description: Code.
  status:
    title: Status
    description: Status.
    range: Status
  findings:
    title: Findings
    description: Findings.
    range: Finding
    multivalued: true
"""
TECH_BODY = """classes:
  Req:
    title: Req
    description: A request shape.
    slots: [needed]
slots:
  needed:
    title: Needed
    description: Needed.
"""
ROOT_CLASS = """  Thing:
    title: Thing
    description: A thing.
    mixins: [AggregateRoot, Described, Tracked]
    slots: [{slot}]
    annotations: {{rp_path: things, database: tenant}}
"""
STORED_SLOT = """  {slot}:
    title: Held
    description: Holds a value.
    range: {range}
{owned}"""
OWNED = "    annotations: {owned: 'true'}\n"


def module(
    name: str,
    kind: str | None,
    body: str,
    imports: tuple[str, ...] = (),
    python_package: str | None = None,
) -> str:
    notes = ([f"module_kind: {kind}"] if kind else []) + (
        [f"python_package: {python_package}"] if python_package else []
    )
    annotations = "annotations:\n" + "".join(f"  {n}\n" for n in notes) if notes else ""
    more = "".join(f"  - {i}\n" for i in imports)
    return HEADER.format(name=name, imports=more, annotations=annotations) + body


def write(folder: Path, name: str, text: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def stored_module(slot_range: str, imports: tuple[str, ...], owned: bool = False) -> str:
    """A domain module whose root holds one slot over ``slot_range``."""
    body = (
        "classes:\n"
        + ROOT_CLASS.format(slot="held")
        + "slots:\n"
        + STORED_SLOT.format(slot="held", range=slot_range, owned=OWNED if owned else "")
    )
    return module("dom", "domain", body, ("rdf_persistence/model/rp_collections", *imports))


def found(folder: Path, root: Path) -> list[str]:
    """Every boundary and hard problem of the target rooted at ``root``, formatted."""
    view = load_schema(root)
    return [
        format_problem(p) for p in [*boundary_problems(view, folder), *hard_problems(view, folder)]
    ]


def rule_lines(problems: list[str], rule: BoundaryRule | HardRule) -> list[str]:
    return [p for p in problems if f"[{rule.value}]" in p]


def test_e1_a_value_module_in_a_domain_target_has_no_problem(tmp_path: Path) -> None:
    """E1 and E11: value classes that are neither roots nor owned pass; the target is a domain one."""
    root = write(tmp_path, "val", module("val", "value", VALUE_BODY, python_package=VALUE_PACKAGE))
    problems = found(tmp_path, root)
    view = load_schema(root)
    assert problems == [], f"a value module was refused: {problems}"
    assert derived_kind(view, tmp_path) == TargetKind.DOMAIN, (
        "a value target is not a domain target"
    )
    assert kind_folder_problems(tmp_path, VALUE_PACKAGE, TargetKind.DOMAIN) == [], (
        "the domain folder was refused for a value module"
    )


@pytest.mark.parametrize(
    ("package", "refused"),
    [
        ("scratch.domain.generated.values", False),
        ("scratch.domain.generated", False),
        ("scratch.services.generated", True),
        ("scratch.adapters.generated", True),
        ("scratch.entrypoints.generated", True),
    ],
)
def test_e2_a_value_module_is_generated_into_the_domain_folder_only(
    tmp_path: Path, package: str, refused: bool
) -> None:
    root = write(tmp_path, "val", module("val", "value", VALUE_BODY, python_package=package))
    view = load_schema(root)
    kind = derived_kind(view, tmp_path)
    problems = [format_problem(p) for p in kind_folder_problems(tmp_path, package, kind, view)]
    assert bool(problems) is refused, f"{package}: {problems}"
    hinted = [p for p in problems if "a value module stays in domain" in p]
    assert len(hinted) == len(problems), (
        f"{package}: the refused rows lack the value hint: {problems}"
    )


def test_e2_the_value_hint_is_given_only_for_a_target_with_a_value_module(tmp_path: Path) -> None:
    root = write(tmp_path, "dom", module("dom", "domain", "classes: {}\n"))
    view = load_schema(root)
    problems = [
        format_problem(p)
        for p in kind_folder_problems(
            tmp_path, "scratch.services.generated", TargetKind.DOMAIN, view
        )
    ]
    assert len(problems) == 1, f"the domain target in services was not refused once: {problems}"
    assert "a value module stays in domain" not in problems[0], (
        f"a hint about a value module on a target with none: {problems}"
    )


@pytest.mark.parametrize("slot_range", ["Status", "string"], ids=["value-enum", "plain-string"])
def test_e3_e10_a_domain_module_imports_a_value_module_and_uses_its_enum(
    tmp_path: Path, slot_range: str
) -> None:
    """E3 and E10: the import is allowed and a stored slot over a value enum is a literal."""
    write(tmp_path, "val", module("val", "value", VALUE_BODY))
    root = write(tmp_path, "dom", stored_module(slot_range, ("val",)))
    problems = found(tmp_path, root)
    assert rule_lines(problems, BoundaryRule.MODULE_KIND) == [], f"import refused: {problems}"
    assert rule_lines(problems, BoundaryRule.REFERENCE) == [], (
        f"enum read as a reference: {problems}"
    )
    assert rule_lines(problems, BoundaryRule.OWNERSHIP) == [], (
        f"a value class needed an owner: {problems}"
    )


def test_e4_a_technical_module_imports_the_value_classes_it_does_not_regenerate(
    tmp_path: Path,
) -> None:
    """E4: the value module has its own folder and package; the technical target owns only its own module."""
    write(
        tmp_path / "values", "val", module("val", "value", VALUE_BODY, python_package=VALUE_PACKAGE)
    )
    body = """classes:
  Response:
    title: Response
    description: Checks answered.
    slots: [checks]
slots:
  checks:
    title: Checks
    description: Checks.
    range: Check
    multivalued: true
"""
    root = write(tmp_path / "tech", "tech", module("tech", "technical", body, ("../values/val",)))
    view = load_schema(root)
    problems = found(tmp_path / "tech", root)
    assert problems == [], f"a technical module holding a value class was refused: {problems}"
    assert [s.name for s in own_schemas(view, tmp_path / "tech")] == ["tech"], (
        "the value module was counted as the technical target's own"
    )


@pytest.mark.parametrize(
    ("kind", "extra"),
    [("technical", TECH_BODY), ("access", TECH_BODY)],
)
def test_e5_e6_a_value_module_importing_a_technical_or_access_module_is_refused(
    tmp_path: Path, kind: str, extra: str
) -> None:
    write(tmp_path, "other", module("other", kind, extra))
    root = write(tmp_path, "val", module("val", "value", VALUE_BODY, ("other",)))
    lines = rule_lines(found(tmp_path, root), BoundaryRule.MODULE_KIND)
    assert any(
        "val" in p and "other" in p and "value module" in p and f"a {kind} module" in p
        for p in lines
    ), f"the import of a {kind} module was not refused: {lines}"
    assert any("move the class into a value or domain module" in p for p in lines), (
        f"no hint to move the class: {lines}"
    )


def test_e5_a_value_module_holding_a_technical_class_is_refused(tmp_path: Path) -> None:
    write(tmp_path, "other", module("other", "technical", TECH_BODY))
    body = """classes:
  Holder:
    title: Holder
    description: Holds a request.
    slots: [req]
slots:
  req:
    title: Req
    description: A request.
    range: Req
"""
    root = write(tmp_path, "val", module("val", "value", body, ("other",)))
    lines = rule_lines(found(tmp_path, root), BoundaryRule.MODULE_KIND)
    assert any("Req" in p and "Holder" in p and "technical" in p for p in lines), (
        f"a value class held a technical one: {lines}"
    )


@pytest.mark.parametrize(
    ("mixins", "annotations", "named"),
    [
        ("[AggregateRoot, Described, Tracked]", "{rp_path: roots}", "Root"),
        ("[Described]", "{graph: meta}", "Root"),
        ("[Described]", "{}", None),
    ],
)
def test_e7_a_value_class_is_never_a_root(
    tmp_path: Path, mixins: str, annotations: str, named: str | None
) -> None:
    body = f"""classes:
  Root:
    title: Root
    description: A class that claims to be stored.
    mixins: {mixins}
    annotations: {annotations}
"""
    root = write(tmp_path, "val", module("val", "value", body))
    lines = rule_lines(found(tmp_path, root), BoundaryRule.MODULE_KIND)
    refused = [p for p in lines if "Root" in p and "value module" in p]
    assert bool(refused) is (named is not None), f"{mixins} {annotations}: {lines}"


@pytest.mark.parametrize("owned", [False, True])
@pytest.mark.parametrize("folder", ["", "values"])
def test_e8_e9_a_stored_class_never_holds_a_value_class(
    tmp_path: Path, owned: bool, folder: str
) -> None:
    """E8 same folder, E9 the value module in a folder of its own: one problem, never also a reference one."""
    write(
        tmp_path / folder,
        "val",
        module("val", "value", VALUE_BODY, python_package=VALUE_PACKAGE if folder else None),
    )
    imported = f"{folder}/val" if folder else "val"
    root = write(tmp_path, "dom", stored_module("Check", (imported,), owned=owned))
    problems = found(tmp_path, root)
    holding = [
        p for p in rule_lines(problems, BoundaryRule.MODULE_KIND) if "never holds a value" in p
    ]
    assert len(holding) == 1, f"the holding rule did not report once: {problems}"
    assert "Check" in holding[0], f"it does not name the held class: {holding}"
    assert "val" in holding[0], f"it does not name the value module: {holding}"
    assert rule_lines(problems, BoundaryRule.REFERENCE) == [], (
        f"the same slot was reported twice, as a reference too: {problems}"
    )


def test_e15_a_stored_slot_over_a_technical_class_is_reported_once_as_holding(
    tmp_path: Path,
) -> None:
    write(tmp_path, "other", module("other", "technical", TECH_BODY))
    root = write(tmp_path, "dom", stored_module("Req", ("other",)))
    problems = found(tmp_path, root)
    holding = [p for p in rule_lines(problems, BoundaryRule.MODULE_KIND) if "Req" in p]
    assert len(holding) == 1, f"the holding rule did not report once: {problems}"
    assert "only a technical module holds a technical class" in holding[0], (
        f"the reason is missing: {holding}"
    )
    assert rule_lines(problems, BoundaryRule.REFERENCE) == [], (
        f"the same slot was also reported as a reference: {problems}"
    )


@pytest.mark.parametrize(
    ("kind", "refused"),
    [("value", False), ("valeu", True), (None, True)],
)
def test_e11_e12_only_a_spelt_value_kind_exempts_the_class(
    tmp_path: Path, kind: str | None, refused: bool
) -> None:
    root = write(tmp_path, "val", module("val", kind, VALUE_BODY))
    problems = found(tmp_path, root)
    assert bool(rule_lines(problems, BoundaryRule.OWNERSHIP)) is refused, (
        f"{kind}: ownership problems {problems}"
    )
    assert bool(rule_lines(problems, HardRule.ANNOTATION)) is (kind == "valeu"), (
        f"{kind}: the kind value was not judged on its own: {problems}"
    )


PLAIN_CHILD = "    is_a: Finding\n"
ROOT_CHILD = (
    "    is_a: Finding\n    mixins: [AggregateRoot, Described, Tracked]\n"
    "    annotations: {rp_path: children, database: tenant}\n"
)
MIXING_ROOT = (
    "    mixins: [Finding, AggregateRoot, Described, Tracked]\n"
    "    annotations: {rp_path: children, database: tenant}\n"
)
PLAIN_MIXER = "    mixins: [Finding]\n"
PLAIN_CLASS = "    mixins: [Described]\n"


@pytest.mark.parametrize(
    ("lines", "unowned", "held"),
    [
        (PLAIN_CHILD, True, True),
        (ROOT_CHILD, False, True),
        (MIXING_ROOT, False, True),
        (PLAIN_MIXER, True, True),
        (PLAIN_CLASS, True, False),
    ],
    ids=["is-a-non-root", "root-is-a", "root-mixes-in", "non-root-mixes-in", "unrelated"],
)
def test_e13_a_stored_class_extending_a_value_class_is_refused(
    tmp_path: Path, lines: str, unowned: bool, held: bool
) -> None:
    """E13: a subclass of a value class, or a class mixing one in, is refused, a root too."""
    write(tmp_path, "val", module("val", "value", VALUE_BODY))
    body = f"""classes:
  Child:
    title: Child
    description: A stored class related to a value one.
{lines}"""
    root = write(
        tmp_path,
        "dom",
        module("dom", "domain", body, ("rdf_persistence/model/rp_collections", "val")),
    )
    problems = found(tmp_path, root)
    ownership = [p for p in rule_lines(problems, BoundaryRule.OWNERSHIP) if "Child" in p]
    assert bool(ownership) is unowned, f"{lines!r}: ownership {ownership}"
    holding = [
        p
        for p in rule_lines(problems, BoundaryRule.MODULE_KIND)
        if "Child" in p and "Finding" in p and "value module" in p
    ]
    assert bool(holding) is held, f"{lines!r}: holding {holding} in {problems}"


@pytest.mark.parametrize(
    ("other_kind", "mixed"),
    [("technical", True), ("domain", False), ("value", False)],
)
def test_e14_a_value_module_beside_a_technical_one_is_a_mixed_target(
    tmp_path: Path, other_kind: str, mixed: bool
) -> None:
    write(tmp_path, "val", module("val", "value", VALUE_BODY))
    root = write(tmp_path, "other", module("other", other_kind, TECH_BODY, ("val",)))
    view = load_schema(root)
    problems = [format_problem(p) for p in mixed_kind_problems(view, tmp_path)]
    assert bool(problems) is mixed, f"value beside {other_kind}: {problems}"
    assert derived_kind(view, tmp_path) == TargetKind.DOMAIN, (
        "a mix with a value module is technical"
    )
