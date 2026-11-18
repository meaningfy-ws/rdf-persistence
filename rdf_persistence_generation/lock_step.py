"""The schema lock in the pipeline (PD-3, PD-4): the check that compares, the step that writes.

The check loads the migration files that exist, reads the committed lock and applies the table of
PD-3; it writes nothing, so ``--check`` runs it. The write step stages the lock, so it is a manifest
output, and drafts the migration of a new version straight into the migrations folder: a draft is the
developer's file from then on, never staged, never overwritten.
"""

import sys
from pathlib import Path

import yaml

from rdf_persistence.domain.exceptions import InvalidMigration
from rdf_persistence.services.generated.service.rp_service import Migration
from rdf_persistence.services.migrations import load_migration, migration_file_name
from rdf_persistence.services.schema_structure import generation_view
from rdf_persistence_generation.config import TOOLKIT_ROOTS, migrations_folder
from rdf_persistence_generation.exceptions import refusing_unsupported_rules
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    GeneratedFile,
    LockChange,
    LockRule,
    SchemaLock,
)
from rdf_persistence_generation.lock import changes, described, draft, summarise
from rdf_persistence_generation.pipeline import Run, schema_faults, stage

LOCK_NAME = "schema.lock.json"
MAX_ERROR = 300  # characters of a library's error text kept in a message
# What needs no new version (safe), or what no step can do (not migratable).
NOT_STEPPED = (LockRule.SAFE, LockRule.NOT_MIGRATABLE)


def _folder(run: Run) -> Path | None:
    relative = migrations_folder(run.target)
    return run.base / relative if relative else None


def _current(run: Run) -> SchemaLock:
    """The lock of the schema as it is now, from the view the generators use."""
    with refusing_unsupported_rules(), schema_faults():
        return summarise(
            generation_view(run.schema_path, roots=TOOLKIT_ROOTS), run.schema_path.parent
        )


def _read_lock(path: Path) -> SchemaLock | CheckProblem | None:
    """The committed lock; ``None`` when there is none, a problem when it cannot be read."""
    if not path.is_file():
        return None
    try:
        return SchemaLock.model_validate_json(path.read_text(encoding="utf-8"))
    except (
        OSError,
        ValueError,
    ) as error:  # not UTF-8 (UnicodeDecodeError) or not a lock (pydantic)
        return CheckProblem(
            element=path.name,
            message=f"cannot be read ({str(error)[:MAX_ERROR]}); restore it from version control",
        )


def _existing_migrations(folder: Path) -> tuple[list[Migration], list[CheckProblem]]:
    """Every migration file the folder holds before this run, and the ones that do not load."""
    found: list[Migration] = []
    problems: list[CheckProblem] = []
    for path in sorted(folder.glob("*.yaml")):
        try:
            found.append(load_migration(path))
        except InvalidMigration as error:
            problems.append(CheckProblem(message=str(error)))
    return found, problems


def _change_problems(old: SchemaLock, new: SchemaLock) -> list[CheckProblem]:
    """What the table of PD-3 refuses for the step from ``old`` to ``new``."""
    found = changes(old, new)
    raised = old.schema_version != new.schema_version
    return [
        *(_not_migratable(c) for c in found if c.rule == LockRule.NOT_MIGRATABLE),
        *(_needs_version(c) for c in found if not raised and c.rule not in NOT_STEPPED),
    ]


def _not_migratable(change: LockChange) -> CheckProblem:
    return CheckProblem(message=f"not migratable, {described(change)}")


def _needs_version(change: LockChange) -> CheckProblem:
    return CheckProblem(
        message=f"{described(change)}: set a new `version:` in the root schema, then regenerate"
    )


def _refusals(old: SchemaLock | None, new: SchemaLock, left: dict[str, str]) -> list[CheckProblem]:
    problems = []
    if new.schema_version in left:
        problems.append(
            CheckProblem(
                message=f"version {new.schema_version} is one the chain already left "
                f"({left[new.schema_version]}): set a version no migration starts from"
            )
        )
    if old is None:
        return problems
    if old.schema_id != new.schema_id:
        problems.append(
            CheckProblem(
                element=LOCK_NAME,
                message=f"is the lock of {old.schema_id}, not of {new.schema_id}",
            )
        )
        return problems
    return [*problems, *_change_problems(old, new)]


def lock_problems(run: Run) -> list[CheckProblem]:
    """The problems of the lock and of the migration files that exist, for a target with ``migrations``."""
    folder = _folder(run)
    if folder is None:
        return []
    migrations, problems = _existing_migrations(folder)
    old = _read_lock(folder / LOCK_NAME)
    if isinstance(old, CheckProblem):
        return [*problems, old]
    left = {m.from_version: migration_file_name(m.from_version, m.to_version) for m in migrations}
    return [*problems, *_refusals(old, _current(run), left)]


def _draft_text(migration: Migration) -> str:
    text: str = yaml.safe_dump(
        migration.model_dump(exclude_none=True),
        sort_keys=False,
        allow_unicode=True,
        width=sys.maxsize,
    )
    return text


def _write_draft(folder: Path, old: SchemaLock, new: SchemaLock) -> None:
    """Draft the migration from ``old`` to ``new`` unless its file exists; say where it is."""
    path = folder / migration_file_name(old.schema_version, new.schema_version)
    text = _draft_text(draft(old, new))  # before the file exists: a refusal leaves none behind
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8") as file:  # exclusive: no race, no link followed
            file.write(text)
    except FileExistsError:
        return
    print(f"rp-generate: drafted {path}: review it before you commit")


def write_lock(run: Run) -> None:
    """Stage the lock; with a new version and no file for it yet, draft the migration (PD-3)."""
    relative = migrations_folder(run.target)
    if relative is None:
        return
    folder = run.base / relative
    new = _current(run)
    old = _read_lock(folder / LOCK_NAME)
    text = new.model_dump_json(indent=2) + "\n"
    stage(run, relative, [GeneratedFile(name=LOCK_NAME, text=text)])
    if isinstance(old, SchemaLock) and old.schema_version != new.schema_version:
        _write_draft(folder, old, new)
