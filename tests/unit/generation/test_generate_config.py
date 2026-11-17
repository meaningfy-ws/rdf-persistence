"""The [tool.rp-generate] configuration (PD-18) becomes GenerationTarget models."""

import json
from pathlib import Path

import pytest

from rdf_persistence.generation import config, steps
from rdf_persistence.generation.cli import build_parser
from rdf_persistence.generation.config import cli_flags, read_targets
from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import GenerationTarget, TargetKind
from rdf_persistence.generation.pipeline import generate

from .conftest import TOY

SINGLE = """
[tool.rp-generate]
schema = "m.yaml"
package = "app.generated"
typescript = "web"
"""

SEVERAL = """
[[tool.rp-generate]]
schema = "a.yaml"
package = "app.a"

[[tool.rp-generate]]
schema = "b.yaml"
package = "app.b"
python = "out/b"
"""


def read(tmp_path: Path, toml: str | None, *flags: str) -> list[GenerationTarget]:
    project = tmp_path / "pyproject.toml"
    if toml is not None:
        project.write_text(toml, encoding="utf-8")
    return read_targets(project, build_parser().parse_args(flags))


def test_a_table_is_one_target(tmp_path: Path) -> None:
    (target,) = read(tmp_path, SINGLE)
    assert target == GenerationTarget(
        schema_file="m.yaml", package="app.generated", typescript="web"
    ), "the table did not become one target"


def test_an_array_of_tables_is_one_target_per_entry(tmp_path: Path) -> None:
    targets = read(tmp_path, SEVERAL)
    assert [t.package for t in targets] == ["app.a", "app.b"], "entries lost or reordered"
    assert targets[1].python == "out/b", "a key of the second entry was lost"


def test_a_flag_overrides_the_only_entry(tmp_path: Path) -> None:
    (target,) = read(tmp_path, SINGLE, "--package", "other.pkg", "--diagrams-out", "docs")
    assert (target.package, target.diagrams) == ("other.pkg", "docs"), "flags did not apply"
    assert (target.schema_file, target.typescript) == ("m.yaml", "web"), (
        "flags clobbered other keys"
    )


def test_flags_alone_make_a_target_when_there_is_no_table(tmp_path: Path) -> None:
    (target,) = read(tmp_path, None, "--schema", "m.yaml", "--package", "p")
    assert target == GenerationTarget(schema_file="m.yaml", package="p"), (
        "flags did not make a target"
    )


@pytest.mark.parametrize(
    "flag",
    [flag.option for flag in cli_flags()][:2],  # one class: every flag takes the same path
)
def test_a_flag_with_several_entries_is_an_error_naming_it(tmp_path: Path, flag: str) -> None:
    with pytest.raises(ConfigError, match=flag):
        read(tmp_path, SEVERAL, flag, "x")


@pytest.mark.parametrize(
    ("toml", "flags", "message"),
    [
        (None, (), "no \\[tool.rp-generate\\]"),
        ("[tool.other]\nx = 1\n", (), "no \\[tool.rp-generate\\]"),
        ('[tool.rp-generate]\npackage = "p"\n', (), "schema"),
        ('[tool.rp-generate]\nschema = "m.yaml"\n', (), "package"),
        ('[tool.rp-generate]\nschema = "m.yaml"\npackage = "p"\ncolour = "red"\n', (), "colour"),
    ],
    ids=["no-file", "no-table", "no-schema", "no-package", "unknown-key"],
)
def test_a_bad_configuration_is_an_error_naming_the_problem(
    tmp_path: Path, toml: str | None, flags: tuple[str, ...], message: str
) -> None:
    with pytest.raises(ConfigError, match=message):
        read(tmp_path, toml, *flags)


def test_the_components_are_written_unless_an_entry_switches_them_off(tmp_path: Path) -> None:
    (default,) = read(tmp_path, SINGLE)
    (quiet,) = read(tmp_path, SINGLE + "openapi = false\n")
    assert (default.openapi, quiet.openapi) == (True, False), "on by default, off by the entry"


def test_the_regenerate_command_is_read_from_its_toml_key(tmp_path: Path) -> None:
    (named,) = read(tmp_path, SINGLE + 'regenerate-command = "make generate-models"\n')
    (unnamed,) = read(tmp_path, SINGLE)
    assert named.regenerate_command == "make generate-models", "the key was not read"
    assert unnamed.regenerate_command is None, "an absent key leaves the command unset"


def test_a_regenerate_command_that_is_not_a_string_is_an_error_naming_the_toml_key(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError, match="regenerate-command"):
        read(tmp_path, SINGLE + "regenerate-command = 3\n")


def test_a_kind_is_read_from_its_toml_key(tmp_path: Path) -> None:
    (technical,) = read(tmp_path, SINGLE + 'kind = "technical"\n')
    assert technical.target_kind == TargetKind.TECHNICAL, "the kind key was not read"


def test_the_toy_librarys_table_has_no_kind_and_passes_the_boundary_check() -> None:
    (toy,) = read_targets(TOY / "pyproject.toml")
    assert toy.target_kind is None, "an absent key leaves the kind unset"
    assert generate([toy], TOY, (steps.BOUNDARY_STEP,), check=True) == [], "no kind, no kind check"


