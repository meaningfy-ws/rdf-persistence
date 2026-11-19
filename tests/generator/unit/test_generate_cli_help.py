"""rp-generate --help: each override flag names the real ``[tool.rp-generate]`` key it overrides."""

import re

from rdf_persistence_generation.cli import build_parser
from rdf_persistence_generation.config import cli_flags
from rdf_persistence_generation.generated.rp_generation import GenerationTarget


def _accepted_keys() -> set[str]:
    """The keys a ``[tool.rp-generate]`` row accepts: a field's alias, or its name when it has none."""
    return {field.alias or name for name, field in GenerationTarget.model_fields.items()}


def test_every_override_flag_help_names_a_key_the_table_accepts() -> None:
    parser = build_parser()
    helps = {a.option_strings[0]: a.help or "" for a in parser._actions if a.option_strings}
    for flag in cli_flags():
        named = re.findall(r"`([^`]+)`", helps[flag.option])
        assert named, f"{flag.option} help names no key: {helps[flag.option]!r}"
        assert set(named) <= _accepted_keys(), f"{flag.option} help names {named}"


def test_the_schema_flag_help_names_the_schema_key() -> None:
    helps = {a.option_strings[0]: a.help for a in build_parser()._actions if a.option_strings}
    assert "`schema`" in helps["--schema"]
