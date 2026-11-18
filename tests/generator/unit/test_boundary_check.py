"""The boundary check (task 1.7, PD-23): ownership of the aggregate's parts and module kinds."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation import steps
from rdf_persistence_generation.checks.boundary import (
    boundary_problems,
    kind_folder_problems,
    target_kind_problems,
)
from rdf_persistence_generation.cli import main
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.generated.rp_generation import (
    BoundaryRule,
    GenerationTarget,
    TargetKind,
)
from rdf_persistence_generation.pipeline import generate
from rdf_persistence_generation.problems import format_problem

from .conftest import ROOT_SCHEMA, TOY, Breaker

MODEL_DIR = Path(__file__).parents[3] / "rdf_persistence"
METAMODEL = MODEL_DIR / "model" / "rp.yaml"
GENERATION_MODEL = MODEL_DIR.parent / "rdf_persistence_generation" / "model" / "rp_generation.yaml"

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


BOOK_ISBN_SLOT = "slots:\n  isbn:\n"
WITH_ACTIVITIES = "  - rdf_persistence/model/rp_collections\n  - books_activities\nannotations:\n  module_kind: domain"
REVIEW_ROOT = """  Review:
    title: Review
    description: A review of a book kept as a root that is also an activity.
    class_uri: lib:Review
    is_a: Activity
    mixins: [AggregateRoot, Described, Tracked]
    annotations:
      rp_path: reviews
      database: tenant
