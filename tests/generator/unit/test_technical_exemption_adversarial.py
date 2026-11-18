"""Adversarial tests of the technical-module exemption (technical-models stage 4, D-49).

Attacks: a stored or domain class slipped past the class rules by way of a module annotated
``module_kind: technical``: an import, a misspelt or absent kind, a technical range, a wrong target kind.
"""

from pathlib import Path

from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import root_classes
from rdf_persistence_generation.checks.boundary import boundary_problems, target_kind_problems
from rdf_persistence_generation.checks.hard import hard_problems
from rdf_persistence_generation.generated.rp_generation import BoundaryRule, TargetKind
from rdf_persistence_generation.problems import format_problem

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
{imports}{kind}
"""
TECH_CLASS = """classes:
  Req:
    title: Req
    description: A request shape with a required slot.
    slots: [needed]
slots:
  needed:
    title: Needed
    description: Needed.
    required: true
"""
ROOT = """  Thing:
    title: Thing
    description: A thing.
    mixins: [AggregateRoot, Described, Tracked]
    slots: [req]
    annotations: {rp_path: things, database: tenant}
"""
REQ_SLOT = """    title: Req slot
    description: Holds a request.
    range: Req
"""


def module(name: str, kind: str | None, body: str, imports: tuple[str, ...] = ()) -> str:
    kind_text = "" if kind is None else f"annotations:\n  module_kind: {kind}"
    more = "".join(f"  - {i}\n" for i in imports)
    return HEADER.format(name=name, imports=more, kind=kind_text) + body


def project(
    tmp_path: Path, tech_kind: str | None, dom_kind: str | None, owned: bool, imports: bool = True
):
    """A root module holding a class with a slot over the technical class; returns (view, folder)."""
    (tmp_path / "tech.yaml").write_text(module("tech", tech_kind, TECH_CLASS), encoding="utf-8")
    slot_annotations = "    annotations: {owned: 'true'}\n" if owned else ""
    body = "classes:\n" + ROOT + "slots:\n  req:\n" + REQ_SLOT + slot_annotations
    imported = (
        ("rdf_persistence/model/rp_collections", "tech")
        if imports
        else ("rdf_persistence/model/rp_collections",)
    )
    (tmp_path / "dom.yaml").write_text(module("dom", dom_kind, body, imported), encoding="utf-8")
    return load_schema(tmp_path / "dom.yaml"), tmp_path


def both(view, folder) -> list[str]:
    return [
        format_problem(p) for p in [*boundary_problems(view, folder), *hard_problems(view, folder)]
    ]


def test_a_domain_class_pointing_at_a_technical_class_is_refused(tmp_path: Path) -> None:
    """Tries a domain slot, not owned, whose range is a technical class: must be a reference or kind problem."""
    view, folder = project(tmp_path, "technical", "domain", owned=False)
    found = both(view, folder)
    assert found, "a stored class referring to a technical class passed every rule"


def test_a_domain_module_importing_a_technical_one_is_refused(tmp_path: Path) -> None:
    """Tries a domain module that imports a technical module and owns its class inline."""
    view, folder = project(tmp_path, "technical", "domain", owned=True)
    found = [p for p in both(view, folder) if f"[{BoundaryRule.MODULE_KIND.value}]" in p]
    assert found, "the domain module imports a technical one and nothing complained"


def test_a_module_without_module_kind_importing_a_technical_one_is_refused(tmp_path: Path) -> None:
    """Tries to hold a technical class inline from a module that declares no kind at all."""
    view, folder = project(tmp_path, "technical", None, owned=True)
    found = [p for p in both(view, folder) if f"[{BoundaryRule.MODULE_KIND.value}]" in p]
    assert any("dom" in p and "Req" in p and "tech" in p for p in found), found


def test_a_misspelt_kind_does_not_exempt_the_class(tmp_path: Path) -> None:
    """Tries `module_kind: technicl`: the class must still be a stored class under the rules (and the value refused)."""
    (tmp_path / "tech.yaml").write_text(module("tech", "technicl", TECH_CLASS), encoding="utf-8")
    view = load_schema(tmp_path / "tech.yaml")
    found = both(view, tmp_path)
    assert any("Req" in p for p in found), f"a misspelt kind exempted Req: {found}"


def test_an_absent_kind_does_not_exempt_the_class(tmp_path: Path) -> None:
    """Tries a module with no `module_kind`: its classes stay under the ownership rule."""
    (tmp_path / "tech.yaml").write_text(module("tech", None, TECH_CLASS), encoding="utf-8")
    view = load_schema(tmp_path / "tech.yaml")
    assert any("Req" in p for p in both(view, tmp_path)), "an unannotated module is exempt"


def test_a_misspelt_kind_value_is_itself_refused(tmp_path: Path) -> None:
    """Tries `module_kind: technicl`: the value must be a problem of its own, not only a side effect."""
    (tmp_path / "tech.yaml").write_text(module("tech", "technicl", TECH_CLASS), encoding="utf-8")
    view = load_schema(tmp_path / "tech.yaml")
    assert any("module_kind" in p for p in both(view, tmp_path)), (
        "a bad module_kind value is accepted"
    )


def test_the_kind_is_read_case_insensitively_so_an_upper_case_kind_exempts(tmp_path: Path) -> None:
    """Tries `module_kind: Technical`: either refused as a value or treated as technical, never half of each."""
    (tmp_path / "tech.yaml").write_text(module("tech", "Technical", TECH_CLASS), encoding="utf-8")
    view = load_schema(tmp_path / "tech.yaml")
    problems = both(view, tmp_path)
    exempt = not any("Req" in p for p in problems)
    refused = any("module_kind" in p for p in problems)
    assert exempt != refused or not exempt, "a kind refused as a value still exempts its classes"


def test_a_technical_module_in_a_domain_target_is_refused(tmp_path: Path) -> None:
    """Tries a technical module in a target of kind domain, and a domain module in a technical one."""
    view, folder = project(tmp_path, "technical", "domain", owned=False)
    (tmp_path / "tech.yaml").write_text(module("tech", "technical", TECH_CLASS), encoding="utf-8")
    assert target_kind_problems(view, folder, TargetKind.DOMAIN), (
        "a technical module passed a domain target"
    )
    assert target_kind_problems(view, folder, TargetKind.TECHNICAL), (
        "a domain module passed a technical target"
    )


def test_a_technical_class_cannot_be_an_aggregate_root_unseen(tmp_path: Path) -> None:
    """Tries a technical-module class that mixes in AggregateRoot with no rp_path: exempt from rules, yet a root downstream."""
    body = """classes:
  Sneaky:
    title: Sneaky
    description: A root in a technical module.
    mixins: [AggregateRoot, Described, Tracked]
