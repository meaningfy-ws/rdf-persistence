"""The [tool.rp-generate] configuration (PD-18) becomes GenerationTarget models."""

from pathlib import Path

import pytest

from rdf_persistence.generation.cli import build_parser
from rdf_persistence.generation.config import cli_flags, read_targets
from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import GenerationTarget

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


@pytest.mark.parametrize("flag", [flag.option for flag in cli_flags()])
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
    assert unnamed.regenerate_command is None, "an absent key is not None"


def test_a_regenerate_command_that_is_not_a_string_is_an_error_naming_the_toml_key(
    tmp_path: Path,
) -> None:
    with pytest.raises(ConfigError, match="regenerate-command"):
        read(tmp_path, SINGLE + "regenerate-command = 3\n")


def test_the_regenerate_command_is_not_a_flag() -> None:
    assert "regenerate_command" not in {f.field for f in cli_flags()}, "it became an rp-generate flag"
