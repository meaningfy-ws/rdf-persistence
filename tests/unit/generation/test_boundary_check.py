"""The boundary check (task 1.7, PD-23): ownership of the aggregate's parts and module kinds."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.generation import steps
from rdf_persistence.generation.checks.boundary import boundary_problems
from rdf_persistence.generation.cli import main
from rdf_persistence.generation.generated.rp_generation import BoundaryRule, GenerationTarget
from rdf_persistence.generation.pipeline import generate
from rdf_persistence.generation.problems import format_problem
from rdf_persistence.services.schema import load_schema

from .conftest import ROOT_SCHEMA, Breaker

MODEL_DIR = Path(__file__).parents[3] / "rdf_persistence"
METAMODEL = MODEL_DIR / "model" / "rp.yaml"
GENERATION_MODEL = MODEL_DIR / "generation" / "model" / "rp_generation.yaml"

NOTES_OWNED = "    range: Note\n    multivalued: true\n    inlined_as_list: true\n    annotations:\n      owned: true\n"
NOTES_REFERENCED = "    range: Note\n    multivalued: true\n    inlined_as_list: true\n"
BOOK_SLOTS = "slots: [isbn, authors, published, genre, chapters, shelf, sequel_of]"
BOOK_IMPORTS = "  - rdf_persistence/model/rp_collections\nannotations:\n  module_kind: domain"
ACCESS_IMPORT = "  - rdf_persistence/model/rp_collections\n  - library_access\nannotations:\n  module_kind: domain"
TENANCY_IMPORT = "  - rdf_persistence/model/rp_collections\n  - rdf_persistence/model/rp_tenancy\nannotations:\n  module_kind: domain"


def problems_of(root: Path) -> list[str]:
    return [format_problem(p) for p in boundary_problems(load_schema(root), root.parent)]


@dataclass(frozen=True)
class Edit:
    """Replace the first ``old`` by ``new`` in ``module``."""

    module: str
    old: str
    new: str


@dataclass(frozen=True)
class Fault:
    """Planted edits; ``rule`` must name ``element`` and every word of ``mentions``."""

    rule: BoundaryRule
    edits: tuple[Edit, ...]
    element: str
    mentions: tuple[str, ...] = ()


FAULTS = (
    Fault(BoundaryRule.OWNERSHIP, (Edit("books.yaml", NOTES_OWNED, NOTES_REFERENCED),), "Note"),
    Fault(
        BoundaryRule.REFERENCE,
        (Edit("books.yaml", NOTES_OWNED, NOTES_REFERENCED),),
        "notes",
        ("Note",),
    ),
    Fault(
        BoundaryRule.OWNERSHIP,
        (
            Edit(
                "books.yaml",
                BOOK_SLOTS,
                "slots: [isbn, authors, published, genre, shelf, sequel_of]",
            ),
        ),
        "Chapter",
    ),
    Fault(
        BoundaryRule.OWNERSHIP,
        (Edit("library_tenant.yaml", "      graph: meta\n", ""),),
        "Library",
    ),
    Fault(
        BoundaryRule.REFERENCE,
        (Edit("scans.yaml", "range: Book", "range: Chapter"),),
        "scan_of",
        ("Chapter",),
    ),
    Fault(
        BoundaryRule.MODULE_KIND,
        (Edit("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT),),
        "books",
        ("library_access", "access"),
    ),
    Fault(
        BoundaryRule.MODULE_KIND,
        (Edit("books.yaml", BOOK_IMPORTS, TENANCY_IMPORT),),
        "books",
        ("rp_tenancy",),
    ),
    Fault(
        BoundaryRule.MODULE_KIND,
        (
            Edit("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT),
            Edit("library_access.yaml", "module_kind: access", "module_kind: technical"),
        ),
        "books",
        ("library_access", "technical"),
    ),
)

PASSING = (
    pytest.param((Edit("scans.yaml", "range: Book", "range: Principal"),), id="reference-by-iri"),
    pytest.param(
        (Edit("scans.yaml", "slots: [scan_of]", "slots: [scan_of, chapters]"),),
        id="owned-by-two-roots",
    ),
)


def plant(break_toy: Breaker, edits: tuple[Edit, ...]) -> Path:
    root = break_toy(*(edits[0].module, edits[0].old, edits[0].new))
    for edit in edits[1:]:
        root = break_toy(edit.module, edit.old, edit.new)
    return root


def test_the_toy_library_passes(toy_copy: Path) -> None:
    assert problems_of(toy_copy / ROOT_SCHEMA) == [], "the toy library must pass its boundary check"


@pytest.mark.parametrize("root", [METAMODEL, GENERATION_MODEL], ids=["metamodel", "generation"])
def test_the_toolkits_own_schemas_pass(root: Path) -> None:
    assert problems_of(root) == [], f"{root.name} must pass the boundary check"


@pytest.mark.parametrize("fault", FAULTS, ids=lambda f: f"{f.rule}-{f.element}-{len(f.edits)}")
def test_a_planted_fault_is_reported_with_its_rule_and_element(
    break_toy: Breaker, fault: Fault
) -> None:
    problems = problems_of(plant(break_toy, fault.edits))
    expected = f"[{fault.rule.value}] {fault.element}:"
    matching = [p for p in problems if expected in p]
    assert matching, f"{expected!r} not in {problems}"
    for word in fault.mentions:
        assert any(word in p for p in matching), f"{word!r} is not named in {matching}"


@pytest.mark.parametrize("edits", PASSING)
def test_an_allowed_variant_passes(break_toy: Breaker, edits: tuple[Edit, ...]) -> None:
    assert problems_of(plant(break_toy, edits)) == [], "this variant is allowed"


def test_every_rule_has_a_row_in_the_table() -> None:
    assert {f.rule for f in FAULTS} == set(BoundaryRule), "a boundary rule has no planted fault"


@pytest.mark.slow
def test_a_domain_module_importing_the_access_module_names_both_modules(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT)
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.generated")
    found = generate([target], root.parent, (steps.BOUNDARY_STEP,), check=True)
    assert len(found) == 1, f"one bad import, one line: {found}"
    line = format_problem(found[0])
    assert "books" in line, "the importing module is not named"
    assert "library_access" in line, "the imported module is not named"
    before = sorted(p.name for p in root.parent.iterdir())
    assert main(["--project", str(root.parent / "pyproject.toml")]) == 1, "wrong exit code"
    assert "library_access" in capsys.readouterr().err, "the CLI does not name the imported module"
    assert sorted(p.name for p in root.parent.iterdir()) == before, "outputs were touched"


def test_check_mode_runs_the_boundary_check(break_toy: Breaker) -> None:
    root = break_toy("books.yaml", NOTES_OWNED, NOTES_REFERENCED)
    assert main(["--project", str(root.parent / "pyproject.toml"), "--check"]) == 1, (
        "--check skipped the boundary check"
    )


API_MODULE = """id: https://example.org/ns/library/api
name: api
title: API module
description: The request and response shapes of the library's own routes.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
annotations:
  module_kind: {kind}