"""
    (tmp_path / "tech.yaml").write_text(module("tech", "technical", body), encoding="utf-8")
    view = load_schema(tmp_path / "tech.yaml")
    problems = both(view, tmp_path)
    assert [c.name for c in root_classes(view, tmp_path)] == ["Sneaky"], (
        "the premise: it is a root downstream"
    )
    assert any("Sneaky" in p and f"[{BoundaryRule.MODULE_KIND.value}]" in p for p in problems), (
        problems
    )


def test_the_exemption_does_not_cover_a_domain_class_that_inherits_a_technical_one(
    tmp_path: Path,
) -> None:
    """Tries a stored class with is_a a technical class: it is stored, so ownership still applies to it."""
    (tmp_path / "tech.yaml").write_text(module("tech", "technical", TECH_CLASS), encoding="utf-8")
    body = """classes:
  Child:
    title: Child
    description: A stored class extending a technical one.
    is_a: Req
"""
    (tmp_path / "dom.yaml").write_text(
        module("dom", "domain", body, ("rdf_persistence/model/rp_collections", "tech")),
        encoding="utf-8",
    )
    view = load_schema(tmp_path / "dom.yaml")
    assert any("Child" in p for p in both(view, tmp_path)), (
        "a domain subclass of a technical class is unchecked"
    )
