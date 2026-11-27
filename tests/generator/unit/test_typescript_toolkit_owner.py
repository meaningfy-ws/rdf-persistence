"""One TypeScript target of a project owns the toolkit's shared modules; the others import them.

typescript-toolkit-modules PD-3 to PD-6: ``render`` takes the owner's folder (``toolkit``) and whether
this run is the owner (``owns_toolkit``); ``_toolkit_folder`` finds the owner of a run.
"""

from pathlib import Path

import pytest

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation.config import read_targets
from rdf_persistence_generation.extensions import typescript
from rdf_persistence_generation.generated.rp_generation import GenerationTarget
from rdf_persistence_generation.manifest import current_inputs
from rdf_persistence_generation.pipeline import Run
from rdf_persistence_generation.steps import _toolkit_folder, _typescript_owners

from .golden import ROOT_SCHEMA, TOY

VALUE_SCHEMA = TOY / "values/loan_checks.yaml"
TECHNICAL_SCHEMA = TOY / "services/loan_checks_response.yaml"
DOMAIN_SCHEMA = TOY / ROOT_SCHEMA
OWNER_FOLDER = Path("web/src/domain/generated")
VALUE_FOLDER = Path("web/src/domain/generated/values")
TECHNICAL_FOLDER = Path("web/src/services/generated")
COMMITTED = TOY / "web/src/domain/generated"
VALUE_PACKAGE = "tests.fixtures.library.domain.generated.values"
TOOLKIT_NAMES = ("rp_access", "rp_core", "rp_service", "rp_tenancy")


def _files(schema: Path, folder: Path, **kwargs: object) -> dict[str, str]:
    return {f.name: f.text for f in typescript.render(schema, folder=folder, **kwargs)}  # type: ignore[arg-type]


def test_an_importer_writes_no_shared_module_and_imports_them_from_the_owner() -> None:  # TC-1
    files = _files(
        TECHNICAL_SCHEMA,
        TECHNICAL_FOLDER,
        owners={VALUE_PACKAGE: VALUE_FOLDER},
        toolkit=OWNER_FOLDER,
    )
    for name in TOOLKIT_NAMES:
        assert f"{name}.ts" not in files, f"{name} is the owner's file"
    assert sorted(files) == ["index.ts", "loan_checks_response.ts"], "only the target's own files"
    assert "rp_" not in files["index.ts"], "the index exports none of the shared modules"
    assert 'from "../../domain/generated/values/loan_checks"' in files["loan_checks_response.ts"], (
        "#371 imports still point at their owner"
    )


def test_a_value_importer_writes_no_shared_module() -> None:  # TC-1
    files = _files(VALUE_SCHEMA, VALUE_FOLDER, toolkit=OWNER_FOLDER)
    assert sorted(files) == ["index.ts", "loan_checks.ts"], "no shared module is written"
    assert "rp_" not in files["index.ts"], "the index exports none of them"


def _module(*imports: typescript.TsImport) -> typescript.TsModule:
    return typescript.TsModule(name="mine", enums=[], interfaces=[], imports=list(imports))


def test_an_import_of_a_shared_module_is_pointed_at_the_owner() -> None:  # TC-1
    served = typescript._served_modules(tuple(typescript.SERVED_SCHEMAS))[0][0]
    module = _module(
        typescript.TsImport(module="mine_other", names=["B"]),
        typescript.TsImport(module="rp_core", names=["A"]),
        typescript.TsImport(module=served, names=["S"]),
    )
    (written,) = typescript._importing_toolkit([module], OWNER_FOLDER, VALUE_FOLDER)
    assert 'from "../rp_core"' in written.text, (
        "a shared module is imported from the owner's folder"
    )
    assert 'from "../rp_service"' in written.text, (
        "a served type is imported from the merged module"
    )
    assert 'from "./mine_other"' in written.text, "a module that is not shared keeps its import"
    assert served not in written.text, "no import of a served schema's own file"


