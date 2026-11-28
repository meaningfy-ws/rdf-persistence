"""A consumer's technical module extends the toolkit's ``Problem`` (consumer-write-rules PD-1a to PD-4, PD-9).

The toy's ``library_problems`` declares ``HeldKeyProblem`` (``is_a: Problem``). Its Python class
inherits ``rdf_persistence.Problem``, its TypeScript interface holds every field of ``Problem`` (so
it is assignable to it), a class the package does not export is refused, and so is a slot that
shadows a field of the toolkit class.
"""

import ast
import re
from collections import Counter
from pathlib import Path

import pytest

import rdf_persistence
from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence.testkit import assert_public_imports
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.extensions import pydantic_split, typescript
from rdf_persistence_generation.generated.rp_generation import TsInterface, TsModule

from .golden import TOY, Breaker

TECHNICAL_SCHEMA = "services/loan_checks_response.yaml"
PROBLEMS_MODULE = "services/library_problems.yaml"
PROBLEM_MODULE = "rp_api_entrypoints"
SERVICES_PYTHON = "services/generated"
CLASS_LINE = re.compile(r"^class (\w+)\(", re.MULTILINE)
INTERFACE_LINE = re.compile(r"^export interface (\w+)", re.MULTILINE)
SLOTS_LINE = "    slots:\n      - holder\n"
SHADOW_SLOTS = "    slots:\n      - holder\n      - kind\n"
SLOT_HOLDER = "slots:\n  holder:\n"
SHADOW_DEFINITION = (
    "slots:\n  kind:\n    title: Kind\n    description: A kind.\n    slot_uri: lib:kind\n"
    "    alias: type\n    range: uri\n  holder:\n"
)
NARROWED = (
    "    slot_usage:\n      problem_status:\n        minimum_value: 400\n"
    "      holder:\n        required: true\n"
)
CLASSES_END = "    slot_usage:\n      holder:\n        required: true\n"


def duplicate_modules(path: Path) -> int:
    """How many modules the closure of ``path`` loads again under another import string."""
    view = load_schema(path)
    view.imports_closure()
    names = [schema.name for schema in view.schema_map.values()]
    return len(names) - len(set(names))


def interfaces(path: Path) -> dict[str, TsInterface]:
    """The toolkit generator's interfaces over the schema at ``path``, by name."""
    modules: list[TsModule] = typescript._generator(path).modules()
    return {each.name: each for module in modules for each in module.interfaces}


# --- TC-1b: one schema under two import names ----------------------------------------------------


def test_the_closure_of_the_toy_adds_no_duplicate_module() -> None:
    own = duplicate_modules(TOY / TECHNICAL_SCHEMA)
    toolkit = duplicate_modules(
        Path(rdf_persistence.__file__).parent / "model/technical/api/rp_api_entrypoints.yaml"
    )
    # A metamodel module the toy's root imports by its package key is loaded once more (D-19).
    direct = [
        each
        for each in load_schema(TOY / TECHNICAL_SCHEMA).schema.imports
        if each.startswith("rdf_persistence/model/rp_")
    ]

    assert own <= toolkit + len(direct), (
        f"the toy's closure repeats {own} modules, the toolkit's {toolkit}"
    )


def test_each_typescript_module_and_interface_is_written_once() -> None:
    files = typescript.render(TOY / TECHNICAL_SCHEMA)

    names = Counter(file.name for file in files)
    declared = Counter(name for file in files for name in INTERFACE_LINE.findall(file.text))
    assert {name for name, count in names.items() if count > 1} == set(), "a module file repeats"
    assert {name for name, count in declared.items() if count > 1} == set(), "an interface repeats"
    assert declared["HeldKeyProblem"] == 1, "the consumer's interface is not written"


def test_each_python_module_and_class_is_written_once() -> None:
    files = pydantic_split.render(TOY / TECHNICAL_SCHEMA)

    names = Counter(file.name for file in files)
    declared = Counter(name for file in files for name in CLASS_LINE.findall(file.text))
    assert {name for name, count in names.items() if count > 1} == set(), "a module file repeats"
    assert {name for name, count in declared.items() if count > 1} == set(), "a class repeats"
    assert declared["HeldKeyProblem"] == 1, "the consumer's class is not generated"


