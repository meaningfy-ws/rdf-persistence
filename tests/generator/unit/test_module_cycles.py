"""The import cycles among generated modules, and which imported names a module may defer (PD-1 to PD-4)."""

import pytest

from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.generated.rp_generation import CycleAnalysis
from rdf_persistence_generation.module_cycles import (
    analyse,
    cycle_components,
    deferred_by_module,
    modules_in_cycles,
)


def _cycles(result: CycleAnalysis) -> list[list[str]]:
    return [cycle.modules for cycle in result.cycles or []]


def _deferred(result: CycleAnalysis, module: str) -> dict[str, tuple[str, ...]]:
    return deferred_by_module(result).get(module, {})


def test_two_modules_that_import_each_other_are_one_cycle() -> None:
    result = analyse(
        {
            "app_a": "from .app_b import B\n\nclass A:\n    b: B\n",
            "app_b": "from .app_a import A\n\nclass B:\n    a: A\n",
        }
    )

    assert _cycles(result) == [["app_a", "app_b"]]
    assert modules_in_cycles(result) == frozenset({"app_a", "app_b"})


def test_a_name_used_only_in_annotations_is_deferred() -> None:
    result = analyse(
        {
            "app_a": "from .app_b import B\n\nclass A:\n    b: Optional[B] = None\n",
            "app_b": "from .app_a import A\n\nclass B:\n    a: Optional[A] = None\n",
        }
    )

    assert _deferred(result, "app_a") == {"app_b": ("B",)}
    assert _deferred(result, "app_b") == {"app_a": ("A",)}


def test_a_base_class_from_the_cycle_is_needed_at_load() -> None:
    result = analyse(
        {
            "app_a": "from .app_b import Base\n\nclass Child(Base):\n    pass\n",
            "app_b": "from .app_a import Child\n\nclass Holder:\n    child: Child\n",
        }
    )

    assert _deferred(result, "app_a") == {}
    assert _deferred(result, "app_b") == {"app_a": ("Child",)}


def test_a_default_factory_and_a_union_alias_are_needed_at_load() -> None:
    result = analyse(
        {
            "app_a": (
                "from .app_b import B, C, D\n\n"
                "class A:\n    b: B = Field(default_factory=B)\n    d: D\n\n"
                "Either = Union[C, int]\n"
            ),
            "app_b": "from .app_a import A\n\nclass B:\n    a: A\n",
        }
    )

    assert _deferred(result, "app_a") == {"app_b": ("D",)}
    assert _deferred(result, "app_b") == {"app_a": ("A",)}


def test_an_imported_name_never_used_is_deferred() -> None:
    result = analyse(
        {
            "app_a": "from .app_b import B\n\nclass A:\n    x: Optional[str] = None\n",
            "app_b": "from .app_a import A\n\nclass B:\n    a: A\n",
        }
    )

    assert _deferred(result, "app_a") == {"app_b": ("B",)}


def test_a_name_used_in_a_function_body_is_deferred() -> None:
    result = analyse(
        {
            "app_a": (
                "from .app_b import B\n\nclass A:\n    def check(self):\n        return B()\n"
            ),
            "app_b": "from .app_a import A\n\nclass B:\n    a: A\n",
        }
    )

    assert _deferred(result, "app_a") == {"app_b": ("B",)}


def test_a_load_cycle_is_refused_naming_the_modules_and_the_classes() -> None:
    texts = {
        "app_a": "from .app_b import Base\n\nclass Child(Base):\n    pass\n\nclass Root:\n    pass\n",
        "app_b": "from .app_a import Root\n\nclass Base:\n    pass\n\nclass Other(Root):\n    pass\n",
    }

    with pytest.raises(SchemaGenerationError) as error:
        analyse(texts)

    message = str(error.value)
    for text in ("app_a", "app_b", "app_a.Root", "app_b.Base"):
        assert text in message


def test_a_half_load_cycle_is_accepted() -> None:
    result = analyse(
        {
            "app_a": "from .app_b import Base\n\nclass Child(Base):\n    pass\n\nclass Root:\n    pass\n",
            "app_b": "from .app_a import Root\n\nclass Base:\n    pass\n\nclass Holder:\n    r: Optional[Root]\n",
        }
    )

    assert _cycles(result) == [["app_a", "app_b"]]
    assert _deferred(result, "app_a") == {}
    assert _deferred(result, "app_b") == {"app_a": ("Root",)}


def test_modules_in_no_cycle_have_nothing_deferred() -> None:
    result = analyse(
        {
            "app_a": "from .app_b import B\n\nclass A:\n    b: B\n",
            "app_b": "class B:\n    pass\n",
        }
    )

    assert _cycles(result) == []
    assert modules_in_cycles(result) == frozenset()
    assert deferred_by_module(result) == {}


def test_an_absolute_import_is_not_an_edge() -> None:
    result = analyse(
        {
            "app_a": "from other.app_b import B\n\nclass A:\n    b: B\n",
            "app_b": "from .app_a import A\n\nclass B:\n    a: A\n",
        }
    )

    assert _cycles(result) == []


def test_the_component_search_works_over_any_sortable_nodes() -> None:
    edges = {1: {2}, 2: {3}, 3: {1}, 4: {1}}

    assert cycle_components([1, 2, 3, 4], edges) == [[1, 2, 3]]
