"""The generator's end-to-end proof (PD-13): the toy library, freshly generated, served.

The toy is copied to ``tmp_path/toy_e2e``, generated as ``toy_e2e.generated``, imported with
``tmp_path`` on ``sys.path`` and served with ``install_service`` over Fuseki, Garage and Zitadel,
wired as ``tests/e2e/library_app.py`` does minus the scan routes. The helpers of the library's own
e2e (callers, settings) and of the toy service (problems, bodies) are imported, not copied.
"""

import importlib
import shutil
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from types import ModuleType

import httpx
import pytest
from fastapi import FastAPI

from rdf_persistence import (
    AccessRules,
    FusekiStore,
    Grant,
    GrantSet,
    JwksTokenVerifier,
    S3FileStore,
    TenantCreate,
    TenantSummary,
    ZitadelIdentity,
    install_service,
    load_role_definitions,
    zitadel_roles_claim,
)
from rdf_persistence.testkit import access_token
from rdf_persistence_generation.cli import main as generate
from tests.e2e.library_app import library_settings
from tests.e2e.world import Callers
from tests.toy import REVIEW_WORKFLOW, ROLES
from tests.toy_service import assert_problem, body_of, drop_buckets, drop_databases, unique_prefix

TOY = Path(__file__).parents[2] / "fixtures" / "library"
PACKAGE = "toy_e2e"
LIBRARIAN, READER, OUTSIDER = "librarian", "reader", "outsider"

pytestmark = pytest.mark.slow