# --- TC-2: the Python class ----------------------------------------------------------------------


def test_the_generated_module_imports_problem_from_the_package(tmp_path: Path) -> None:
    files = {file.name: file.text for file in pydantic_split.render(TOY / TECHNICAL_SCHEMA)}
    module = tmp_path / "library_problems.py"
    module.write_text(files["library_problems.py"], encoding="utf-8")

    assert_public_imports(module)
    assert "from rdf_persistence import" in files["library_problems.py"], (
        "Problem is not imported from the public package"
    )
    assert "rdf_persistence.api" not in files["library_problems.py"], "a deep import of the toolkit"


def test_the_root_imports_only_names_the_package_exports() -> None:
    files = {file.name: file.text for file in pydantic_split.render(TOY / TECHNICAL_SCHEMA)}

    for name, text in files.items():
        imported = {
            each
            for node in ast.walk(ast.parse(text))
            if isinstance(node, ast.ImportFrom) and node.module == "rdf_persistence"
            for each in (alias.name for alias in node.names)
        }
        assert imported <= set(rdf_persistence.__all__), (
            f"{name} imports what the package does not export: "
            f"{sorted(imported - set(rdf_persistence.__all__))}"
        )


def test_the_generated_class_inherits_the_toolkit_problem() -> None:
    from tests.fixtures.library.services.generated.library_problems import HeldKeyProblem

    assert issubclass(HeldKeyProblem, rdf_persistence.Problem), "not a Problem"
    problem = HeldKeyProblem(
        type="https://example.org/held",
        title="Held",
        status=409,
        holder="https://example.org/book/1",
    )
    assert problem.model_dump(exclude_none=True)["holder"] == "https://example.org/book/1", (
        "the extra field is not dumped"
    )


# --- TC-3, TC-3b: what generation refuses --------------------------------------------------------


def test_a_class_the_package_does_not_export_is_refused(toy_copy: Path, break_toy: Breaker) -> None:
    break_toy(PROBLEMS_MODULE, "is_a: Problem", "is_a: InUseProblem")

    with pytest.raises(SchemaGenerationError) as refused:
        pydantic_split.render(toy_copy / TECHNICAL_SCHEMA)

    text = str(refused.value)
    assert "HeldKeyProblem" in text, "the consumer class is not named"
    assert "InUseProblem" in text, "the toolkit class is not named"
    assert PROBLEM_MODULE in text, "the toolkit module is not named"


def test_a_slot_that_shadows_a_field_of_the_toolkit_class_is_refused(
    toy_copy: Path, break_toy: Breaker
) -> None:
    break_toy(PROBLEMS_MODULE, SLOTS_LINE, SHADOW_SLOTS)
    break_toy(PROBLEMS_MODULE, SLOT_HOLDER, SHADOW_DEFINITION)

    with pytest.raises(SchemaGenerationError) as refused:
        pydantic_split.render(toy_copy / TECHNICAL_SCHEMA)

    assert "HeldKeyProblem.kind shadows Problem.type" in str(refused.value), (
        "the shadowing slot and the shadowed field are not named"
    )


def test_narrowing_the_inherited_slot_is_allowed(toy_copy: Path, break_toy: Breaker) -> None:
    break_toy(PROBLEMS_MODULE, CLASSES_END, NARROWED)

    files = pydantic_split.render(toy_copy / TECHNICAL_SCHEMA)

    assert "library_problems.py" in {file.name for file in files}, (
        "the narrowed class is not written"
    )


# --- TC-4: the TypeScript interface is assignable to Problem -------------------------------------


def test_the_interface_holds_every_field_of_problem_as_problem_has_it() -> None:
    found = interfaces(TOY / PROBLEMS_MODULE)
    problem = {each.name: each for each in found["Problem"].fields}
    held = {each.name: each for each in found["HeldKeyProblem"].fields}

    assert set(problem) <= set(held), f"fields missing: {sorted(set(problem) - set(held))}"
    for name, field in problem.items():
        assert held[name].type == field.type, f"{name} has another type"
        assert field.optional or not held[name].optional, f"{name} was required and is optional"
    assert held["holder"].optional is False, "the holder is required"
