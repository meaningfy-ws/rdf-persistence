"""Adversarial tests of the testkit target and the ``replaced`` sites (technical-models stage 4).

Attacks: the testkit imported without the extras, ``FieldFlags`` in the model-shape comparison, and the
three sites that rebuild a model with ``replaced``.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from rdf_persistence.testkit.generated.rp_testkit import ClassShape, FieldFlags, SlotShape
from rdf_persistence.testkit.model_shape import model_shape_diff

ROOT = Path(__file__).parents[3]
BLOCKED = ("linkml", "testcontainers", "pydantic_settings", "faststream")
PROBE = (
    "import sys\n"
    f"for name in {BLOCKED!r}:\n"
    "    sys.modules[name] = None\n"
    "import rdf_persistence.testkit.generated.rp_testkit\n"
    "import rdf_persistence.testkit\n"
    "import rdf_persistence.testkit.model_shape, rdf_persistence.testkit.shape_snapshot\n"
    "import rdf_persistence.testkit.guards, rdf_persistence.testkit.tokens, rdf_persistence.testkit.zitadel\n"
    "loaded = [m for m in ('rdf_persistence_generation', 'rdf_persistence_generation.generated.rp_generation') if m in sys.modules]\n"
    "assert not loaded, f'the testkit pulled in the generator: {loaded}'\n"
)


def test_the_testkit_imports_without_the_extras() -> None:
    """Tries to import the generated testkit module and the package with linkml, testcontainers, settings and faststream blocked."""
    done = subprocess.run(
        [sys.executable, "-c", PROBE], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr


def test_the_generated_testkit_module_imports_only_runtime_dependencies() -> None:
    """Tries the module's own imports: none outside pydantic, the standard library and the toolkit's domain."""
    source = (ROOT / "rdf_persistence/testkit/generated/rp_testkit.py").read_text()
    imported = {
        line.split()[1].split(".")[0]
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
    }
    allowed = {
        "__future__",
        "re",
        "sys",
        "datetime",
        "decimal",
        "enum",
        "typing",
        "pydantic",
        "rdf_persistence",
    }
    assert imported <= allowed, f"unexpected imports: {imported - allowed}"


class Plain(BaseModel):
    """A model of two fields."""

    name: str
    tags: list[str] = Field(default_factory=list)


def shape(required: bool, multivalued: bool, name: str = "name") -> ClassShape:
    return ClassShape(
        class_name="Plain",
        slots=[SlotShape(name=name, range="string", required=required, multivalued=multivalued)],
    )


def test_field_flags_equality_is_by_value() -> None:
    """Tries two FieldFlags built apart: equal by value, unequal when either flag differs."""
    assert FieldFlags(required=True, multivalued=False) == FieldFlags(
        required=True, multivalued=False
    )
    assert FieldFlags(required=True, multivalued=False) != FieldFlags(
        required=True, multivalued=True
    )


@pytest.mark.parametrize(
    ("required", "multivalued", "expected"),
    [(True, False, []), (False, False, ["required"]), (True, True, ["multivalued"])],
    ids=["same", "required-differs", "multivalued-differs"],
)
def test_the_model_shape_diff_names_each_differing_flag(
    required: bool, multivalued: bool, expected: list[str]
) -> None:
    """Tries each flag of the `name` field alone: one line naming the flag, none when they agree."""
    lines = model_shape_diff([shape(required, multivalued)], [Plain])
    named = [
        flag
        for flag in ("required", "multivalued")
        if any(f"{flag} " in line and "name" in line for line in lines)
    ]
    assert named == expected, lines


def test_both_flags_differing_give_two_lines_in_a_stable_order() -> None:
    """Tries a field wrong in both flags: required first, multivalued second, as the former code wrote them."""
    lines = [
        line for line in model_shape_diff([shape(False, True)], [Plain]) if "Plain.name" in line
    ]
    assert [("required" in line, "multivalued" in line) for line in lines] == [
        (True, False),
        (False, True),
    ], lines


def test_the_line_text_is_unchanged() -> None:
    """Tries the exact wording of a flag line, which consumers' snapshots may hold."""
    lines = model_shape_diff([shape(False, False)], [Plain])
    assert "field differs: Plain.name: required True in code, False in schema" in lines, lines
