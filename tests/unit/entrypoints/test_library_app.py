"""The consumer's file route, gated by ``ServiceKit.require_aggregate`` (PD-14b), over the fakes."""

from collections.abc import AsyncIterator

import httpx
import pytest

from rdf_persistence import Grant, GrantSet, JwksTokenVerifier
from rdf_persistence.domain.exceptions import NotFound, StoreUnavailable
from rdf_persistence.domain.generated.rp_access import Action, Prohibition
from rdf_persistence.domain.iris import graph_iri
from rdf_persistence.domain.media import JSON
from rdf_persistence.testkit import FakeFileStore, FakeIdentity, FakeStore, TokenSigner
from rdf_persistence.testkit.tokens import ISSUER
from tests.e2e.library_app import build_library_app
from tests.toy import SETTINGS
from tests.toy_service import TENANT_BODY, principal_of, store_scan, toy_key

BYTES = b"%PDF-1.7 dune"
LIMIT = 4096  # holds a tenant's body, not a scan's bytes of LIMIT + 1


class World:
    def __init__(self, max_body_bytes: int | None = None) -> None:
        self.signer = TokenSigner(key=toy_key())
        self.files = FakeFileStore()
        self.store = FakeStore()
        verifier = JwksTokenVerifier(
            ISSUER, self.signer.audience, self.signer.roles_claim, transport=self.signer.transport
        )
        settings = SETTINGS.model_copy(
            update={
                "roles_claim": self.signer.roles_claim,
                "max_body_bytes": max_body_bytes or SETTINGS.max_body_bytes,
            }
        )
        self.app = build_library_app(
            store=self.store,
            files=self.files,
            identity=FakeIdentity(),
            verifier=verifier,
            settings=settings,
        )

    def as_(self, who: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.signer.issue(sub=who, roles=[])}"}


@pytest.fixture
async def world() -> AsyncIterator[World]:
    made = World(max_body_bytes=LIMIT)
    async with made.app.router.lifespan_context(made.app):
        yield made


@pytest.fixture
async def http(world: World) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=world.app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class Shelf:
    """A tenant of ``ada`` with a scan in it, and a reader ``rita``."""

    def __init__(self, world: World, http: httpx.AsyncClient) -> None:
        self.world, self.http = world, http
        self.tenant = ""
        self.tenant_iri = ""
        self.scan_iri = ""
        self.scan_id = ""

    async def set_up(self) -> "Shelf":
        ada = self.world.as_("ada")
        made = await self.http.post("/libraries", json=TENANT_BODY, headers=ada)
        self.tenant, self.tenant_iri = made.headers["location"], made.json()["id"]
        scan = await store_scan(self.world.app.state.kit, self.tenant_iri, principal_of("ada"))
        self.scan_iri = scan.id
        self.scan_id = self.scan_iri.rsplit("/", 1)[-1]
        await self.grants()
        return self

    async def grants(self, *bans: Prohibition) -> None:
        ada = self.world.as_("ada")
        current = await self.http.get(f"{self.tenant}/grants", headers=ada)
        held = GrantSet.model_validate(current.json())
        reader = Grant(assignee=principal_of("rita"), target=self.tenant_iri, role="reader")
        body = GrantSet(
            grants=[g for g in held.grants or [] if g != reader] + [reader], prohibitions=list(bans)
        )
        put = await self.http.put(
            f"{self.tenant}/grants",
            content=body.model_dump_json(exclude_none=True),
            headers={**ada, "If-Match": current.headers["etag"], "Content-Type": JSON},
        )
        assert put.status_code == 200, put.text

    @property
    def file(self) -> str:
        return f"{self.tenant}/scan-files/{self.scan_id}"


@pytest.fixture
async def shelf(world: World, http: httpx.AsyncClient) -> Shelf:
    return await Shelf(world, http).set_up()


async def test_the_bytes_are_kept_under_the_id_of_the_scan_and_read_back(
    world, http, shelf
) -> None:
    stored = await http.put(shelf.file, content=BYTES, headers=world.as_("ada"))
    assert stored.status_code == 204, stored.text
    (bucket,) = await world.files.list_buckets("lib-t-")
    assert await world.files.get(bucket, shelf.scan_id) == BYTES, "keyed by the scan's id"
    read = await http.get(shelf.file, headers=world.as_("rita"))
    assert read.content == BYTES, "a reader gets them"


