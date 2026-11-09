"""Roots written only through a session (PD-3, #55): the generic create, replace and delete are not served."""

import shutil
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from rdf_persistence import Mapper, UnitOfWork, generated_models
from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.domain.generated import rp_core
from rdf_persistence.generation.cli import main as generate
from tests.toy import TOY_SCHEMA
from tests.toy_service import SCAN_BODY, ToyService, principal_of, store_scan
from tests.unit.entrypoints.scene import NIL, Scene, problem_of

PACKAGE = "writelib"
LIBRARY = TOY_SCHEMA.parent
TAG = "      rp_path: scans\n"
SHEDS = """
id: https://example.org/ns/library/sheds
name: sheds
title: Sheds module
description: Sheds that store books; the shed is a service-written aggregate root.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
  - rdf_persistence/model/rp_core
  - rdf_persistence/model/rp_annotations
annotations:
  module_kind: domain

classes:
  Shed:
    title: Shed
    description: A shed of the library; a root the consumer writes through a session.
    class_uri: lib:Shed
    mixins: [AggregateRoot, Described, Tracked]
    annotations:
      rp_path: sheds
      database: tenant
      rp_writes: service
"""
PYPROJECT = f"""
[tool.rp-generate]
schema = "library.yaml"
package = "{PACKAGE}.generated"
python = "generated"
"""


# --- T-6: a stored file cannot be rewritten by a client --------------------------------------


async def scan_path(scene: Scene) -> str:
    scan = await store_scan(scene.service.kit, scene.tenant_iri, principal_of("ada"))
    return f"{scene.tenant}/scans/{scan.id.rsplit('/', 1)[-1]}"


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
async def test_the_generic_writes_of_a_scan_answer_405_and_leave_it_unchanged(
    scene: Scene, method: str
) -> None:
    member = await scan_path(scene)
    before = await scene.http.get(member, headers=scene.headers("ada"))
    url = f"{scene.tenant}/scans" if method == "POST" else member
    response = await scene.http.request(
        method,
        url,
        json=SCAN_BODY,
        headers=scene.headers("ada", **{"If-Match": before.headers["etag"]}),
    )
    assert response.status_code == 405, response.text
    assert problem_of(response).type.endswith("method-not-allowed"), "the existing problem"
    assert response.headers["allow"] == "GET", "only the read is served"
    after = await scene.http.get(member, headers=scene.headers("ada"))
    assert (after.json(), after.headers["etag"]) == (before.json(), before.headers["etag"]), (
        "the scan is as it was"
    )


async def test_a_scan_and_the_scan_listing_are_still_read(scene: Scene) -> None:
    member = await scan_path(scene)
    assert (await scene.http.get(member, headers=scene.headers("ada"))).status_code == 200
    listing = await scene.http.get(f"{scene.tenant}/scans", headers=scene.headers("ada"))
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 1, "the stored scan is listed"


async def test_a_scan_that_is_not_there_is_still_a_404_on_read(scene: Scene) -> None:
    response = await scene.http.get(f"{scene.tenant}/scans/{NIL}1", headers=scene.headers("ada"))
    assert response.status_code == 404, "the read is served"


# --- T-7: any root can opt in ----------------------------------------------------------------


@pytest.fixture(scope="module")
def shed_project(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Path, Any]]:
    """The toy library plus ``Shed``, a root without ``StoredFile`` annotated ``rp_writes: service``: its schema and generated package."""
    root = tmp_path_factory.mktemp("writes")
    project = root / PACKAGE
    ignored = shutil.ignore_patterns("generated", "web", "golden", "__pycache__", "pyproject.toml")
    shutil.copytree(LIBRARY, project, ignore=ignored)
    (project / "__init__.py").write_text("")
    (project / "sheds.yaml").write_text(SHEDS)
    library = (
        (project / "library.yaml").read_text().replace("  - scans\n", "  - scans\n  - sheds\n")
    )
    (project / "library.yaml").write_text(library)
    (project / "pyproject.toml").write_text(PYPROJECT)
    assert generate(["--project", str(project / "pyproject.toml")]) == 0, "rp-generate failed"
    sys.path.insert(0, str(root))
    package = __import__(f"{PACKAGE}.generated", fromlist=["generated"])
    try:
        yield project / "library.yaml", package
    finally:
        sys.path.remove(str(root))
        for name in [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")]:
            del sys.modules[name]


@pytest.fixture
async def shed_service(shed_project: tuple[Path, Any]) -> AsyncIterator[ToyService]:
    schema, package = shed_project
    toy = ToyService(schema=schema, package=package)
    async with toy.app.router.lifespan_context(toy.app):
        yield toy


def test_an_annotated_root_is_described_by_its_reads_only(shed_project) -> None:
    schema, package = shed_project
    paths = ToyService(schema=schema, package=package).app.openapi()["paths"]
    collection, member = "/libraries/{t}/sheds", "/libraries/{t}/sheds/{aggregate_id}"
    assert set(paths[collection]) == {"get"}, "the listing"
    assert set(paths[member]) == {"get"}, "the read"
    assert set(paths["/libraries/{t}/books"]) == {"get", "post"}, (
        "an unannotated root keeps its create"
    )


# --- T-8: the consumer's route writes it -----------------------------------------------------


async def test_a_session_adds_replaces_and_removes_a_shed_each_with_a_new_version(
    shed_service: ToyService, shed_project: tuple[Path, Any]
) -> None:
    """``Shed`` is annotated ``rp_writes: service`` (T-7): the generic writes are not served, a session writes it."""
    _, package = shed_project
    mapper = Mapper(shed_service.kit.view, generated_models(package.sheds, rp_core))
    async with shed_service.client() as http:
        scene = await Scene.set_up(shed_service, http)
    kit, tenant, ada = shed_service.kit, scene.tenant_iri, principal_of("ada")
    shed = package.sheds.Shed(
        id=str(kit.iris.mint_aggregate(tenant, "shed", "sheds")), label="Shed"
    )
    async with kit.session(tenant, ada) as session:
        work = UnitOfWork(session, mapper)
        work.add(shed)
        await work.commit()
        _, _, added = await session.get_graph(shed.id)
        read = await work.get(package.sheds.Shed, shed.id)
        read.label = "Tool shed"
        work.add(read)
        await work.commit()
        _, _, replaced = await session.get_graph(shed.id)
        assert replaced != added, "the replace is a new version"
        await session.remove(shed.id, replaced)
        with pytest.raises(NotFound):
            await session.get_graph(shed.id)


async def test_a_scan_written_through_a_session_is_read_over_the_api(
    scene: Scene, client: httpx.AsyncClient
) -> None:
    member = await scan_path(scene)
    response = await client.get(member, headers=scene.headers("ada"))
    assert response.json()["label"] == SCAN_BODY["label"], "the record the session wrote"
