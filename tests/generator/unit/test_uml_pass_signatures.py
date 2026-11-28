"""PD-19a: the new passes take arguments and return values, never a ``Context``.

The five functions of PD-19 are inspected by their annotations and called with empty, hand-built
inputs. A pass that a later task adds (1.7, stage 2) is skipped until its module has it, so this
file is green alone and starts to bind the day the function lands.
"""

import importlib
import inspect
import types
import typing
from collections.abc import Collection, Mapping
from typing import Any

import pytest

from rdf_persistence_generation.generated import rp_generation

PASSES = [
    ("rdf_persistence_generation.uml.aggregates", "package_kinds"),
    ("rdf_persistence_generation.uml.aggregates", "derive_aggregates"),
    ("rdf_persistence_generation.uml.aggregates", "check_pointers"),
    ("rdf_persistence_generation.uml.conventions", "convention_lines"),
    ("rdf_persistence_generation.uml.conventions", "missing_notes"),
]
PLAIN = (int, str, bool)
CONTAINERS = (list, Mapping, dict, Collection, set, frozenset, tuple)


def _find(module: str, name: str) -> Any:
    try:
        found = getattr(importlib.import_module(module), name, None)
    except ModuleNotFoundError:
        found = None
    if found is None:
        pytest.skip(f"{module}.{name} arrives in a later task")
    return found


def _leaves(hint: Any) -> list[Any]:
    """The classes a hint is made of, containers and unions opened."""
    origin = typing.get_origin(hint)
    if origin is None:
        return [hint] if hint is not type(None) else []
    if origin in CONTAINERS or origin in (typing.Union, types.UnionType):
        return [leaf for arg in typing.get_args(hint) for leaf in _leaves(arg)]
    return [hint]


def _is_generated(leaf: Any) -> bool:
    return inspect.isclass(leaf) and leaf.__module__ == rp_generation.__name__


def _is_usage(leaf: Any) -> bool:
    return inspect.isclass(leaf) and leaf.__name__ == "Usage"


def _empty(hint: Any) -> Any:
    origin = typing.get_origin(hint)
    if origin in (typing.Union, types.UnionType):
        return _empty(typing.get_args(hint)[0])
    if origin in (list, Collection):
        return []
    if origin in (Mapping, dict):
        return {}
    if origin in (set, frozenset):
        return set()
    return hint()


@pytest.fixture(params=PASSES, ids=lambda each: each[1])
def a_pass(request: pytest.FixtureRequest) -> Any:
    return _find(*request.param)


def test_no_pass_takes_a_context(a_pass: Any) -> None:
    hints = typing.get_type_hints(a_pass)
    names = {leaf.__name__ for hint in hints.values() for leaf in _leaves(hint)}
    assert "Context" not in names, f"{a_pass.__name__} is annotated with Context"


def test_parameters_are_records_usages_or_plain_values(a_pass: Any) -> None:
    hints = typing.get_type_hints(a_pass)
    hints.pop("return")
    assert hints, f"{a_pass.__name__} takes no argument"
    for name, hint in hints.items():
        for leaf in _leaves(hint):
            ok = _is_generated(leaf) or _is_usage(leaf) or leaf in PLAIN
            assert ok, (
                f"{a_pass.__name__}({name}) is {leaf}: not a record, a Usage or a plain value"
            )


def test_the_result_is_a_record_a_mapping_or_a_list_of_records(a_pass: Any) -> None:
    result = typing.get_type_hints(a_pass)["return"]
    leaves = _leaves(result)
    assert leaves, f"{a_pass.__name__} returns nothing"
    for leaf in leaves:
        assert _is_generated(leaf) or leaf in PLAIN, f"{a_pass.__name__} returns {leaf}"
    if typing.get_origin(result) is None:
        assert _is_generated(result), f"{a_pass.__name__} returns {result}, not a record"


def test_a_pass_runs_on_empty_hand_built_inputs(a_pass: Any) -> None:
    hints = typing.get_type_hints(a_pass)
    hints.pop("return")
    arguments = {name: _empty(hint) for name, hint in hints.items()}
    outcome = a_pass(**arguments)
    assert outcome is not None, f"{a_pass.__name__} returned nothing"
    expected = (
        typing.get_origin(typing.get_type_hints(a_pass)["return"])
        or typing.get_type_hints(a_pass)["return"]
    )
    assert isinstance(outcome, expected), f"{a_pass.__name__} returned {type(outcome)}"
