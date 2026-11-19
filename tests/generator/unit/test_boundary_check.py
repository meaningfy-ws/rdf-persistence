"""The boundary check (task 1.7, PD-23): ownership of the aggregate's parts and module kinds."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation import steps
from rdf_persistence_generation.checks.boundary import (
    boundary_problems,
    derived_kind,
    kind_folder_problems,
    mixed_kind_problems,
    toolkit_themes,
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
    # target_kind is a rule of the target (its kind and its folder), not of a module: tested below by its own cases
    rules = set(BoundaryRule) - {BoundaryRule.TARGET_KIND}
    assert {f.rule for f in FAULTS} == rules, "a boundary rule has no planted fault"


@pytest.mark.slow
def test_a_domain_module_importing_the_access_module_names_both_modules(
    break_toy: Breaker, capsys: pytest.CaptureFixture[str]
) -> None:
    root = break_toy("books.yaml", BOOK_IMPORTS, ACCESS_IMPORT)
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.domain.generated")
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
def test_a_class_of_a_technical_module_needs_no_owning_root(tmp_path: Path) -> None:
    """A target of technical modules only (PD-2: a mixed target is refused, so not beside the toy's)."""
    (tmp_path / "api.yaml").write_text(API_MODULE.format(kind="technical"), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[tool.rp-generate]\nschema = "api.yaml"\npackage = "app.services.generated"\n'
        'python = "app/services/generated"\ntypescript = "web"\n',
        encoding="utf-8",
    )
    assert main(["--project", str(tmp_path / "pyproject.toml")]) == 0, "rp-generate must succeed"
    generated = tmp_path / "app" / "services" / "generated"
    ts = tmp_path / "web" / "api.ts"
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


def single_module_folder(tmp_path: Path, module_kind: str) -> Path:
    """A folder whose only module, ``api``, is annotated ``module_kind: <module_kind>``."""
    (tmp_path / "api.yaml").write_text(API_MODULE.format(kind=module_kind), encoding="utf-8")
    return tmp_path


def derived_of(folder: Path) -> TargetKind:
    return derived_kind(load_schema(folder / "api.yaml"), folder)


def mixed_problems_of(folder: Path) -> list[str]:
    view = load_schema(folder / "api.yaml")
    return [format_problem(p) for p in mixed_kind_problems(view, folder)]


def test_a_target_whose_only_module_is_technical_derives_technical_and_is_not_mixed(
    tmp_path: Path,
) -> None:
    """TC-01b: PD-1, every own module technical."""
    folder = single_module_folder(tmp_path, "technical")
    assert derived_of(folder) == TargetKind.TECHNICAL, "a technical module makes a technical target"
    assert mixed_problems_of(folder) == [], "one kind of module is no mix"


@pytest.mark.parametrize("module_kind", ["domain", "access"])
def test_a_target_whose_only_module_is_not_technical_derives_domain_and_is_not_mixed(
    tmp_path: Path, module_kind: str
) -> None:
    """Error matrix: a lone ``module_kind: access`` module derives ``domain`` (PD-1)."""
    folder = single_module_folder(tmp_path, module_kind)
    assert derived_of(folder) == TargetKind.DOMAIN, f"a {module_kind} module is no technical one"
    assert mixed_problems_of(folder) == [], "one kind of module is no mix"


def test_a_target_whose_modules_are_all_technical_derives_technical(tmp_path: Path) -> None:
    folder = tmp_path / "all-technical"
    folder.mkdir()
    assert derived_of(kind_folder(folder, "technical")) == TargetKind.TECHNICAL, (
        "every one of the own modules is technical"
    )


@pytest.mark.parametrize("side_kind", ["domain", "access"])
def test_a_target_of_technical_and_other_modules_is_refused_naming_the_technical_one(
    tmp_path: Path, side_kind: str
) -> None:
    """PD-2, spec "a target of both kinds": the problem names the technical module, once."""
    found = mixed_problems_of(kind_folder(tmp_path, side_kind))
    assert len(found) == 1, f"one mixed target, one problem: {found}"
    assert found[0].startswith(f"[{BoundaryRule.TARGET_KIND.value}] "), f"rule not named: {found}"
    assert "technical modules api" in found[0], f"the technical module is not named: {found}"
    assert "beside domain ones" in found[0], f"the mix is not named: {found}"
    assert "a target generates one kind" in found[0], f"the rule is not stated: {found}"


def test_a_mixed_target_derives_domain(tmp_path: Path) -> None:
    """PD-1: ``technical`` only when every own module is technical."""
    assert derived_of(kind_folder(tmp_path, "domain")) == TargetKind.DOMAIN, (
        "not every one is technical"
    )


def test_the_boundary_step_reports_a_mixed_target_once_and_no_folder_problem(
    toy_copy: Path,
) -> None:
    """PD-2: when a target mixes kinds, the folder rule does not run (its annotate hint would mislead)."""
    add_api_module(toy_copy, "technical")
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.services.generated")
    found = generate([target], toy_copy, (steps.BOUNDARY_STEP,), check=True)
    assert [p.rule for p in found] == [BoundaryRule.TARGET_KIND.value], (
        f"one problem expected: {found}"
    )
    line = format_problem(found[0])
    assert "api" in line, f"the technical module is not named: {line}"
    assert "annotate" not in line, f"the folder hint was given for a mixed target: {line}"


def test_the_boundary_step_derives_the_kind_of_its_target_for_the_folder_rule(
    toy_copy: Path,
) -> None:
    """DEC-1: the toy's modules are domain, so a technical layer is refused with no kind declared."""
    target = GenerationTarget(schema_file=ROOT_SCHEMA, package="app.services.generated")
    found = generate([target], toy_copy, (steps.BOUNDARY_STEP,), check=True)
    assert [p.rule for p in found] == [BoundaryRule.TARGET_KIND.value], f"{found}"
    assert "domain" in format_problem(found[0]), f"the derived kind is not named: {found}"


def unannotated_module_folder(tmp_path: Path) -> Path:
    """A folder whose only module, ``api``, has no ``annotations:`` block, so no ``module_kind``."""
    text = API_MODULE.format(kind="domain").replace("annotations:\n  module_kind: domain\n", "", 1)
    assert "module_kind" not in text, "the fixture must carry no module_kind"
    (tmp_path / "api.yaml").write_text(text, encoding="utf-8")
    return tmp_path


def test_a_module_without_the_annotation_derives_domain(tmp_path: Path) -> None:
    """Spec "a consumer's settings without the annotation": no ``module_kind`` is no technical module."""
    folder = unannotated_module_folder(tmp_path)
    assert derived_of(folder) == TargetKind.DOMAIN, "an unannotated module is no technical one"
    assert mixed_problems_of(folder) == [], "one kind of module is no mix"


def test_the_boundary_step_on_a_module_without_the_annotation_names_the_annotation_to_add(
    tmp_path: Path,
) -> None:
    """Spec "a consumer's settings without the annotation": domain target in a technical layer."""
    unannotated_module_folder(tmp_path)
    target = GenerationTarget(schema_file="api.yaml", package="app.services.generated")
    found = generate([target], tmp_path, (steps.BOUNDARY_STEP,), check=True)
    # The lone ``Account`` class is a domain class with no owner, so the ownership rule also speaks;
    # this test is about the kind rule only.
    kind_problems = [p for p in found if p.rule == BoundaryRule.TARGET_KIND.value]
    assert len(kind_problems) == 1, f"one target_kind problem expected: {found}"
    line = format_problem(kind_problems[0])
    assert "domain" in line, f"the derived kind is not named: {line}"
    assert "module_kind: technical" in line, f"the annotation to add is not named: {line}"


PROJECT_HEAD = (
    '[tool.rp-generate]\nschema = "library.yaml"\npackage = "{package}"\npython = "generated"\n'
)


def files_of(folder: Path) -> set[str]:
    return {p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()}


def write_project(toy: Path, package: str) -> Path:
    project = toy / "pyproject.toml"
    project.write_text(PROJECT_HEAD.format(package=package), encoding="utf-8")
    return project


def test_a_domain_target_in_a_technical_layer_fails_naming_target_package_and_kind_and_writes_nothing(
    toy_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec "a consumer's settings without the annotation": the whole run is refused, nothing is left."""
    package = "tests.fixtures.library.services.generated"
    project = write_project(toy_copy, package)
    before = files_of(toy_copy)
    code = main(["--project", str(project)])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code != 0, "a domain target in a technical layer must fail"
    assert BoundaryRule.TARGET_KIND.value in text, f"the rule is not named: {text}"
    assert ROOT_SCHEMA in text, f"the target (its schema) is not named: {text}"
    assert package in text, f"the package is not named: {text}"
    assert "domain" in text, f"the derived kind is not named: {text}"
    assert "module_kind: technical" in text, f"the annotation is not named as a fix: {text}"
    assert files_of(toy_copy) == before, "a failed run wrote a file"
    assert not (toy_copy / "generated").exists(), "the output folder was created"
    assert [p.name for p in toy_copy.iterdir() if p.name.startswith(".rp-generate")] == [], (
        "a staging folder is left behind"
    )


def test_a_target_of_both_kinds_fails_naming_the_target_and_the_technical_module_and_writes_nothing(
    toy_copy: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Spec "a target of both kinds": a technical module in a target of domain modules."""
    add_api_module(toy_copy, "technical")
    project = write_project(toy_copy, "tests.fixtures.library.domain.generated")
    before = files_of(toy_copy)
    code = main(["--project", str(project)])
    captured = capsys.readouterr()
    text = captured.out + captured.err
    assert code != 0, "a target of both kinds must fail"
    assert ROOT_SCHEMA in text, f"the target (its schema) is not named: {text}"
    assert "api" in text, f"the technical module is not named: {text}"
    assert "a target generates one kind" in text, f"the rule is not stated: {text}"
    assert files_of(toy_copy) == before, "a failed run wrote a file"


# --- kind and folder (PD-3, DEC-3): every target, the theme rule for the toolkit's own run ------------

REPO = MODEL_DIR.parent
SERVICE_SCHEMA = "rdf_persistence/model/technical/api/rp_api_entrypoints.yaml"
TOOLKIT_FOLDER = REPO / Path(SERVICE_SCHEMA).parent


def folder_problems_of(folder: Path, package: str, kind: TargetKind) -> list[str]:
    return [format_problem(p) for p in kind_folder_problems(folder, package, kind)]


@pytest.mark.parametrize(
    ("kind", "package"),
    [
        (TargetKind.DOMAIN, "rdf_persistence.core.domain.generated"),  # TC-13
        (TargetKind.TECHNICAL, "rdf_persistence.access.services.generated"),
        (TargetKind.TECHNICAL, "rdf_persistence.access.adapters.generated.wire"),  # a group after
        (TargetKind.TECHNICAL, "rdf_persistence.access.entrypoints.generated"),
    ],
)
def test_a_toolkit_target_in_the_folder_its_kind_allows_has_no_problem(
    kind: TargetKind, package: str
) -> None:
    assert folder_problems_of(TOOLKIT_FOLDER, package, kind) == [], "the folder fits the kind"


@pytest.mark.parametrize(
    ("kind", "package"),
    [
        (TargetKind.TECHNICAL, "rdf_persistence.access.domain.generated"),  # TC-14
        (TargetKind.DOMAIN, "rdf_persistence.access.adapters.generated"),  # TC-15
        (TargetKind.DOMAIN, "rdf_persistence.access.services.generated.service"),
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
    found = folder_problems_of(TOOLKIT_FOLDER, "rdf_persistence.access.domain", TargetKind.DOMAIN)
    assert len(found) == 1, f"one target, one problem: {found}"
    assert "has no layer before generated" in found[0], f"the missing layer is not named: {found}"


def test_a_domain_target_in_a_technical_layer_of_the_toolkit_names_the_annotation() -> None:
    """PD-3: a derived ``domain`` in a technical layer is told how to be technical."""
    found = folder_problems_of(
        TOOLKIT_FOLDER, "rdf_persistence.access.adapters.generated", TargetKind.DOMAIN
    )
    assert len(found) == 1, f"one target, one problem: {found}"
    assert "is not in a folder a domain target allows" in found[0], f"{found}"
    assert "; if its modules are technical, annotate them module_kind: technical" in found[0], found


def test_a_technical_target_in_the_domain_layer_does_not_name_the_annotation() -> None:
    found = folder_problems_of(
        TOOLKIT_FOLDER, "rdf_persistence.access.domain.generated", TargetKind.TECHNICAL
    )
    assert len(found) == 1, f"one target, one problem: {found}"
    assert "annotate" not in found[0], f"the hint is for a derived domain only: {found}"


# TC-01a: the consumer rows of the error matrix. A consumer's folder is the toy's: no theme check.


@pytest.mark.parametrize("package", ["app.generated", "p", "generated"])
@pytest.mark.parametrize("kind", [TargetKind.DOMAIN, TargetKind.TECHNICAL])
def test_a_consumer_package_without_a_layer_before_generated_is_refused(
    kind: TargetKind, package: str
) -> None:
    """TC-16 inverted: a consumer keeps no layout of its own; ``app.generated`` fails."""
    found = folder_problems_of(TOY, package, kind)
    assert len(found) == 1, f"one target, one problem: {found}"
    assert found[0].startswith("[target_kind] "), f"rule not named: {found}"
    assert package in found[0], f"the package is not named: {found}"
    assert "has no layer before generated" in found[0], f"the missing layer is not named: {found}"
    assert f"a {kind.value} target's package ends in" in found[0], f"the kind is not named: {found}"


@pytest.mark.parametrize(
    ("kind", "package"),
    [
        (TargetKind.DOMAIN, "app.catalogue.domain.generated"),  # no theme check for a consumer
        (TargetKind.DOMAIN, "app.domain.generated"),
        (TargetKind.TECHNICAL, "app.services.generated"),
        (TargetKind.TECHNICAL, "app.adapters.generated.wire"),
    ],
)
def test_a_consumer_package_in_the_layer_of_its_kind_has_no_problem(
    kind: TargetKind, package: str
) -> None:
    assert folder_problems_of(TOY, package, kind) == [], "the layer fits the kind"


def test_a_consumer_domain_target_in_a_technical_layer_names_the_annotation() -> None:
    """Spec "a consumer's settings without the annotation": the derived kind is named, the fix too."""
    found = folder_problems_of(TOY, "app.services.generated", TargetKind.DOMAIN)
    assert len(found) == 1, f"one target, one problem: {found}"
    assert "domain" in found[0], f"the derived kind is not named: {found}"
    assert "module_kind: technical" in found[0], f"the annotation is not named: {found}"


def test_a_consumer_technical_target_in_the_domain_layer_is_refused() -> None:
    found = folder_problems_of(TOY, "app.domain.generated", TargetKind.TECHNICAL)
    assert len(found) == 1, f"one target, one problem: {found}"
    assert "is not in a folder a technical target allows" in found[0], f"{found}"


LIBRARY = "rdf_persistence"


@pytest.mark.parametrize(
    ("kind", "package"),
    [
        (TargetKind.TECHNICAL, "rdf_persistence.services.generated"),
        (TargetKind.TECHNICAL, "rdf_persistence.services.generated.settings"),
        (TargetKind.DOMAIN, f"{LIBRARY}.domain.generated"),  # the old layer folder, no theme
        (TargetKind.TECHNICAL, "rdf_persistence.nowhere.services.generated"),
        (TargetKind.DOMAIN, "rdf_persistence.models.domain.generated"),
        (TargetKind.TECHNICAL, "elsewhere.access.services.generated"),
        (TargetKind.TECHNICAL, "rdf_persistence.access.extra.services.generated"),
    ],
)
def test_a_toolkit_target_whose_segment_before_the_layer_is_no_theme_is_named(
    kind: TargetKind, package: str
) -> None:
    """PD-4 (D-25): ``<root>.<theme>.<layer>.generated``; a layer straight under the package is no theme."""
    found = folder_problems_of(TOOLKIT_FOLDER, package, kind)

    assert len(found) == 1, f"one target, one problem: {found}"
    assert found[0].startswith(f"[target_kind] {package}:"), f"rule and package not named: {found}"
    assert "theme" in found[0], f"the theme is not asked for: {found}"


def test_the_themes_are_the_package_folders_of_the_library_but_the_testkit() -> None:
    """One source for the theme list: the subpackages of ``rdf_persistence``, the testkit apart."""
    assert {"core", "access", "api", "messaging"} <= toolkit_themes()
    assert not {"testkit", "model", "domain", "adapters"} & toolkit_themes()


def test_the_themes_of_the_check_are_the_themes_of_the_changed_files_mapper() -> None:
    """A folder added or dropped without the mapper (or the reverse) fails here."""
    from tests.changed import THEMES

    assert toolkit_themes() == THEMES


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


def toolkit_target(package: str) -> GenerationTarget:
    return GenerationTarget(schema_file=SERVICE_SCHEMA, package=package)


def test_the_toolkit_targets_derive_domain_for_the_metamodel_and_technical_for_the_rest() -> None:
    """TC-02, permanent form: every target of the toolkit's own ``pyproject.toml`` (24 of them).

    The metamodel's five domain targets (``rp.yaml`` and the four theme targets of
    domain-model-per-theme) derive domain; the other 19 derive technical.
    """
    targets = read_targets(PYPROJECT)
    assert len(targets) == 24, f"the toolkit's targets: {[t.schema_file for t in targets]}"
    derived = {}
    for target in targets:
        root = REPO / target.schema_file
        derived[target.schema_file] = derived_kind(load_schema(root), root.parent)
    assert [f for f, k in derived.items() if k == TargetKind.DOMAIN] == [
        "rdf_persistence/model/rp.yaml",
        "rdf_persistence/model/rp_tenancy.yaml",
        "rdf_persistence/model/rp_provenance.yaml",
        "rdf_persistence/model/rp_files.yaml",
        "rdf_persistence/model/rp_collaboration.yaml",
    ], f"only the metamodel's five targets derive domain: {derived}"
    assert sum(k == TargetKind.TECHNICAL for k in derived.values()) == 19, f"{derived}"


@pytest.mark.slow
def test_the_boundary_step_passes_a_technical_target_in_the_api_entrypoints_generated_package() -> (
    None
):
    """TC-72, first half: a technical target in a theme's ``generated`` folder (``make generate`` covers the rest)."""
    target = toolkit_target("rdf_persistence.api.entrypoints.generated")
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
    found = generate([toolkit_target(package)], REPO, (steps.BOUNDARY_STEP,), check=True)
    assert [(p.rule, p.element) for p in found] == [(BoundaryRule.TARGET_KIND.value, package)]
