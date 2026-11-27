"""The generated Python imports and type-checks whatever the schema's class names and module split (#242, #243).

#242: a class whose ``is_a`` parent is in another module got the parent as its last base, after
the mixins the parent already has, so the module failed to import (no consistent MRO).
#243: a class named after a name the generated module imports (``Field``, ``Optional``,
``BaseModel``) rebound it, so every later class called the model instead of ``pydantic.Field``.
"""

import importlib
import pkgutil
from pathlib import Path

import pytest

from rdf_persistence_generation.cli import main
from rdf_persistence_generation.uml.cli import main as uml2linkml
from tests.generator import uml_library_stage2

from .generated_project import (
    PACKAGE,
    generated,
    module,
    mypy_output,
    root_class,
    write_project,
    write_target,
)


def test_a_converted_qea_model_generates_a_package_whose_every_module_imports_and_type_checks(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole path, end to end: rp-uml2linkml, then rp-generate, then the generated package."""
    project.mkdir()
    converted = uml2linkml(
        [
            str(uml_library_stage2.build_library(tmp_path)),
            "--package",
            uml_library_stage2.PACKAGE,
            "--prefixes",
            str(uml_library_stage2.write_prefixes(tmp_path)),
            "--out",
            str(project),
            "--root-name",
            uml_library_stage2.ROOT_NAME,
        ]
    )
    assert converted == 0, capsys.readouterr().err
    pyproject = write_target(project, uml_library_stage2.ROOT_NAME)

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err
    assert main(["--check", "--project", str(pyproject)]) == 0, capsys.readouterr().err

    package = importlib.import_module(f"{PACKAGE}.domain.generated")
    modules = [info.name for info in pkgutil.iter_modules(package.__path__)]
    assert modules, "the converted model generated no module"
    for name in modules:
        assert generated(name), f"{name} does not import"


def test_the_check_type_checks_the_generated_package_and_names_the_module_and_the_error(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    pyproject = write_project(project, {"app_typed": module("app_typed", root_class("Ledger"))})
    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err
    written = project / PACKAGE / "domain" / "generated" / "app_typed.py"
    written.write_text(written.read_text() + '\nCOUNT: int = "one"\n')

    code = main(["--check", "--project", str(pyproject)])

    error = capsys.readouterr().err
    assert code == 1, "a generated module with a type error passed the check"
    assert "type check" in error, error
    assert "app_typed.py" in error, "the module is not named"
    assert "Incompatible types in assignment" in error, "mypy's error is not given"
    assert not list(project.rglob(".mypy_cache")), "the check wrote mypy's cache into the project"


def test_a_root_subclass_whose_parent_is_in_another_module_has_the_parent_first_and_imports(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = module(
        "app_base",
        root_class("Edition", abstract=True) + root_class("PrintEdition", parent="Edition"),
    )
    more = module("app_more", root_class("EbookEdition", parent="Edition"), imports=("app_base",))
    pyproject = write_project(project, {"app_base": base, "app_more": more})

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err

    edition = generated("app_base").Edition
    ebook = generated("app_more").EbookEdition
    assert ebook.__bases__[0] is edition, "the is_a parent is the first base, as in its own module"
    assert isinstance(ebook(id="https://example.org/ns/library#e-1", label="E"), edition)


# A class named `datetime` is refused by the lint (standard_naming), and a generated class name is
# always camel case, so only a capitalised name can shadow one: `Datetime` stands in for it.
# `Decimal` is also a slot's type and `Enum` the base of the module's enum.
SHADOWING_NAMES = ("Field", "Optional", "BaseModel", "Datetime", "Decimal", "Enum")
FOLLOWER_SLOTS = """\
slots:
  amount:
    title: Amount
    description: An amount, a decimal.
    slot_uri: lib:amount
    range: decimal
  colour:
    title: Colour
    description: A colour, from an enumeration.
    slot_uri: lib:colour
    range: Colour
enums:
  Colour:
    title: Colour
    description: The colours.
    enum_uri: lib:Colour
    permissible_values:
      red:
        title: Red
        description: Red.
        meaning: lib:red
"""


def follower(name: str) -> str:
    return root_class(name) + "    slots: [amount, colour]\n"


def test_classes_named_after_the_names_a_generated_module_imports_import_validate_and_type_check(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    classes = "".join(root_class(name) + follower(f"After{name}") for name in SHADOWING_NAMES)
    named_module = module("app_named", classes, slots=FOLLOWER_SLOTS)
    pyproject = write_project(project, {"app_named": named_module})

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err

    named = generated("app_named")
    for name in SHADOWING_NAMES:
        shadowing = getattr(named, name)(id=f"https://example.org/ns/library#{name}", label=name)
        after = getattr(named, f"After{name}")(
            id=f"https://example.org/ns/library#after-{name}",
            label=name,
            amount="1.5",
            colour="red",
        )
        assert shadowing.label == name, f"{name} validates"
        assert (str(after.amount), after.colour) == ("1.5", "red"), f"After{name} validates"
    assert mypy_output(project) == "", "the generated module is mypy-clean"


NARROWING_SLOTS = """\
slots:
  has_part:
    title: Has part
    description: The parts, a list.
    slot_uri: lib:hasPart
    range: Part
    multivalued: true
  counts:
    title: Counts
    description: The counts, a list.
    slot_uri: lib:counts
    range: integer
    multivalued: true
"""
NARROWED_USAGE = """\
    slot_usage:
      has_part:
        required: true
        multivalued: false
      counts:
        multivalued: false
        equals_number: 1
"""


def test_a_subclass_narrowing_a_list_slot_to_one_value_generates_a_package_mypy_accepts(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#417: an optional list in the parent, a required single value in the subclass (TC-1, TC-5)."""
    classes = (
        root_class("Part")
        + root_class("Holder", abstract=True)
        + "    slots: [has_part, counts]\n"
        + root_class("OnePartHolder", parent="Holder")
        + NARROWED_USAGE
    )
    pyproject = write_project(
        project, {"app_narrow": module("app_narrow", classes, slots=NARROWING_SLOTS)}
    )

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err

    assert mypy_output(project) == "", "the narrowed field is not marked for mypy"
