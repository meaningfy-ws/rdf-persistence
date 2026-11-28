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
from rdf_persistence_generation.steps import TYPESCRIPT_STEP, _toolkit_folder, _typescript_owners

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
    assert sorted(files) == ["index.ts", "library_problems.ts", "loan_checks_response.ts"], (
        "only the target's own files"
    )
    assert "rp_" not in files["index.ts"], "the index exports none of the shared modules"
    assert 'from "../../domain/generated/values/loan_checks"' in files["loan_checks_response.ts"], (
        "#371 imports still point at their owner"
    )
    assert 'from "../../domain/generated/rp_core"' in files["loan_checks_response.ts"], (
        "the toy's toolkit type is imported from the owner's rp_core"
    )


def test_a_value_importer_writes_no_shared_module() -> None:  # TC-1
    files = _files(VALUE_SCHEMA, VALUE_FOLDER, toolkit=OWNER_FOLDER)
    assert sorted(files) == ["index.ts", "loan_checks.ts"], "no shared module is written"
    assert "rp_" not in files["index.ts"], "the index exports none of them"


MODEL = Path(__file__).parents[3] / "rdf_persistence/model"
IMPORTER_SCHEMA = """id: https://example.org/ns/library/holder
name: holder
title: Holder
description: A technical module whose class holds a metamodel type and a served type.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
  - {core}
  - {served}
annotations:
  module_kind: technical

classes:
  Holder:
    title: Holder
    description: Holds a registry kind and an authorisation.
    attributes:
      holder_id:
        description: Identifier.
        identifier: true
      who:
        description: A metamodel type.
        range: RegistryKind
      checked:
        description: A served type.
        range: Authorised
"""


@pytest.mark.parametrize(
    ("type_name", "module"),
    [
        pytest.param("RegistryKind", "rp_core", id="a-metamodel-enum"),
        pytest.param("Authorised", typescript.SERVICE_MODULE, id="a-served-type"),
    ],
)
def test_an_importer_of_the_toolkit_imports_a_type_it_uses_from_the_owner(
    tmp_path: Path, type_name: str, module: str
) -> None:  # TC-1, F1
    schema = tmp_path / "holder.yaml"
    schema.write_text(
        IMPORTER_SCHEMA.format(
            core=(MODEL / "rp_core").as_posix(),
            served=(MODEL / "technical/api/rp_api_entrypoints").as_posix(),
        ),
        encoding="utf-8",
    )
    files = _files(
        schema,
        Path("web/src/services/generated"),
        toolkit=Path("web/src/domain/generated"),
    )
    for name in (*TOOLKIT_NAMES, "rp_api_entrypoints"):
        assert f"{name}.ts" not in files, f"{name} is the owner's file"
    assert sorted(files) == ["holder.ts", "index.ts"], "only the target's own files"
    assert "rp_" not in files["index.ts"], "the index exports none of the shared modules"
    assert f'from "../../domain/generated/{module}"' in files["holder.ts"], (
        f"{type_name} is imported from the owner's {module}"
    )
    assert type_name in files["holder.ts"], f"the module uses {type_name}"


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


def test_the_owners_render_of_the_domain_schema_equals_the_plain_render() -> None:  # RISK-2, TC-2
    today = _files(DOMAIN_SCHEMA, OWNER_FOLDER)
    owner = _files(DOMAIN_SCHEMA, OWNER_FOLDER, toolkit=OWNER_FOLDER, owns_toolkit=True)
    assert owner == today, "the domain schema's closure already holds the shared set"


def test_without_a_toolkit_the_domain_render_is_the_committed_domain_tree() -> None:  # TC-3, R-6
    rendered = _files(
        DOMAIN_SCHEMA, OWNER_FOLDER, owners={VALUE_PACKAGE: VALUE_FOLDER}, toolkit=None
    )
    committed = {f.name: f.read_text(encoding="utf-8") for f in COMMITTED.glob("*.ts")}
    assert sorted(rendered) == sorted(committed), "the same files, none of the values folder's"
    for name, text in committed.items():
        assert rendered[name] == text, f"{name} differs from the committed domain file"


def _staged(staging: Path, run: Run) -> dict[str, str]:
    run.staging = staging
    TYPESCRIPT_STEP.run(run)
    return {
        f.relative_to(staging).as_posix(): f.read_text(encoding="utf-8")
        for f in sorted(staging.rglob("*"))
        if f.is_file()
    }


def test_one_typescript_target_with_the_key_writes_the_same_files_as_without(
    tmp_path: Path,
) -> None:  # TC-3, R-6
    with_key = _staged(tmp_path / "with", _run(_ts("a", owner=True)))
    without = _staged(tmp_path / "without", _run(_ts("a")))
    assert with_key, "the target wrote files"
    assert with_key == without, (
        "one TypeScript target writes the same files with or without the key"
    )


TESTKIT_SCHEMA = """id: https://example.org/ns/library/holder
name: holder
title: Holder
description: A technical module whose class holds one type of a non-shared toolkit module.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
  - {testkit}
annotations:
  module_kind: technical

classes:
  Holder:
    title: Holder
    description: Holds a selection data outcome.
    attributes:
      holder_id:
        description: Identifier.
        identifier: true
      outcome:
        description: A type of the testkit module.
        range: SelectionDataOutcome
"""


def test_a_toolkit_module_outside_the_shared_set_is_written_and_exported(
    tmp_path: Path,
) -> None:  # TC-2, R-2
    schema = tmp_path / "holder.yaml"
    schema.write_text(
        TESTKIT_SCHEMA.format(testkit=(MODEL / "technical/testkit/rp_testkit").as_posix()),
        encoding="utf-8",
    )
    files = _files(schema, Path("web/src/services/generated"), toolkit=OWNER_FOLDER)
    assert "rp_testkit" not in typescript._shared_names(), "outside the shared set"
    assert "rp_testkit.ts" in files, "the importer writes the module the owner does not"
    assert 'export * from "./rp_testkit";' in files["index.ts"], "and exports it"
    assert 'from "./rp_testkit"' in files["holder.ts"], "its own import stays local"


def test_a_toolkit_specifier_from_a_nested_owner_folder_starts_with_a_dot_slash() -> (
    None
):  # TC-4, R-7
    module = _module(typescript.TsImport(module="rp_core", names=["A"]))
    nested = Path("web/src/generated/toolkit")
    (written,) = typescript._importing_toolkit([module], nested, Path("web/src/generated"))
    assert 'from "./toolkit/rp_core"' in written.text, "a nested owner folder is imported with ./"


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