slots:
"""


def book_slot_over(name: str, range_: str, *, imports_activities: bool) -> tuple[Edit, ...]:
    """Edits that give ``Book`` the slot ``name`` with the range ``range_``; the book module imports the activities one if asked."""
    slot = (
        f"slots:\n  {name}:\n    title: {name}\n    description: A planted slot.\n"
        f"    slot_uri: lib:{name}\n    range: {range_}\n  isbn:\n"
    )
    edits = (
        Edit("books.yaml", BOOK_SLOTS, BOOK_SLOTS.replace("sequel_of]", f"sequel_of, {name}]")),
        Edit("books.yaml", BOOK_ISBN_SLOT, slot),
    )
    imports = (Edit("books.yaml", BOOK_IMPORTS, WITH_ACTIVITIES),) if imports_activities else ()
    return (*imports, *edits)


FAULTS = (
    Fault(
        BoundaryRule.ACTIVITY_DIRECTION,  # TC-101: the stored model refers to a use case
        book_slot_over("last_shelving", "ShelveBooks", imports_activities=True),
        "last_shelving",
        ("Book", "ShelveBooks"),
    ),
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
    pytest.param(  # TC-102: a toolkit activity class may be referred to (was_generated_by)
        book_slot_over("made_by", "Activity", imports_activities=False), id="toolkit-activity"
    ),
    pytest.param(  # TC-102: and the workflow activity
        book_slot_over("last_move", "Transition", imports_activities=True), id="toolkit-transition"
    ),
    pytest.param(  # TC-102: so may an aggregate root that is also an activity
        (
            *book_slot_over("last_review", "Review", imports_activities=True),
            Edit("books_activities.yaml", "slots:\n", REVIEW_ROOT),
        ),
        id="activity-root",
    ),
)


def plant(break_toy: Breaker, edits: tuple[Edit, ...]) -> Path:
    root = break_toy(*(edits[0].module, edits[0].old, edits[0].new))
    for edit in edits[1:]:
        root = break_toy(edit.module, edit.old, edit.new)
    return root


def test_the_toy_library_passes(toy_copy: Path) -> None:
    assert problems_of(toy_copy / ROOT_SCHEMA) == [], "the toy library must pass its boundary check"


@pytest.mark.parametrize("name", ["ApproveBook", "ShelveBooks", "Activity", "Transition"])
@pytest.mark.slow
def test_the_toy_generates_a_frame_for_each_activity_class(generated_toy: Path, name: str) -> None:
    """TC-100: the activities module generates, and each activity class gets its frame."""
    assert (generated_toy / f"{name}.frame.jsonld").is_file(), f"no frame for {name}"


def test_the_stored_module_does_not_import_the_activities_module() -> None:
    """P-0001: the static module never imports the activities one."""
    books = (TOY / "books.yaml").read_text(encoding="utf-8")
    assert "books_activities" not in books, "books.yaml must not import its activities module"


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
    # target_kind needs a declared kind, which a planted edit cannot give: tested below by its own cases
    rules = set(BoundaryRule) - {BoundaryRule.TARGET_KIND}
    assert {f.rule for f in FAULTS} == rules, "a boundary rule has no planted fault"


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


def test_a_class_slot_of_a_technical_module_has_no_reference_problem(toy_copy: Path) -> None:
    """D-49: a technical class is never stored, so `Terms.items` ranging over `Term` is no reference."""
    found = [p for p in problems_of(add_terms_module(toy_copy, "")) if "[reference]" in p]
    assert found == [], "the reference rule applies to stored classes only"


def test_the_reference_problem_names_its_fixes(toy_copy: Path) -> None:
    root = add_terms_module(toy_copy, "")
    terms = toy_copy / "terms.yaml"
    terms.write_text(
        terms.read_text(encoding="utf-8").replace("module_kind: technical", "module_kind: domain"),
        encoding="utf-8",
    )
    found = [p for p in problems_of(root) if "[reference]" in p]
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


SIDE_IMPORTS = "imports:\n  - linkml:types\n  - side\n"


def kind_folder(tmp_path: Path, side_kind: str | None) -> Path:
    """A folder with a technical ``api`` module, and a ``side`` module of ``side_kind`` it imports when given."""
    api = API_MODULE.format(kind="technical")
    if side_kind is not None:
        api = api.replace("imports:\n  - linkml:types\n", SIDE_IMPORTS, 1)
        side = (
            API_MODULE.format(kind=side_kind)
            .replace("Account", "Member")
            .replace("account_id", "member_id")
            .replace("/api\n", "/side\n", 1)
            .replace("name: api", "name: side", 1)
        )
        (tmp_path / "side.yaml").write_text(side, encoding="utf-8")
    (tmp_path / "api.yaml").write_text(api, encoding="utf-8")
    return tmp_path


def kind_problems_of(folder: Path, kind: TargetKind) -> list[str]:
    view = load_schema(folder / "api.yaml")
    return [format_problem(p) for p in target_kind_problems(view, folder, kind)]


def test_a_technical_target_whose_only_module_is_technical_has_no_problem(tmp_path: Path) -> None:
    folder = kind_folder(tmp_path, None)
    assert kind_problems_of(folder, TargetKind.TECHNICAL) == [], "a technical module fits"


def test_a_technical_target_refuses_a_domain_module_naming_it(tmp_path: Path) -> None:
    folder = kind_folder(tmp_path, "domain")
    found = kind_problems_of(folder, TargetKind.TECHNICAL)
    assert len(found) == 1, f"one domain module, one problem: {found}"
    assert found[0].startswith("[target_kind] side"), f"rule and module not named: {found[0]}"


def test_a_domain_target_refuses_a_technical_module_naming_it(tmp_path: Path) -> None:
    folder = kind_folder(tmp_path, "domain")
    found = kind_problems_of(folder, TargetKind.DOMAIN)
    assert len(found) == 1, f"one technical module, one problem: {found}"
    assert found[0].startswith("[target_kind] api"), f"rule and module not named: {found[0]}"


def test_the_boundary_step_checks_the_kind_of_its_target(toy_copy: Path) -> None:
    target = GenerationTarget(
        schema_file=ROOT_SCHEMA, package="app.generated", target_kind=TargetKind.TECHNICAL
    )
    found = generate([target], toy_copy, (steps.BOUNDARY_STEP,), check=True)
    assert found, "the toy's domain modules must fail a technical target"
    assert {p.rule for p in found} == {BoundaryRule.TARGET_KIND.value}, f"{found}"


def test_a_technical_target_refuses_an_access_module_naming_it(tmp_path: Path) -> None:
    """Row 1: a module of kind access is not technical, so a technical target refuses it."""
    found = kind_problems_of(kind_folder(tmp_path, "access"), TargetKind.TECHNICAL)
    assert len(found) == 1, found
    assert found[0].startswith("[target_kind] side"), found


KIND_HEAD = '[tool.rp-generate]\nschema = "library.yaml"\npackage = "tests.fixtures.library.generated"\npython = "generated"\n'


def files_of(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


def declare_kind(toy: Path, kind: str) -> Path:
    project = toy / "pyproject.toml"
    project.write_text(f'{KIND_HEAD}kind = "{kind}"\n', encoding="utf-8")
    return project


def test_a_technical_target_over_domain_modules_fails_naming_target_and_module_and_writes_nothing(
    toy_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Row 1: probe of PD-9; the whole run is refused, no generated file, manifest or staging is left."""
    project = declare_kind(toy_copy, "technical")
    before = files_of(toy_copy)
    code = main(["--project", str(project)])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code != 0, "a technical target over domain modules must fail"
    assert BoundaryRule.TARGET_KIND.value in text, f"the rule is not named: {text}"
    assert ROOT_SCHEMA in text, f"the target (its schema) is not named: {text}"
    assert "books" in text, f"the module is not named: {text}"
    assert files_of(toy_copy) == before, "a failed run wrote a file"
    assert not (toy_copy / "generated").exists(), "the output folder was created"
    assert [p.name for p in toy_copy.iterdir() if p.name.startswith(".rp-generate")] == [], (
        "a staging folder is left behind"
    )


