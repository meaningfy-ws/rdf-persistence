"""The service API answers for dependent parts (dependent-aggregates DEC-3, PD-18, A-17).

An audit A1 is the whole, its results R1 and R2 the parts; ``ada`` is the tenant's creator.
"""

import json

import httpx
import pytest

from rdf_persistence.core.domain.media import JSON
from tests.scene import PROBLEMS
from tests.toy_service import TENANT_BODY, ToyService

BODY = {"label": "Audit", "description": "An audit."}
MISSING = "https://example.org/library/audit/missing"


class Audits:
    """A tenant of ``ada``, and the writes and reads of audits and results in it."""

    def __init__(self, service: ToyService, http: httpx.AsyncClient) -> None:
        self.http, self.headers = http, service.bearer("ada")
        self.path = ""

    async def set_up(self) -> "Audits":
        made = await self.http.post("/libraries", json=TENANT_BODY, headers=self.headers)
        self.path = made.headers["location"]
        return self

    async def post(self, collection: str, **slots: str) -> httpx.Response:
        return await self.http.post(
            f"{self.path}/{collection}", json={**BODY, **slots}, headers=self.headers
        )

    async def created(self, collection: str, **slots: str) -> str:
        made = await self.post(collection, **slots)
        assert made.status_code == 201, made.text
        return made.json()["id"]

    async def replace(self, iri: str, collection: str, **slots: str) -> httpx.Response:
        url = f"{self.path}/{collection}/{iri.rsplit('/', 1)[1]}"
        current = await self.http.get(url, headers=self.headers)
        return await self.http.put(
            url,
            content=json.dumps({**current.json(), **slots}),
            headers={**self.headers, "If-Match": current.headers["etag"], "Content-Type": JSON},
        )

    async def results_of(self, audit: str) -> list[str]:
        listed = await self.http.get(
            f"{self.path}/audit-results", params={"of_audit": audit}, headers=self.headers
        )
        assert listed.status_code == 200, listed.text
        return [item["id"] for item in listed.json()["items"]]


async def audits(service: ToyService, client: httpx.AsyncClient) -> Audits:
    return await Audits(service, client).set_up()


async def test_a_result_posted_for_a_missing_audit_is_404_naming_nothing_but_the_kind(
    service, client
):
    lib = await audits(service, client)

    refused = await lib.post("audit-results", of_audit=MISSING)

    assert refused.status_code == 404, refused.text
    assert refused.json()["type"] == f"{PROBLEMS}not-found", "the problem is a not-found"


async def test_a_result_posted_for_an_existing_audit_is_created(service, client):
    lib = await audits(service, client)
    a1 = await lib.created("audits")

    made = await lib.post("audit-results", of_audit=a1)

    assert made.status_code == 201, made.text


async def test_a_result_posted_for_a_result_instead_of_an_audit_is_404(service, client):
    lib = await audits(service, client)
    a1 = await lib.created("audits")
    r1 = await lib.created("audit-results", of_audit=a1)

    refused = await lib.post("audit-results", of_audit=r1)

    assert refused.status_code == 404, "the pointer must name an audit, not any aggregate"


async def test_a_replace_that_changes_the_audit_is_409_conflict(service, client):
    lib = await audits(service, client)
    a1, a2 = await lib.created("audits"), await lib.created("audits")
    r1 = await lib.created("audit-results", of_audit=a1)

    refused = await lib.replace(r1, "audit-results", of_audit=a2)

    assert refused.status_code == 409, refused.text
    assert refused.json()["type"] == f"{PROBLEMS}conflict", "the type ends in problems/conflict"


async def test_a_replace_that_keeps_the_audit_is_accepted(service, client):
    lib = await audits(service, client)
    a1 = await lib.created("audits")
    r1 = await lib.created("audit-results", of_audit=a1)

    kept = await lib.replace(r1, "audit-results", label="Renamed")

    assert kept.status_code == 200, kept.text


async def test_listing_on_the_pointer_returns_that_audits_results_only(service, client):  # A-17
    lib = await audits(service, client)
    a1, a2 = await lib.created("audits"), await lib.created("audits")
    r1 = await lib.created("audit-results", of_audit=a1)
    r2 = await lib.created("audit-results", of_audit=a1)
    r3 = await lib.created("audit-results", of_audit=a2)

    assert sorted(await lib.results_of(a1)) == sorted([r1, r2]), "A1's results, both"
    assert await lib.results_of(a2) == [r3], "A2's result, alone"


@pytest.mark.parametrize("collection", ["audit-results", "audit-findings"])
async def test_a_dependent_class_posted_with_a_missing_whole_is_404(service, client, collection):
    lib = await audits(service, client)
    slot = {"audit-results": "of_audit", "audit-findings": "of_result"}[collection]

    refused = await lib.post(collection, **{slot: MISSING})

    assert refused.status_code == 404, f"{collection}: {refused.text}"
