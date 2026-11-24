"""Helpers that write a small generated project and import or type-check what it generates."""

import importlib
import subprocess
import sys
from pathlib import Path
from types import ModuleType

from rdf_persistence_generation.checks.importable import MYPY_CONFIG

PACKAGE = "imports_app"
HEADER = """\
id: https://example.org/ns/library/{name}
name: {name}
title: {name} module
description: The {name} module.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
  rp: https://meaningfy.ws/ns/rdf-persistence#
default_prefix: lib
default_range: string
imports:
  - linkml:types
  - rdf_persistence/model/rp_core
  - rdf_persistence/model/rp_annotations
{extra_imports}"""
DOMAIN = "annotations:\n  module_kind: domain\n"
PYPROJECT = f"""\
[tool.rp-generate]
schema = "{{root}}.yaml"
package = "{PACKAGE}.domain.generated"
python = "{PACKAGE}/domain/generated"
migrations = "migrations"
"""


def root_class(name: str, *, parent: str | None = None, abstract: bool = False) -> str:
    """A root class (``AggregateRoot``, ``Described``, ``Tracked``), optionally under ``parent``."""
    lines = [
        f"  {name}:",
        f"    title: {name}",
        f"    description: The {name} class, an aggregate root.",
        f"    class_uri: lib:{name}",
        "    mixins: [AggregateRoot, Described, Tracked]",
    ]
    if parent:
        lines.append(f"    is_a: {parent}")
    if abstract:
        lines.append("    abstract: true")
    else:
        lines += ["    annotations:", f"      rp_path: {name.lower()}s", "      database: tenant"]
    return "\n".join(lines) + "\n"


def module(name: str, classes: str, *, imports: tuple[str, ...] = (), slots: str = "") -> str:
    extra = "".join(f"  - {other}\n" for other in imports)
    return f"{HEADER.format(name=name, extra_imports=extra)}{DOMAIN}\nclasses:\n{classes}{slots}"


def write_target(folder: Path, root: str) -> Path:
    """A pyproject whose target generates ``<root>.yaml`` into the package, and the package's folders."""
    folder.mkdir(exist_ok=True)
    (folder / PACKAGE / "domain").mkdir(parents=True)
    (folder / PACKAGE / "__init__.py").write_text("")
    (folder / PACKAGE / "domain" / "__init__.py").write_text("")
    (folder / "pyproject.toml").write_text(PYPROJECT.format(root=root))
    return folder / "pyproject.toml"


def write_project(folder: Path, modules: dict[str, str]) -> Path:
    """The project: a pyproject, a root schema importing ``modules``, the modules; returns the pyproject."""
    pyproject = write_target(folder, "app")
    root = HEADER.format(name="app", extra_imports="".join(f"  - {m}\n" for m in modules))
    (folder / "app.yaml").write_text(
        root.replace("title: app module\n", 'title: app\nversion: "1"\n')
    )
    for name, text in modules.items():
        (folder / f"{name}.yaml").write_text(text)
    return pyproject


def generated(name: str) -> ModuleType:
    return importlib.import_module(f"{PACKAGE}.domain.generated.{name}")


def mypy_output(project: Path) -> str:
    """mypy over the generated package, as ``make typecheck-generated`` runs it; empty when clean."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "--config-file",
            str(MYPY_CONFIG),
            "--no-incremental",
            f"{PACKAGE}/domain/generated",
        ],
        cwd=project,
        capture_output=True,
        text=True,
        check=False,
    )
    return "" if result.returncode == 0 else result.stdout