async def test_the_apps_post_writes_the_record_through_a_session_and_the_bytes_to_the_bucket(
    world, http, shelf
) -> None:
    created = await http.post(
        f"{shelf.tenant}/scan-files",
        params={"label": "Dune, rescanned", "file_name": "dune.pdf"},
        content=BYTES,
        headers={**world.as_("ada"), "Content-Type": "application/pdf"},
    )
    assert created.status_code == 201, created.text
    record = await http.get(created.headers["location"], headers=world.as_("ada"))
    assert record.json()["byte_size"] == len(BYTES), "the record, read over the generic route"
    (bucket,) = await world.files.list_buckets("lib-t-")
    assert await world.files.get(bucket, created.headers["location"].rsplit("/", 1)[-1]) == BYTES


async def test_a_body_over_the_limit_is_a_413_and_stores_nothing(world, http, shelf) -> None:
    refused = await http.post(
        f"{shelf.tenant}/scan-files",
        params={"label": "x", "file_name": "x.pdf"},
        content=bytes(LIMIT + 1),
        headers=world.as_("ada"),
    )
    assert refused.status_code == 413, refused.text
    assert world.files.sent("put") == [], "no bytes were stored"


async def post_while_the_store_is_down(world, http, shelf):
    """A scan posted when the commit fails: the response, and the bytes the bucket holds afterwards."""
    world.store.on("update", StoreUnavailable("down"))
    response = await http.post(
        f"{shelf.tenant}/scan-files",
        params={"label": "x", "file_name": "x.pdf"},
        content=BYTES,
        headers=world.as_("ada"),
    )
    (bucket,) = await world.files.list_buckets("lib-t-")
    return response, world.files, bucket


async def test_a_post_whose_commit_fails_removes_the_bytes(world, http, shelf) -> None:
    response, files, _ = await post_while_the_store_is_down(world, http, shelf)
    assert response.status_code == 503, response.text
    assert len(files.sent("delete")) == 1, "the bytes were removed again"


async def test_a_failing_cleanup_does_not_hide_the_error_that_caused_it(world, http, shelf) -> None:
    world.files.on("delete", NotFound("bucket gone"))  # would answer 404 if it escaped
    response, _, _ = await post_while_the_store_is_down(world, http, shelf)
    assert response.status_code == 503, "the commit's error, not a second 500"


async def test_a_reader_cannot_post_a_scan(world, http, shelf) -> None:
    refused = await http.post(
        f"{shelf.tenant}/scan-files",
        params={"label": "x", "file_name": "x.pdf"},
        content=BYTES,
        headers=world.as_("rita"),
    )
    assert refused.status_code == 403, refused.text


async def test_a_read_prohibition_on_the_scan_stops_the_file_too(world, http, shelf) -> None:
    await http.put(shelf.file, content=BYTES, headers=world.as_("ada"))
    ban = Prohibition(
        assignee=principal_of("rita"), target=str(graph_iri(shelf.scan_iri)), action=Action.READ
    )
    await shelf.grants(ban)
    read = await http.get(shelf.file, headers=world.as_("rita"))
    assert read.status_code == 403, "the rule on the scan applies to its file"


async def test_a_reader_cannot_write_the_file_and_an_outsider_cannot_see_it(
    world, http, shelf
) -> None:
    assert (await http.put(shelf.file, content=b"x", headers=world.as_("rita"))).status_code == 403
    assert (await http.get(shelf.file, headers=world.as_("omar"))).status_code == 404


@pytest.mark.parametrize(
    "scan_id",
    [
        "dune.pdf",
        "0000",
        pytest.param("898B0B0D-E7B5-4C3D-99E3-DB49565D00AA", id="upper-case-uuid"),
    ],
)
async def test_a_name_that_is_not_a_scan_id_is_a_404_before_the_store_is_asked(
    world, http, shelf, scan_id
) -> None:
    asked = len(world.store.sent("query"))
    response = await http.put(
        f"{shelf.tenant}/scan-files/{scan_id}", content=b"x", headers=world.as_("ada")
    )
    assert response.status_code == 404, response.text
    assert len(world.store.sent("query")) == asked, "no query"