def test_a_domain_target_holding_a_technical_module_fails_naming_it_and_writes_nothing(
    toy_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Row 2: probe of PD-9; a technical module in a domain target."""
    add_api_module(toy_copy, "technical")
    project = declare_kind(toy_copy, "domain")
    before = files_of(toy_copy)
    code = main(["--project", str(project)])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code != 0, "a domain target holding a technical module must fail"
    assert f"[{BoundaryRule.TARGET_KIND.value}] api" in text, f"rule and module not named: {text}"
    assert files_of(toy_copy) == before, "a failed run wrote a file"


# --- kind and folder (PD-4, DEC-3): the toolkit's own run only --------------------------------------

REPO = MODEL_DIR.parent
SERVICE_SCHEMA = "rdf_persistence/model/technical/api/rp_api_entrypoints.yaml"
TOOLKIT_FOLDER = REPO / Path(SERVICE_SCHEMA).parent


def folder_problems_of(folder: Path, package: str, kind: TargetKind | None) -> list[str]:
    return [format_problem(p) for p in kind_folder_problems(folder, package, kind)]


@pytest.mark.parametrize(
    ("kind", "package"),
    [
        (TargetKind.DOMAIN, "x.core.domain.generated"),  # TC-13
        (TargetKind.TECHNICAL, "x.access.services.generated"),
        (TargetKind.TECHNICAL, "x.access.adapters.generated.wire"),  # a group after generated
        (TargetKind.TECHNICAL, "x.access.entrypoints.generated"),
    ],
)
def test_a_toolkit_target_in_the_folder_its_kind_allows_has_no_problem(
    kind: TargetKind, package: str
) -> None:
    assert folder_problems_of(TOOLKIT_FOLDER, package, kind) == [], "the folder fits the kind"


@pytest.mark.parametrize(
    ("kind", "package"),
    [
        (TargetKind.TECHNICAL, "x.access.domain.generated"),  # TC-14
        (TargetKind.DOMAIN, "x.access.adapters.generated"),  # TC-15
        (TargetKind.DOMAIN, "x.access.services.generated.service"),
    ],
)
def test_a_toolkit_target_in_the_wrong_folder_is_named_with_its_package(
    kind: TargetKind, package: str
) -> None:
    found = folder_problems_of(TOOLKIT_FOLDER, package, kind)
    assert len(found) == 1, f"one target, one problem: {found}"
    assert found[0].startswith(f"[target_kind] {package}:"), f"rule and package not named: {found}"
    assert kind.value in found[0], f"the kind is not named: {found}"


def test_a_toolkit_target_without_a_generated_segment_is_refused() -> None:
    found = folder_problems_of(TOOLKIT_FOLDER, "x.access.domain", TargetKind.DOMAIN)
    assert len(found) == 1, f"one target, one problem: {found}"
    assert "generated" in found[0], f"the missing segment is not named: {found}"


@pytest.mark.parametrize(
    "package", ["rdf_persistence.testkit.generated", "rdf_persistence_generation.generated"]
)
def test_the_testkit_and_the_generator_packages_are_exempt(package: str) -> None:
    """TC-72: they sit outside the themes."""
    assert folder_problems_of(TOOLKIT_FOLDER, package, TargetKind.TECHNICAL) == []


@pytest.mark.parametrize(
    "package",
    [
        "rdf_persistence.testkitx.domain.generated",
        "rdf_persistence.testkit_extra.access.domain.generated",
        "rdf_persistence_generationx.access.domain.generated",
        "rdf_persistence_generation_extra.domain.generated",
    ],
)
def test_a_package_that_only_starts_like_an_exempt_one_is_not_exempt(package: str) -> None:
    """The exemption matches whole segments: ``rdf_persistence.testkitx`` is not the testkit."""
    assert len(folder_problems_of(TOOLKIT_FOLDER, package, TargetKind.TECHNICAL)) == 1, package


def test_a_consumer_run_keeps_its_own_folder_layout() -> None:
    """TC-16: a consumer's ``app.generated`` passes, kind or not."""
    assert folder_problems_of(TOY, "app.generated", TargetKind.TECHNICAL) == [], "consumer run"
    assert folder_problems_of(TOOLKIT_FOLDER, "app.generated", None) == [], "no kind declared"


def toolkit_target(kind: TargetKind, package: str) -> GenerationTarget:
    return GenerationTarget(schema_file=SERVICE_SCHEMA, package=package, target_kind=kind)


@pytest.mark.slow
def test_the_boundary_step_passes_the_old_layout_package_of_a_technical_target() -> None:
    """TC-72, first half: a technical target in a theme's ``generated`` folder (``make generate`` covers the rest)."""
    target = toolkit_target(TargetKind.TECHNICAL, "rdf_persistence.api.entrypoints.generated")
    assert generate([target], REPO, (steps.BOUNDARY_STEP,), check=True) == []


PYPROJECT = REPO / "pyproject.toml"
ACCESS_SERVICES_SCHEMA = "rdf_persistence/model/technical/access/rp_access_services.yaml"
WRONG_FOLDER = "rdf_persistence.access.domain.generated"


def toolkit_targets_from(project: Path) -> list[GenerationTarget]:
    return [t for t in read_targets(project) if t.schema_file.startswith("rdf_persistence/")]


@pytest.mark.slow
def test_the_toolkit_targets_pass_the_boundary_step_on_the_theme_layout(tmp_path: Path) -> None:
    """TC-73, first half: every target of the toolkit's own ``pyproject.toml``, read from a copy."""
    (tmp_path / "pyproject.toml").write_text(
        PYPROJECT.read_text(encoding="utf-8"), encoding="utf-8"
    )
    targets = toolkit_targets_from(tmp_path / "pyproject.toml")

    assert len(targets) > 10, "the toolkit's own targets were read"
    assert generate(targets, REPO, (steps.BOUNDARY_STEP,), check=True) == []


@pytest.mark.slow
def test_the_boundary_step_names_the_target_whose_package_is_edited_to_a_domain_folder(
    tmp_path: Path,
) -> None:
    """TC-73, second half: one technical target's package edited, on a copy of ``pyproject.toml``."""
    text = PYPROJECT.read_text(encoding="utf-8")
    block = f'schema = "{ACCESS_SERVICES_SCHEMA}"\npackage = "rdf_persistence.access.services.generated"'
    assert block in text, "the access services target is in pyproject.toml"
    (tmp_path / "pyproject.toml").write_text(
        text.replace(
            block, block.replace("rdf_persistence.access.services.generated", WRONG_FOLDER)
        ),
        encoding="utf-8",
    )

    found = generate(
        toolkit_targets_from(tmp_path / "pyproject.toml"), REPO, (steps.BOUNDARY_STEP,), check=True
    )

    assert [(p.rule, p.element) for p in found] == [(BoundaryRule.TARGET_KIND.value, WRONG_FOLDER)]
    assert PYPROJECT.read_text(encoding="utf-8") == text, "the real pyproject.toml is untouched"


@pytest.mark.slow
def test_the_boundary_step_refuses_a_technical_target_in_a_domain_folder_naming_it() -> None:
    """TC-72, second half: the check is wired into the step."""
    # TC-72 names the old service package under domain, which test_technical_split bans as a literal
    package = "rdf_persistence.core.domain.generated.rp_service"
    found = generate(
        [toolkit_target(TargetKind.TECHNICAL, package)], REPO, (steps.BOUNDARY_STEP,), check=True
    )
    assert [(p.rule, p.element) for p in found] == [(BoundaryRule.TARGET_KIND.value, package)]
