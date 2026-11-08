"""Read the ``[tool.rp-generate]`` table or array of tables (PD-18) into GenerationTarget models."""

import functools
import tomllib
from argparse import Namespace
from pathlib import Path

from pydantic import ValidationError

from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import (
    CliFlag,
    GenerationAnnotation,
    GenerationTarget,
)
from rdf_persistence.services.schema import PACKAGE_DIR, load_schema
from rdf_persistence.services.schema_structure import annotation_text

# TOML key -> model field where they differ (`schema` would shadow a pydantic method)
TOML_KEYS = {"schema": "schema_file", "regenerate-command": "regenerate_command"}
FIELD_KEYS = {field: key for key, field in TOML_KEYS.items()}
GENERATION_MODEL = PACKAGE_DIR / "generation" / "model" / "rp_generation.yaml"
TARGET_CLASS = "GenerationTarget"


@functools.cache
def cli_flags() -> tuple[CliFlag, ...]:
    """The flags of ``rp-generate``: each slot of GenerationTarget that carries a ``cli_flag`` annotation."""
    slots = load_schema(GENERATION_MODEL).class_induced_slots(TARGET_CLASS)
    return tuple(
        CliFlag(option=option, field=str(slot.name))
        for slot in slots
        if (option := annotation_text(slot, GenerationAnnotation.CLI_FLAG))
    )


def python_folder(target: GenerationTarget) -> Path:
    """The Python output folder of ``target``, relative to the folder of the ``pyproject.toml``."""
    return Path(target.python or target.package.replace(".", "/"))


def _given_flags(flags: Namespace) -> dict[str, str]:
    return {
        f.field: getattr(flags, f.field)
        for f in cli_flags()
        if getattr(flags, f.field, None) is not None
    }


def _problems(error: ValidationError) -> str:
    """The errors of a validation, naming TOML keys rather than model fields."""
    return "; ".join(
        f"{'.'.join(FIELD_KEYS.get(str(part), str(part)) for part in e['loc'])}: {e['msg']}"
        for e in error.errors()
    )


def _refuse_unusable(rows: int, given: dict[str, str], project: Path) -> None:
    """Flags override the keys of the only row; with no row they make the target; with several
    rows any flag is an error naming it."""
    if rows > 1 and given:
        names = ", ".join(f.option for f in cli_flags() if f.field in given)
        raise ConfigError(
            f"{names} cannot be used with {rows} [[tool.rp-generate]] entries in {project}"
        )
    if not rows and not {"schema_file", "package"} <= given.keys():
        raise ConfigError(
            f"no [tool.rp-generate] entry in {project}, and no --schema and --package flags"
        )


def _toml_entries(project: Path, given: dict[str, str]) -> list[GenerationTarget]:
    """The targets of ``project``'s table, each row validated with the flags laid over it."""
    table = (
        tomllib.loads(project.read_text(encoding="utf-8")).get("tool", {}).get("rp-generate", [])
        if project.is_file()
        else []
    )
    rows = table if isinstance(table, list) else [table]
    _refuse_unusable(len(rows), given, project)
    try:
        return [
            GenerationTarget.model_validate(
                {
                    **{TOML_KEYS.get(k, k): v for k, v in row.items()},
                    **given,
                }
            )
            for row in rows or [{}]
        ]
    except ValidationError as error:
        raise ConfigError(f"{project}: invalid entry: {_problems(error)}") from error


def read_targets(project: Path, flags: Namespace | None = None) -> list[GenerationTarget]:
    """Return the targets of ``project``'s ``[tool.rp-generate]``, with the flags applied.

    Raises:
        ConfigError: When no target can be made, a key is unknown or missing, or a flag conflicts.
    """
    return _toml_entries(project, _given_flags(flags or Namespace()))