@contextmanager
def generated_toy(tmp_path: Path) -> Iterator[ModuleType]:
    """The toy copied to ``tmp_path/toy_e2e``, generated as ``toy_e2e.generated`` and imported.

    ``tmp_path`` is on ``sys.path`` and ``toy_e2e`` in ``sys.modules`` only inside the block.
    """
    folder = tmp_path / PACKAGE
    shutil.copytree(TOY, folder, ignore=shutil.ignore_patterns("__pycache__", "generated"))
    exit_code = generate(
        ["--project", str(folder / "pyproject.toml"), "--package", f"{PACKAGE}.domain.generated"]
    )
    assert exit_code == 0, "the toy copy did not generate"
    sys.path.insert(0, str(tmp_path))
    importlib.invalidate_caches()
    try:
        yield importlib.import_module(f"{PACKAGE}.domain.generated")
    finally:
        sys.path.remove(str(tmp_path))
        for name in [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")]:
            del sys.modules[name]
        importlib.invalidate_caches()


@asynccontextmanager
async def served(
    generated: ModuleType, tmp_path: Path, fuseki, garage, zitadel_project
) -> AsyncIterator[tuple[httpx.AsyncClient, Callers]]:
    """The freshly generated library served in process: a client and the callers."""
    prefix = unique_prefix()
    server = zitadel_project.server
    users = {user.name: user for user in zitadel_project.machine_users}
    callers = Callers(
        tokens={name: access_token(zitadel_project, user) for name, user in users.items()},
        principals={name: f"{server.url}/users/{user.user_id}" for name, user in users.items()},
    )
    roles_claim = zitadel_roles_claim(zitadel_project.project_id)
    folder = tmp_path / PACKAGE
    async with (
        FusekiStore(fuseki.url, fuseki.user, fuseki.password) as store,
        ZitadelIdentity(
            server.url,
            server.admin_pat,
            zitadel_project.organisation_id,
            zitadel_project.project_id,
        ) as identity,
        JwksTokenVerifier(
            server.url, zitadel_project.project_id, roles_claim, allow_insecure_issuer=True
        ) as verifier,
    ):
        files = S3FileStore(garage.endpoint, garage.key_id, garage.secret, garage.region)
        app = FastAPI()
        install_service(
            app,
            schema=folder / "library.yaml",
            generated=generated,
            store=store,
            files=files,
            identity=identity,
            verifier=verifier,
            rules=AccessRules(load_role_definitions(ROLES)),
            settings=library_settings(prefix, roles_claim),
            workflows=[REVIEW_WORKFLOW],
            migrations=folder / "migrations",
        )
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with (
            app.router.lifespan_context(app),
            httpx.AsyncClient(transport=transport, base_url="http://library") as http,
        ):
            yield http, callers
        await drop_databases(store, prefix)
        await drop_buckets(files, prefix)


def dune(generated: ModuleType, label: str = "Dune"):
    """A book with a chapter and a note, built from the freshly generated classes."""
    books = importlib.import_module(f"{generated.__name__}.books")
    note = books.Note.model_construct(label="Spice", description="The spice must flow.", text="x")
    chapter = books.Chapter.model_construct(number=1, notes=[note])
    return books.Book.model_construct(
        label=label,
        description="A planet.",
        genre=books.Genre.FICTION,
        authors=["Herbert"],
        chapters=[chapter],
    )


async def make_library(
    http: httpx.AsyncClient, callers: Callers, generated: ModuleType
) -> tuple[str, str]:
    """The librarian makes a library; returns its path and its IRI."""
    library = importlib.import_module(f"{generated.__name__}.library")
    root = body_of(library.Library.model_construct(description="Books for all.", city="Ghent"))
    created = await http.post(
        "/libraries",
        json=TenantCreate(label="Ghent", root=root).model_dump(mode="json"),
        headers=callers.as_(LIBRARIAN),
    )
    assert created.status_code == 201, created.text
    return created.headers["location"], TenantSummary.model_validate(created.json()).id


async def test_a_librarian_creates_reads_replaces_and_deletes_a_book(
    tmp_path, fuseki, garage, zitadel_project
) -> None:
    """TC-51."""
    with generated_toy(tmp_path) as generated:
        async with served(generated, tmp_path, fuseki, garage, zitadel_project) as (http, callers):
            path, _ = await make_library(http, callers, generated)
            librarian = callers.as_(LIBRARIAN)
            created = await http.post(
                f"{path}/books", json=body_of(dune(generated)), headers=librarian
            )
            assert created.status_code == 201, created.text
            book, etag = created.headers["location"], created.headers["etag"]
            read = await http.get(book, headers=librarian)
            assert read.status_code == 200, read.text
            assert read.json()["label"] == "Dune", "the book that was created"
            replaced = await http.put(
                book,
                json=body_of(dune(generated, "Dune Messiah")),
                headers=callers.as_(LIBRARIAN, **{"If-Match": etag}),
            )
            assert replaced.status_code == 200, replaced.text
            assert replaced.headers["etag"] != etag, "a new version"
            deleted = await http.delete(
                book, headers=callers.as_(LIBRARIAN, **{"If-Match": replaced.headers["etag"]})
            )
            assert deleted.status_code == 204, deleted.text
            assert (await http.get(book, headers=librarian)).status_code == 404, "gone"


async def test_a_reader_may_not_write_a_book(tmp_path, fuseki, garage, zitadel_project) -> None:
    """TC-52."""
    with generated_toy(tmp_path) as generated:
        async with served(generated, tmp_path, fuseki, garage, zitadel_project) as (http, callers):
            path, tenant_iri = await make_library(http, callers, generated)
            answer = await http.get(f"{path}/grants", headers=callers.as_(LIBRARIAN))
            assert answer.status_code == 200, answer.text
            granted = GrantSet.model_validate(answer.json())
            readers = GrantSet(
                grants=[
                    *(granted.grants or []),
                    Grant(assignee=callers.principals[READER], target=tenant_iri, role=READER),
                ]
            )
            put = await http.put(
                f"{path}/grants",
                json=readers.model_dump(mode="json", exclude_none=True),
                headers=callers.as_(LIBRARIAN, **{"If-Match": answer.headers["etag"]}),
            )
            assert put.status_code == 200, put.text
            refused = await http.post(
                f"{path}/books", json=body_of(dune(generated)), headers=callers.as_(READER)
            )
            assert_problem(refused, 403, "forbidden")


async def test_an_outsider_finds_no_library(tmp_path, fuseki, garage, zitadel_project) -> None:
    """TC-53."""
    with generated_toy(tmp_path) as generated:
        async with served(generated, tmp_path, fuseki, garage, zitadel_project) as (http, callers):
            path, _ = await make_library(http, callers, generated)
            answer = await http.get(path, headers=callers.as_(OUTSIDER))
            assert_problem(answer, 404, "not-found")


def test_the_generated_package_leaves_neither_modules_nor_path_behind(tmp_path: Path) -> None:
    """TC-54."""
    with generated_toy(tmp_path) as generated:
        assert generated.__name__ == f"{PACKAGE}.domain.generated", "imported under the new name"
        assert str(tmp_path) in sys.path, "tmp_path is on the path inside the block"
    assert not [n for n in sys.modules if n == PACKAGE or n.startswith(f"{PACKAGE}.")], (
        "toy_e2e is still in sys.modules"
    )
    assert str(tmp_path) not in sys.path, "tmp_path is still on sys.path"