@pytest.mark.parametrize(
    "literal",
    [
        '"access"',
        '"Technical"',
        '"TECHNICAL"',
        '" domain"',
        '"technical\\n"',
        '""',
        "1",
        "true",
        "[]",
    ],
)
def test_a_kind_that_is_not_exactly_domain_or_technical_is_an_error_naming_the_toml_key(
    tmp_path: Path, literal: str
) -> None:
    """Probe of PD-9: no case folding, no trimming, no coercion."""
    with pytest.raises(ConfigError, match="kind"):
        read(tmp_path, SINGLE + f"kind = {literal}\n")


def test_a_kind_spelt_target_kind_is_refused_naming_the_key(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="target_kind"):
        read(tmp_path, SINGLE + 'target_kind = "technical"\n')


def test_the_regenerate_command_is_not_a_flag() -> None:
    assert "regenerate_command" not in {f.field for f in cli_flags()}, (
        "it became an rp-generate flag"
    )


def test_a_regenerate_command_spelt_with_an_underscore_is_refused_naming_the_key(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError, match="regenerate_command"):
        read(tmp_path, SINGLE + 'regenerate_command = "make generate-models"\n')


def test_a_schema_file_spelt_with_an_underscore_is_refused_naming_the_key(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="schema_file"):
        read(tmp_path, SINGLE.replace('schema = "m.yaml"', 'schema_file = "m.yaml"'))


# "   " stands for blank ("" and "   " are one class; "   " also guards the whitespace in the pattern)
@pytest.mark.parametrize("command", ["   ", "make a\nmake b", "make `x`"])
def test_a_regenerate_command_that_is_blank_multiline_or_backticked_is_refused(
    tmp_path: Path, command: str
) -> None:
    with pytest.raises(ConfigError, match="regenerate-command"):
        read(tmp_path, SINGLE + f"regenerate-command = {json.dumps(command)}\n")


def test_make_generate_models_is_an_accepted_regenerate_command(tmp_path: Path) -> None:
    (target,) = read(tmp_path, SINGLE + 'regenerate-command = "make generate-models"\n')
    assert target.regenerate_command == "make generate-models", "a plain command was refused"


def test_the_regenerate_command_flag_is_refused_by_the_parser(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args(["--regenerate-command", "make x"])
    assert exit_info.value.code == 2, "the parser accepted --regenerate-command"
    assert "--regenerate-command" in capsys.readouterr().err, "the flag is not named"


def test_each_row_of_several_entries_keeps_its_own_regenerate_command(tmp_path: Path) -> None:
    first, second = read(
        tmp_path,
        SEVERAL.replace('package = "app.a"', 'package = "app.a"\nregenerate-command = "x"'),
    )
    assert (first.regenerate_command, second.regenerate_command) == ("x", None), "rows mixed up"


def test_a_row_with_the_aliased_keys_sets_the_fields(tmp_path: Path) -> None:
    """TC-45: `regenerate-command` is the model's own alias; `schema` is read through the key map (see the xfail)."""
    (target,) = read(tmp_path, SINGLE + 'regenerate-command = "make g"\n')
    assert (target.schema_file, target.regenerate_command) == ("m.yaml", "make g"), (
        "an aliased key did not set its field"
    )
    assert GenerationTarget.model_fields["regenerate_command"].alias == "regenerate-command", (
        "the alias is not declared in the schema (PD-10)"
    )


@pytest.mark.xfail(
    strict=True,
    reason="linkml 1.12.1 names a pydantic field by an alias that is an identifier: "
    "`alias: schema` would make a field `schema` shadowing a pydantic method (PD-10 diverges)",
)
def test_schema_and_kind_are_aliases_not_entries_of_a_key_map() -> None:
    """TC-45 (blocked): `schema` and `kind` as aliases of `schema_file` and `target_kind`."""
    aliases = {name: field.alias for name, field in GenerationTarget.model_fields.items()}
    assert (aliases["schema_file"], aliases["target_kind"]) == ("schema", "kind"), "no such alias"
    assert not hasattr(config, "FIELD_OF_TOML_KEY"), "the key map outlived the aliases"


def test_a_row_naming_a_field_whose_alias_differs_is_refused_with_todays_text(
    tmp_path: Path,
) -> None:
    """TC-46: `schema_file` is refused before validation, as an extra input."""
    with pytest.raises(ConfigError) as refused:
        read(tmp_path, SINGLE.replace('schema = "m.yaml"', 'schema_file = "a.yaml"'))
    assert "invalid entry: schema_file: Extra inputs are not permitted" in str(refused.value), (
        "the refusal changed its text"
    )


def test_a_bad_regenerate_command_names_the_alias_not_the_field(tmp_path: Path) -> None:
    """TC-47: the message names the TOML key `regenerate-command`."""
    with pytest.raises(ConfigError) as refused:
        read(tmp_path, SINGLE + "regenerate-command = 3\n")
    problem = str(refused.value).split("invalid entry:")[1]
    assert "regenerate-command:" in problem, "the alias is not named"
    assert "regenerate_command" not in problem, "the field name leaked into the message"
