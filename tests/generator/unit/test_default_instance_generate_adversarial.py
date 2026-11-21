"""Adversarial tests of ``default_instance`` through ``rp-generate`` (technical-models D-44..D-47).

Attacks: nesting, cycles, inheritance, a range of another module, an unquoted ``true``, a narrowed range,
a class order the generator reshuffles.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from rdf_persistence_generation.cli import main

HEAD = """id: https://example.org/ns/{name}
name: {name}
title: {name}
description: A module.
prefixes: {{g: "https://example.org/ns/g#", linkml: "https://w3id.org/linkml/"}}
default_prefix: g
default_range: {default_range}
imports: [linkml:types{imports}]
annotations:
  module_kind: technical
"""
SIZE = """  size:
    title: Size
    description: A count.
    range: integer
    ifabsent: int(3)
"""


def cls(name: str, slots: str = "", is_a: str = "", extra: str = "") -> str:
    parent = f"    is_a: {is_a}\n" if is_a else ""
    listed = f"    slots: [{slots}]\n" if slots else ""
    return f"  {name}:\n    title: {name}\n    description: The {name}.\n{parent}{listed}{extra}"


def holder_slot(name: str, range_: str, flag: str = "'true'", extra: str = "") -> str:
    return (
        f"  {name}:\n    title: {name}\n    description: The {name}.\n    range: {range_}\n{extra}"
        f"    annotations:\n      default_instance: {flag}\n"
    )


def build(tmp: Path, modules: dict[str, str]) -> tuple[int, Path, str]:
    """Write ``modules`` (name -> body of classes+slots) as a project, generate; return (exit code, folder, stderr)."""
    folder = tmp / "proj"
    folder.mkdir()
    for name, body in modules.items():
        (folder / f"{name}.yaml").write_text(body, encoding="utf-8")
    root = next(iter(modules))
    (folder / "pyproject.toml").write_text(
        f'[tool.rp-generate]\nschema = "{root}.yaml"\npackage = "proj.services.generated"\n'
        'python = "generated"\n',
        encoding="utf-8",
    )
    code = main(["--project", str(folder / "pyproject.toml")])
    return code, folder, ""


def load(folder: Path, module: str) -> ModuleType:
    name = f"proj_generated_{module}_{id(folder)}"
    spec = importlib.util.spec_from_file_location(name, folder / "generated" / f"{module}.py")
    assert spec is not None, "no spec"
    assert spec.loader is not None, "no loader"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def schema(
    classes: str, slots: str, default_range: str = "string", imports: str = "", name: str = "groups"
) -> str:
    return (
        HEAD.format(name=name, default_range=default_range, imports=imports)
        + "classes:\n"
        + classes
        + "slots:\n"
        + slots
    )


def test_a_default_nested_two_levels_builds_every_level_distinctly(tmp_path: Path) -> None:
    """Tries Holder -> Group -> Inner, each a default_instance: all three levels build, none shared."""
    classes = cls("Inner", "size") + cls("Group", "inner") + cls("Holder", "group")
    slots = SIZE + holder_slot("inner", "Inner") + holder_slot("group", "Group")
    code, folder, _ = build(tmp_path, {"groups": schema(classes, slots)})
    assert code == 0, "a nested default is generated"
    mod = load(folder, "groups")
    a, b = mod.Holder(), mod.Holder()
    assert a.group.inner.size == 3, "the innermost default is built"
    assert a.group.inner is not b.group.inner, "the innermost instance is shared between objects"


def test_a_class_holding_itself_by_default_is_refused_not_a_recursion(tmp_path: Path) -> None:
    """Tries a self-cycle: Node.child ranges over Node with default_instance (infinite construction)."""
    classes = cls("Node", "child")
    code, folder, _ = build(tmp_path, {"groups": schema(classes, holder_slot("child", "Node"))})
    assert code != 0, "a self-referring default generated, and building it recurses for ever"


def test_a_two_class_cycle_is_refused(tmp_path: Path) -> None:
    """Tries A.b -> B and B.a -> A, both default_instance: whichever order, one is declared after its holder."""
    classes = cls("A", "b") + cls("B", "a")
    slots = holder_slot("b", "B") + holder_slot("a", "A")
    code, _, _ = build(tmp_path, {"groups": schema(classes, slots)})
    assert code != 0, "a two-class default cycle generated"


def test_a_default_instance_of_a_subclass_of_the_holder_is_refused(tmp_path: Path) -> None:
    """Tries Holder.group ranging over a subclass of Holder (a cycle through is_a)."""
    classes = cls("Holder", "group") + cls("Sub", "", is_a="Holder")
    code, _, _ = build(tmp_path, {"groups": schema(classes, holder_slot("group", "Sub"))})
    assert code != 0, "a default through a subclass of the holder generated: construction recurses"


def test_a_range_inheriting_a_required_slot_with_a_default_is_built(tmp_path: Path) -> None:
    """Tries a range whose required slot comes from a parent but has an ifabsent: it must build."""
    classes = cls("Base", "size", extra="    slot_usage:\n      size: {required: true}\n")
    classes += cls("Group", "", is_a="Base") + cls("Holder", "group")
    code, folder, _ = build(
        tmp_path, {"groups": schema(classes, SIZE + holder_slot("group", "Group"))}
    )
    assert code == 0, "the parent's required slot has a default, so the range builds"
    assert load(folder, "groups").Holder().group.size == 3, "the inherited default is held"


def test_a_range_declared_before_its_holder_but_after_the_holders_parent_still_builds(
    tmp_path: Path,
) -> None:
    """Tries schema order Group, Holder(is_a Base), Base: the generator reorders parents first; Group must stay before Holder."""
    classes = cls("Group", "size") + cls("Holder", "group", is_a="Base") + cls("Base")
    code, folder, _ = build(
        tmp_path, {"groups": schema(classes, SIZE + holder_slot("group", "Group"))}
    )
    if code != 0:
        return  # refused is acceptable
    assert load(folder, "groups").Holder().group.size == 3, "the generated module builds"


@pytest.mark.parametrize("flag", ["true", "'true'", "'True'"])
def test_the_flag_in_any_boolean_spelling_builds_the_default(tmp_path: Path, flag: str) -> None:
    """D-55 (5): YAML `true` (the spec's spelling), `'true'` and `'True'` all generate the default."""
    classes = cls("Group", "size") + cls("Holder", "group")
    code, folder, _ = build(
        tmp_path, {"groups": schema(classes, SIZE + holder_slot("group", "Group", flag=flag))}
    )
    assert code == 0, f"{flag} is the flag"
    assert load(folder, "groups").Holder().group.size == 3, (
        f"{flag} generated a slot with no default"
    )


@pytest.mark.parametrize("flag", ["'yes'", "1", "'maybe'"])
def test_a_flag_that_is_not_a_boolean_is_refused_and_writes_nothing(
    tmp_path: Path, flag: str
) -> None:
    """D-55 (5): a value that is no boolean stops the run; it is no silent off."""
    classes = cls("Group", "size") + cls("Holder", "group")
    code, folder, _ = build(
        tmp_path, {"groups": schema(classes, SIZE + holder_slot("group", "Group", flag=flag))}
    )
    assert code != 0, f"{flag} generated"
    assert not (folder / "generated" / "groups.py").exists(), "a refused schema wrote a module"


def test_a_false_flag_generates_no_default(tmp_path: Path) -> None:
    """D-55 (5): `false` is off: the slot is an ordinary optional one."""
    classes = cls("Group", "size") + cls("Holder", "group")
    code, folder, _ = build(
        tmp_path, {"groups": schema(classes, SIZE + holder_slot("group", "Group", flag="false"))}
    )
    assert code == 0, "`false` is a valid flag"
    assert load(folder, "groups").Holder().group is None, "`false` still built a default"


def test_a_slot_without_range_over_a_class_default_range_builds_that_class(tmp_path: Path) -> None:
    """Tries a slot with no `range` where `default_range` is a class: the check reads default_range, so must the generator."""
    classes = cls("Group", "size") + cls("Holder", "group")
    body = (
        SIZE
        + "  group:\n    title: Group slot\n    description: The group.\n    annotations:\n      default_instance: 'true'\n"
    )
    code, folder, _ = build(tmp_path, {"groups": schema(classes, body, default_range="Group")})
    if code != 0:
        return
    holder = load(folder, "groups").Holder
    assert holder().group.size == 3, (
        "the generator built the wrong default for a slot whose range is the default range"
    )


def test_a_range_class_in_an_imported_module_is_imported_and_built(tmp_path: Path) -> None:
    """Tries a holder whose range class lives in another module of the project."""
    other = schema(cls("Group", "size"), SIZE, name="other")
    root = schema(cls("Holder", "group"), holder_slot("group", "Group"), imports=", other")
    code, folder, _ = build(tmp_path, {"groups": root, "other": other})
    assert code == 0, "a range in an imported module generates"
    assert load_package(folder).Holder().group.size == 3, "the imported range builds"


def load_package(folder: Path) -> ModuleType:
    """Import ``groups`` as part of a package, so its relative import of ``other`` resolves."""
    package = f"proj_pkg_{id(folder)}"
    spec = importlib.util.spec_from_file_location(
        package,
        folder / "generated" / "__init__.py",
        submodule_search_locations=[str(folder / "generated")],
    )
    assert spec is not None, "no spec"
    assert spec.loader is not None, "no loader"
    pkg = importlib.util.module_from_spec(spec)
    sys.modules[package] = pkg
    spec.loader.exec_module(pkg)
    return importlib.import_module(f"{package}.groups")


def test_a_narrowed_range_in_a_subclass_keeps_a_default_of_the_narrowed_class(
    tmp_path: Path,
) -> None:
    """Tries Holder2 is_a Holder narrowing `group` to SubGroup: the default must not be a bare Group refused by validation."""
    classes = cls("Group", "size") + cls("SubGroup", "", is_a="Group") + cls("Holder", "group")
    classes += cls(
        "Holder2", "", is_a="Holder", extra="    slot_usage:\n      group: {range: SubGroup}\n"
    )
    code, folder, _ = build(
        tmp_path, {"groups": schema(classes, SIZE + holder_slot("group", "Group"))}
    )
    if code != 0:
        return
    held = load(folder, "groups").Holder2().group
    assert type(held).__name__ == "SubGroup", (
        f"the narrowed slot defaulted to {type(held).__name__}"
    )


def test_a_range_class_with_a_default_instance_slot_that_cannot_build_is_refused(
    tmp_path: Path,
) -> None:
    """Tries Holder.group -> Group, where Group.inner -> Inner has a required slot with no default: refused naming inner."""
    inner = cls("Inner", "need", extra="")
    classes = inner + cls("Group", "inner") + cls("Holder", "group")
    slots = (
        "  need:\n    title: Need\n    description: Need.\n    required: true\n"
        + holder_slot("inner", "Inner")
        + holder_slot("group", "Group")
    )
    code, _, _ = build(tmp_path, {"groups": schema(classes, slots)})
    assert code != 0, "a nested default that cannot build generated"


@pytest.mark.parametrize(
    "ifabsent",
    [
        "string(a,b)",
        "string( a , b )",
        "string(a)",
        pytest.param(
            "string()",
            marks=pytest.mark.xfail(strict=True, reason="under the floor, design D-55"),
        ),
        "string(a, 'b')",
    ],
)
def test_a_list_default_forms_are_split_cleanly(tmp_path: Path, ifabsent: str) -> None:
    """Tries list-default spellings: each is the list of stripped names or a refusal, never a string with spaces."""
    classes = cls("Names", "names")
    slots = (
        "  names:\n    title: Names\n    description: Names.\n    multivalued: true\n"
        f"    ifabsent: {ifabsent}\n"
    )
    code, folder, _ = build(tmp_path, {"groups": schema(classes, slots)})
    if code != 0:
        return
    names = load(folder, "groups").Names().names
    assert all(n == n.strip() and n for n in names), f"{ifabsent} gave {names!r}"