classes:
  Account:
    title: Account
    description: What a route answers about an account; never stored.
    class_uri: lib:Account
    attributes:
      account_id:
        title: Account id
        description: The identifier of the account.
        identifier: true
      active:
        title: Active
        description: Whether the account may sign in.
        range: boolean
"""


def add_api_module(toy: Path, kind: str) -> Path:
    """Write ``api.yaml`` of the given kind into the toy and import it from the root schema."""
    (toy / "api.yaml").write_text(API_MODULE.format(kind=kind), encoding="utf-8")
    root = toy / ROOT_SCHEMA
    text = root.read_text(encoding="utf-8")
    root.write_text(
        text.replace("  - library_access\n", "  - library_access\n  - api\n", 1), encoding="utf-8"
    )
    return root


@pytest.mark.slow
def test_a_class_of_a_technical_module_needs_no_owning_root(toy_copy: Path) -> None:
    add_api_module(toy_copy, "technical")
    assert main(["--project", str(toy_copy / "pyproject.toml")]) == 0, "rp-generate must succeed"
    generated = toy_copy / "generated"
    ts = toy_copy / "web" / "src" / "domain" / "generated" / "api.ts"
    py = next(generated.rglob("api.py"))
    assert "export interface Account " in ts.read_text(encoding="utf-8"), "Account is not in api.ts"
    assert "class Account(" in py.read_text(encoding="utf-8"), "Account is not in api.py"


@pytest.mark.parametrize("kind", ["domain", "access"])
def test_a_class_of_a_domain_or_access_module_still_needs_an_owning_root(
    toy_copy: Path, kind: str
) -> None:
    root = add_api_module(toy_copy, kind)
    assert "[ownership] Account: is neither an aggregate root nor owned by any root" in problems_of(
        root
    ), f"a {kind} class that nothing owns must still be refused"


def test_a_domain_class_owned_only_by_a_technical_class_is_refused(toy_copy: Path) -> None:
    holder = API_MODULE.format(kind="technical").replace(
        "imports:\n  - linkml:types\n", "imports:\n  - linkml:types\n  - lost\n"
    ) + (
        "  Holder:\n    title: Holder\n    description: A request shape.\n    attributes:\n"
        "      holder_id:\n        description: Id.\n        identifier: true\n"
        "      part:\n        description: Owns a part.\n        range: Orphan\n"
        "        annotations:\n          owned: true\n"
    )
    (toy_copy / "api.yaml").write_text(holder, encoding="utf-8")
    (toy_copy / "lost.yaml").write_text(
        API_MODULE.format(kind="domain")
        .replace("Account", "Orphan")
        .replace("account_id", "orphan_id")
        .replace("api\n", "lost\n", 1)
        .replace("/api\n", "/lost\n", 1),
        encoding="utf-8",
    )
    root = toy_copy / ROOT_SCHEMA
    text = root.read_text(encoding="utf-8")
    root.write_text(text.replace("  - library_access\n", "  - library_access\n  - api\n", 1))
    assert "[ownership] Orphan: is neither an aggregate root nor owned by any root" in problems_of(
        root
    ), "a technical class is never stored, so what it owns is not owned"


TERMS_MODULE = """id: https://example.org/ns/library/terms
name: terms
title: Terms module
description: A page of terms, shaped for a route.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
annotations:
  module_kind: technical

