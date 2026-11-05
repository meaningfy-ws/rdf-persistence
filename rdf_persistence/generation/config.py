"""Read the ``[tool.rp-generate]`` table or array of tables (PD-18) into GenerationTarget models."""

import tomllib
from argparse import Namespace
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from rdf_persistence.generation.generated.rp_generation import GenerationTarget

TOML_SCHEMA_KEY = (
    "schema"  # the model's field is schema_file: `schema` would shadow a pydantic method
)


class ConfigError(Exception):
    """The configuration is unusable: a usage error, exit code 2."""


@dataclass(frozen=True)
class Flag:
    """A command-line flag and the GenerationTarget field it overrides."""

    option: str
    field: str


FLAGS = (
    Flag("--schema", "schema_file"),
    Flag("--package", "package"),
    Flag("--python-out", "python"),
    Flag("--typescript-out", "typescript"),
    Flag("--diagrams-out", "diagrams"),
)


def _toml_entries(project: Path) -> list[dict]:
    if not project.is_file():
        return []
    table = (
        tomllib.loads(project.read_text(encoding="utf-8")).get("tool", {}).get("rp-generate", [])
    )
    entries = table if isinstance(table, list) else [table]
    return [
        {"schema_file" if key == TOML_SCHEMA_KEY else key: value for key, value in entry.items()}
        for entry in entries
    ]


def _given_flags(flags: Namespace) -> dict[str, str]:
    return {f.field: getattr(flags, f.field) for f in FLAGS if getattr(flags, f.field) is not None}


def _target(entry: dict, project: Path) -> GenerationTarget:
    try:
        return GenerationTarget.model_validate(entry)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in e['loc']).replace('schema_file', TOML_SCHEMA_KEY)}: {e['msg']}"
            for e in error.errors()
        )
        raise ConfigError(f"{project}: invalid entry: {problems}") from error


def read_targets(project: Path, flags: Namespace) -> list[GenerationTarget]:
    """Return the targets of ``project``'s ``[tool.rp-generate]``, with the flags applied.

    Flags override the keys of the only entry; with no entry they make the target; with several
    entries any flag is an error naming it.

    Raises:
        ConfigError: When no target can be made, a key is unknown or missing, or a flag conflicts.
    """
    entries, given = _toml_entries(project), _given_flags(flags)
    if len(entries) > 1 and given:
        names = ", ".join(f.option for f in FLAGS if f.field in given)
        raise ConfigError(
            f"{names} cannot be used with {len(entries)} [[tool.rp-generate]] entries in {project}"
        )
    if not entries and not {"schema_file", "package"} <= given.keys():
        raise ConfigError(
            f"no [tool.rp-generate] entry in {project}, and no --schema and --package flags"
        )
    return [_target({**entry, **given}, project) for entry in (entries or [{}])]
