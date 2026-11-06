"""Scenarios 'a new class in the model' and 'a stale replace' (rp-service-api), against Fuseki."""

import asyncio
import importlib
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

from rdf_persistence import Problem
from rdf_persistence.generation.cli import main as generate
from tests.integration.api.conftest import BOOK, TENANT_BODY, drop_databases, make_book
from tests.toy import TOY_SCHEMA
from tests.toy_service import ToyService, unique_prefix

LIBRARY = TOY_SCHEMA.parent
PACKAGE = "shelflib"
SHELVES = """
id: https://example.org/ns/library/shelves
name: shelves
title: Shelves module
description: Shelves that hold books; the shelf is an aggregate root.
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
annotations:
  module_kind: domain

classes:
  Shelf:
    title: Shelf
    description: A shelf of the library; an aggregate root.
    class_uri: lib:Shelf
    mixins: [AggregateRoot, Described, Tracked]
    slots: [capacity]
    annotations:
      rp_path: shelves
      database: tenant

slots:
  capacity:
    title: Capacity
    description: How many books the shelf holds.
    slot_uri: lib:capacity
    range: integer
"""
PYPROJECT = f"""
[tool.rp-generate]
schema = "library.yaml"
package = "{PACKAGE}.generated"
python = "generated"
"""


def with_a_shelf(root: Path) -> tuple[Path, ModuleType]:
    """A copy of the toy library under ``root`` whose schema also has the aggregate root ``Shelf``, generated."""
    project = root / PACKAGE
    shutil.copytree(
        LIBRARY,
        project,
        ignore=shutil.ignore_patterns(
            "generated", "web", "golden", "__pycache__", "pyproject.toml"
        ),
    )
    (project / "__init__.py").write_text("")
    (project / "shelves.yaml").write_text(SHELVES)
    schema = (
        (project / "library.yaml").read_text().replace("  - scans\n", "  - scans\n  - shelves\n")
    )
    (project / "library.yaml").write_text(schema)
    (project / "pyproject.toml").write_text(PYPROJECT)
    assert generate(["--project", str(project / "pyproject.toml")]) == 0, "rp-generate failed"
    sys.path.insert(0, str(root))
    importlib.invalidate_caches()
    return project / "library.yaml", importlib.import_module(f"{PACKAGE}.generated")


@pytest.fixture
def extended_model(tmp_path: Path):
    """The extended schema and its generated package; the import is undone afterwards."""
    schema, package = with_a_shelf(tmp_path)
    yield schema, package
    sys.path.remove(str(tmp_path))
    for name in [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")]:
        del sys.modules[name]


async def test_a_new_class_in_the_model_is_served_after_a_restart_with_no_code_added(
    store, extended_model
) -> None:
    schema, package = extended_model
    shelf = {"label": "Fiction", "description": "Novels.", "capacity": 120}
    before = ToyService(store, prefix=unique_prefix())
    async with before.app.router.lifespan_context(before.app), before.client() as http:
        tenant = (
            await http.post("/libraries", json=TENANT_BODY, headers=before.bearer("ada"))
        ).headers["location"]
        missing = await http.post(f"{tenant}/shelves", json=shelf, headers=before.bearer("ada"))
    await drop_databases(store, before.settings.prefix)
    assert missing.status_code == 404, "the model has no Shelf yet, so there is no route"

    after = ToyService(store, schema=schema, package=package, prefix=unique_prefix())
    try:
        async with after.app.router.lifespan_context(after.app), after.client() as http:
            tenant = (
                await http.post("/libraries", json=TENANT_BODY, headers=after.bearer("ada"))
            ).headers["location"]
            created = await http.post(f"{tenant}/shelves", json=shelf, headers=after.bearer("ada"))
            read = await http.get(created.headers["location"], headers=after.bearer("ada"))
    finally:
        await drop_databases(store, after.settings.prefix)
    assert created.status_code == 201, created.text
    assert "/shelves/" in created.json()["id"], "the IRI is minted below the new path"
    assert (read.status_code, read.json()["capacity"]) == (200, 120), "and the shelf is served"


async def test_a_stale_replace_is_a_409_problem_and_the_book_is_unchanged(toy, client) -> None:
    created = await make_book(toy, client)
    book, first = created.headers["location"], created.headers["etag"]
    headers = {**toy.bearer("ada"), "If-Match": first}
    won = await client.put(book, json={**BOOK, "label": "First"}, headers=headers)
    lost = await client.put(book, json={**BOOK, "label": "Second"}, headers=headers)
    assert won.status_code == 200, won.text
    assert lost.status_code == 409, lost.text
    assert lost.headers["content-type"] == "application/problem+json", "a problem response"
    assert Problem.model_validate(lost.json()).title == "Version conflict", "the fixed title"
    reread = await client.get(book, headers=toy.bearer("ada"))
    assert reread.json()["label"] == "First", "the book is unchanged by the stale replace"
    assert reread.headers["etag"] == won.headers["etag"], "and so is its version"


async def test_two_replaces_in_flight_leave_exactly_one_winner(toy, client) -> None:
    created = await make_book(toy, client)
    book, etag = created.headers["location"], created.headers["etag"]
    headers = {**toy.bearer("ada"), "If-Match": etag}
    answers = await asyncio.gather(
        *(client.put(book, json={**BOOK, "label": f"Edit {n}"}, headers=headers) for n in range(2))
    )
    assert sorted(a.status_code for a in answers) == [200, 409], (
        "one wins, the other is told to re-read"
    )