def test_the_owner_gains_a_metamodel_module_its_schema_does_not_import() -> None:  # TC-2a
    plain = _files(VALUE_SCHEMA, VALUE_FOLDER)
    owner = _files(VALUE_SCHEMA, VALUE_FOLDER, toolkit=VALUE_FOLDER, owns_toolkit=True)
    assert "rp_collections.ts" not in plain, "the value schema does not import it"
    assert "rp_collections.ts" in owner, "the owner writes every shared module"
    assert 'export * from "./rp_collections";' in owner["index.ts"], "and exports it"


def test_the_shared_modules_render_as_the_committed_owner_files() -> None:  # TC-2b
    assert typescript._shared_modules(), "there are shared modules"
    for module in typescript._shared_modules():
        committed = (COMMITTED / f"{module.name}.ts").read_text(encoding="utf-8")
        assert typescript._file(module).text == committed, (
            f"{module.name} differs from the committed owner file"
        )
    owner = _files(DOMAIN_SCHEMA, OWNER_FOLDER, toolkit=OWNER_FOLDER, owns_toolkit=True)
    assert owner["rp_service.ts"] == (COMMITTED / "rp_service.ts").read_text(encoding="utf-8"), (
        "the merged served module equals the committed one"
    )


def test_the_shared_names_hold_the_modules_the_served_schemas_and_the_service_module() -> None:
    names = typescript._shared_names()
    assert typescript.SERVICE_MODULE in names, "the merged module is shared"
    assert {m.name for m in typescript._shared_modules()} <= set(names), "every shared module"
    assert "rp_collections" in names, "a metamodel module the toy's value schema lacks"


def test_without_a_toolkit_the_domain_render_is_today_s() -> None:  # TC-5
    today = _files(DOMAIN_SCHEMA, OWNER_FOLDER)
    explicit = _files(DOMAIN_SCHEMA, OWNER_FOLDER, toolkit=None)
    owner = _files(DOMAIN_SCHEMA, OWNER_FOLDER, toolkit=OWNER_FOLDER, owns_toolkit=True)
    assert explicit == today, "toolkit=None is today's path"
    assert owner == today, "the domain schema's closure already holds the shared set"


def _target(**update: object) -> GenerationTarget:
    base = read_targets(TOY / "pyproject.toml")[
        1
    ]  # the value entry: its closure lacks rp_collections
    return base.model_copy(update=update)


def _run(*targets: GenerationTarget) -> Run:
    return Run(
        targets[0] if targets else _target(),
        TOY,
        TOY,
        load_schema(DOMAIN_SCHEMA),
        targets=targets,
    )


def _ts(folder: str, *, owner: bool = False) -> GenerationTarget:
    return _target(
        typescript=folder, toolkit_typescript=owner, package=f"p{folder.replace('/', '_')}"
    )


TOY_RUN_TARGETS = tuple(read_targets(TOY / "pyproject.toml"))

FOLDER_CASES = [
    pytest.param((_ts("a", owner=True),), None, id="one-target-with-the-key"),
    pytest.param((), None, id="flags-only-run"),
    pytest.param((_ts("a"), _ts("b")), None, id="two-targets-no-owner"),
    pytest.param((_ts("a", owner=True), _ts("b", owner=True)), None, id="two-owners"),
    pytest.param((_ts("a", owner=True), _ts("b")), Path("a"), id="one-owner-of-two"),
    pytest.param((_ts("a"), _ts("b", owner=True), _ts("c")), Path("b"), id="owner-in-the-middle"),
]


@pytest.mark.parametrize(("targets", "expected"), FOLDER_CASES)
def test_the_toolkit_folder_of_a_run(
    targets: tuple[GenerationTarget, ...], expected: Path | None
) -> None:  # TC-5
    run = _run(*targets) if targets else Run(_target(), TOY, TOY, load_schema(DOMAIN_SCHEMA))
    assert _toolkit_folder(run) == expected, "the owner's folder, or None"
    assert _typescript_owners(run) is not None, "owners stay computed as before"


def test_a_target_with_the_key_lists_the_metamodel_files_as_inputs() -> None:  # TC-8
    path = "rdf_persistence/model/rp_collections.yaml"
    with_key = {e.path for e in current_inputs(_target(toolkit_typescript=True), TOY)}
    without = {e.path for e in current_inputs(_target(toolkit_typescript=False), TOY)}
    assert path in with_key, "a metamodel module the owner writes is an input"
    assert path not in without, "an importer does not list it"
