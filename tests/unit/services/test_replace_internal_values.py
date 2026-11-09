"""A replace keeps the internal values the service stored (PD-3, R1-1): no body can set them, none may be erased."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from rdflib import Literal, URIRef

from rdf_persistence.domain.generated.rp_core import Principal
from rdf_persistence.domain.iris import DEFAULT_IRIS
from rdf_persistence.domain.media import JSON
from rdf_persistence.generation.cli import main as generate
from rdf_persistence.services.aggregates import Aggregates
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.session import Session
from rdf_persistence.testkit import FakeStore
from rdf_persistence.testkit.fakes import FAKE_DATABASE

TENANT = "https://example.org/tenants/t1"
ADA = Principal(id="https://example.org/people/ada")
SERIAL = URIRef("https://example.org/ns/m#serial")
PYPROJECT = """
[tool.rp-generate]
schema = "m.yaml"
package = "app.generated"
"""
SCHEMA = """
id: https://example.org/ns/m
name: m
title: Module
description: A module for the tests.
prefixes:
  tst: https://example.org/ns/m#
  linkml: https://w3id.org/linkml/
default_prefix: tst
default_range: string
imports:
  - linkml:types
  - rdf_persistence/model/rp_core
  - rdf_persistence/model/rp_annotations
classes:
  Crate:
    title: Crate
    description: A root with a slot the service sets; the consumer writes it by the generic routes.
    mixins: [AggregateRoot, Described]
    slots: [serial]
    annotations:
      rp_path: crates
slots:
  serial:
    title: Serial
    description: Set by the service, never by a body.
    slot_uri: tst:serial
    range: string
    annotations:
      internal: true
"""


@pytest.fixture(scope="module")
def documents(tmp_path_factory: pytest.TempPathFactory) -> Documents:
    project = tmp_path_factory.mktemp("crates")
    (project / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (project / "m.yaml").write_text(SCHEMA, encoding="utf-8")
    assert generate(["--project", str(project / "pyproject.toml")]) == 0, "rp-generate failed"
    return Documents(load_schema(project / "m.yaml"), project / "app" / "generated")


async def test_a_replace_keeps_the_internal_value_the_service_stored(documents: Documents) -> None:
    store = FakeStore()
    await store.create_dataset(FAKE_DATABASE)
    session = Session(
        store,
        database=FAKE_DATABASE,
        tenant_iri=TENANT,
        principal=ADA,
        clock=lambda: datetime(2026, 11, 9, tzinfo=UTC),
        iris=DEFAULT_IRIS,
    )

    class Tenancy:
        @asynccontextmanager
        async def tenant_session(self, tenant, principal):
            yield session

    aggregates = Aggregates(documents, Tenancy())  # type: ignore[arg-type]
    crate, body = documents.aggregates["crates"], json.dumps({"label": "A"}).encode()
    iri, (triples, _, version) = await aggregates.create(TENANT, ADA, crate, "crates", body, JSON)
    await session.replace_graph(iri, [*triples, (URIRef(iri), SERIAL, Literal("S-1"))], version)
    _, _, stored = await session.get_graph(iri)

    replaced, _, _ = await aggregates.replace(
        TENANT, ADA, crate, iri, json.dumps({"id": iri, "label": "B"}).encode(), JSON, stored
    )

    assert (URIRef(iri), SERIAL, Literal("S-1")) in replaced, "the internal value is still there"
    assert Literal("B") in set(replaced.objects()), "and the body's label replaced the old one"
