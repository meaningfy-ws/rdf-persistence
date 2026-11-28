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
  main_part:
    title: Main part
    description: The main piece, one object.
    slot_uri: lib:mainPart
    range: Piece
    inlined: true
    annotations:
      owned: true
"""
NARROWED_USAGE = """\
    slot_usage:
      has_part:
        range: SubPart
        required: true
        multivalued: false
      counts:
        multivalued: false
        equals_number: 1
      main_part:
        range: SubPiece
"""
PIECE_CLASSES = """\
  Piece:
    title: Piece
    description: A piece, inlined in its holder.
    class_uri: lib:Piece
    mixins: [Described]
  SubPiece:
    title: Sub piece
    description: A narrower piece.
    class_uri: lib:SubPiece
    is_a: Piece
"""


def test_a_subclass_narrowing_a_list_slot_to_one_value_generates_a_package_mypy_accepts(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#417: an optional list in the parent, a required single value of a narrower range in the
    subclass (TC-1, TC-5); beside it a compatible covariant override, unmarked (#428 W2)."""
    classes = (
        root_class("Part")
        + root_class("SubPart", parent="Part")
        + PIECE_CLASSES
        + root_class("Holder", abstract=True)
        + "    slots: [has_part, counts, main_part]\n"
        + root_class("OnePartHolder", parent="Holder")
        + NARROWED_USAGE
    )
    pyproject = write_project(
        project, {"app_narrow": module("app_narrow", classes, slots=NARROWING_SLOTS)}
    )

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err

    text = (project / PACKAGE / "domain" / "generated" / "app_narrow.py").read_text()
    narrower = text[text.index("class OnePartHolder(") :]
    main_part = next(line for line in narrower.splitlines() if line.startswith("    main_part:"))
    assert "SubPiece" in main_part, f"the covariant override keeps its range: {main_part}"
    assert "# type: ignore" not in main_part, f"a covariant override is marked: {main_part}"
    assert mypy_output(project) == "", "the narrowed field is not marked for mypy"


KEYED_SLOTS = """\
slots:
  code:
    title: Code
    description: The code of a part.
    slot_uri: lib:code
    range: string
  parts:
    title: Parts
    description: The parts, a list.
    slot_uri: lib:parts
    range: Part
    multivalued: true
    inlined: true
    inlined_as_list: true
    annotations:
      owned: true
"""
PART_ID = "https://example.org/ns/library#p-1"
PART_CLASS = """\
  Part:
    title: Part
    description: A part, inlined in its holder, one per code.
    class_uri: lib:Part
    mixins: [Described]
    slots: [code]
    unique_keys:
      by_code:
        unique_key_slots: [code]
"""
KEYED_CLASSES = (
    PART_CLASS
    + root_class("KeyedHolder")
    + "    slots: [parts]\n"
    + root_class("OneKeyedHolder", parent="KeyedHolder")
    + "    slot_usage:\n      parts:\n        required: true\n        multivalued: false\n"
    + root_class("OptionalOneKeyedHolder", parent="KeyedHolder")
    + "    slot_usage:\n      parts:\n        multivalued: false\n"
)


def test_a_narrowed_keyed_slot_validates_one_value_and_a_list_still_refuses_a_repeated_key(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#417 (TC-4): the unique-key validator the subclass inherits reads a single value as a one-item list."""
    pyproject = write_project(
        project, {"app_keyed": module("app_keyed", KEYED_CLASSES, slots=KEYED_SLOTS)}
    )

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err

    keyed = generated("app_keyed")
    one = keyed.OneKeyedHolder(
        id="https://example.org/ns/library#k-1",
        label="K",
        parts=keyed.Part(id=PART_ID, label="P", code="a"),
    )
    assert one.parts.code == "a", "the narrowed holder validates one part"
    none = keyed.OptionalOneKeyedHolder(id="https://example.org/ns/library#k-0", label="K")
    assert none.parts is None, "an absent narrowed keyed slot validates (#428 S2)"
    parts = [keyed.Part(id=PART_ID, label="P", code="a") for _ in range(2)]
    with pytest.raises(ValueError, match="unique_keys by_code"):
        keyed.KeyedHolder(id="https://example.org/ns/library#k-2", label="K", parts=parts)
    assert mypy_output(project) == "", "the generated package is mypy-clean"


DICT_KEYED_SLOTS = """\
slots:
  code:
    title: Code
    description: The code of a part.
    slot_uri: lib:code
    range: string
  parts_by_id:
    title: Parts by id
    description: The parts, keyed by their identifier.
    slot_uri: lib:partsById
    range: Part
    multivalued: true
    inlined: true
    annotations:
      owned: true
"""
DICT_KEYED_CLASSES = PART_CLASS + root_class("DictKeyedHolder") + "    slots: [parts_by_id]\n"


def test_a_keyed_slot_rendered_as_a_dict_checks_its_values(
    project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """#428 S1: a multivalued inlined slot over a class with an identifier, no ``inlined_as_list``,
    is a dict; its unique-key check reads the dict's values (PD-1)."""
    pyproject = write_project(
        project,
        {"app_dict": module("app_dict", DICT_KEYED_CLASSES, slots=DICT_KEYED_SLOTS)},
    )

    assert main(["--project", str(pyproject)]) == 0, capsys.readouterr().err

    text = (project / PACKAGE / "domain" / "generated" / "app_dict.py").read_text()
    field = next(line for line in text.splitlines() if line.startswith("    parts_by_id:"))
    assert "dict[" in field, f"LinkML renders the slot as a dict (RISK-1): {field}"
    keyed = generated("app_dict")

    def holder(*codes: str) -> object:
        parts = {
            f"{PART_ID}-{n}": keyed.Part(id=f"{PART_ID}-{n}", label="P", code=code)
            for n, code in enumerate(codes)
        }
        return keyed.DictKeyedHolder(
            id="https://example.org/ns/library#d-1", label="D", parts_by_id=parts
        )

    assert holder().parts_by_id == {}, "an empty dict validates"
    assert len(holder("a", "b").parts_by_id) == 2, "two parts of different codes validate"
    with pytest.raises(ValueError, match="unique_keys by_code"):
        holder("a", "a")
    assert mypy_output(project) == "", "the generated package is mypy-clean"
