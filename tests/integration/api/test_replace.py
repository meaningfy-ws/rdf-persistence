"""Scenario 'a replace keeps what the service stored' (rp-service-api, PD-14b), against Fuseki."""

from rdf_persistence.domain.iris import graph_iri, tenant_resource_name
from tests.integration.api.conftest import make_tenant
from tests.toy_service import SCAN_BODY

FILE_KEY = "https://meaningfy.ws/ns/rdf-persistence#fileKey"


async def test_a_replace_of_a_scan_keeps_its_file_key(toy, client) -> None:
    headers = toy.bearer("ada")
    tenant = await make_tenant(toy, client)
    made = await client.post(f"{tenant}/scans", json=SCAN_BODY, headers=headers)
    assert made.status_code == 201, made.text
    iri, location, etag = made.json()["id"], made.headers["location"], made.headers["etag"]
    database = tenant_resource_name(toy.settings.prefix, iri.rsplit("/scans/", 1)[0])
    await toy.store.update(
        database,
        f'INSERT DATA {{ GRAPH <{graph_iri(iri)}> {{ <{iri}> <{FILE_KEY}> "the-key" }} }}',
    )

    replaced = await client.put(
        location,
        json={**SCAN_BODY, "label": "Dune, rescanned"},
        headers={**headers, "If-Match": etag},
    )

    assert replaced.status_code == 200, replaced.text
    ask = f'ASK {{ GRAPH <{graph_iri(iri)}> {{ <{iri}> <{FILE_KEY}> "the-key" }} }}'
    assert (await toy.store.query(database, ask)).askAnswer, "the key the client cannot set stays"