classes:
  Term:
    title: Term
    description: One term of a page.
    class_uri: lib:Term
    attributes:
      label:
        title: Label
        description: The term's label.
        identifier: true
  Terms:
    title: Terms
    description: A page of terms.
    class_uri: lib:Terms
    attributes:
      items:
        title: Items
        description: The terms of this page.
        range: Term
        multivalued: true
        inlined_as_list: true
{extra}"""


def add_terms_module(toy: Path, extra: str) -> Path:
    """Write ``terms.yaml`` (a technical module) into the toy and import it from the root schema."""
    (toy / "terms.yaml").write_text(TERMS_MODULE.format(extra=extra), encoding="utf-8")
    root = toy / ROOT_SCHEMA
    text = root.read_text(encoding="utf-8")
    assert "  - library_access\n" in text, "the toy root schema no longer imports library_access"
    root.write_text(
        text.replace("  - library_access\n", "  - library_access\n  - terms\n", 1), encoding="utf-8"
    )
    return root


def test_the_reference_problem_names_its_fixes(toy_copy: Path) -> None:
    found = [p for p in problems_of(add_terms_module(toy_copy, "")) if "[reference]" in p]
    assert len(found) == 1, f"one not-owned slot, one reference problem: {found}"
    for fix in (
        "owned: true",
        "Term inline",
        "make Term an aggregate root",
        "point the slot at a root, Principal or Activity",
    ):
        assert fix in found[0], f"{fix!r} is not named in {found[0]}"


def test_an_owned_slot_of_a_technical_module_has_no_reference_problem(toy_copy: Path) -> None:
    owned = "        annotations:\n          owned: true\n"
    found = [p for p in problems_of(add_terms_module(toy_copy, owned)) if "[reference]" in p]
    assert found == [], "an owned slot is held inline"
