"""The policy guard at start-up over the fakes: the policy is fixed once a deployment has data (PD-9, PD-13)."""

import json
import logging

import pytest
from rdflib import Graph, Literal, URIRef

from rdf_persistence.core.domain.exceptions import IriPolicyChanged
from rdf_persistence.core.domain.generated.rp_core import Principal
from rdf_persistence.domain.layout import POLICY_SEGMENT
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.generated.service.rp_service import IdKind, IdSpec, IriPolicy
from rdf_persistence.services.iri_policy_guard import guard_iri_policy
from rdf_persistence.services.iris import Iris
from rdf_persistence.services.tenancy import Tenancy
from rdf_persistence.testkit import FakeFileStore, FakeStore
from tests.fixtures.library.generated.library import Library
from tests.fixtures.library.generated.library_access import LibraryAccess
from tests.logs import attributes, records_of
from tests.toy import ADA, SETTINGS, library_slots, toy_mapper

RECORD_GRAPH = URIRef(f"{SETTINGS.base}{POLICY_SEGMENT}")
THIRTEEN = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=13))
TWELVE = IriPolicy(object_id=IdSpec(kind=IdKind.RANDOM, length=12))


def settings_of(policy: IriPolicy | None):
    return SETTINGS.model_copy(update={"iri_policy": policy})


def recording_updates(store: FakeStore) -> list[str]:
    """The updates that write the policy record (tenancy writes others)."""
    return [text for text in store.sent("update") if POLICY_SEGMENT in text]


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


@pytest.fixture
async def tenancy(store) -> Tenancy:
    made = Tenancy(
        store,
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
    )
    await made.ensure_system_database()
    return made


async def test_the_first_start_records_the_policy(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    assert len(store.sent("update")) == 1, (
        "the first start sends exactly one update, recording the policy"
    )


async def test_a_restart_with_the_same_policy_starts(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))


async def test_a_changed_template_names_the_differing_field_and_mints_nothing(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    with pytest.raises(IriPolicyChanged, match=r"object_id\.length"):
        await guard_iri_policy(store, tenancy, settings_of(TWELVE))
    assert len(store.sent("update")) == 1, "the record is not overwritten"


async def test_every_differing_field_is_named(store, tenancy):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    changed = THIRTEEN.model_copy(update={"meta_template": "{tenant}/m", "tenant_id": None})
    changed = changed.model_copy(update={"object_id": TWELVE.object_id})
    with pytest.raises(IriPolicyChanged) as caught:
        await guard_iri_policy(store, tenancy, settings_of(changed))
    assert "meta_template" in str(caught.value), "the refusal names the differing meta template"
    assert "object_id.length" in str(caught.value), (
        "the refusal names the differing object id length"
    )


@pytest.mark.parametrize(
    "second",
    [IriPolicy(), IriPolicy(tenant_id=IdSpec(kind=IdKind.UUID4))],
    ids=["explicit-default", "explicit-uuid4-tenant-id"],
)
async def test_the_default_policy_unset_or_explicit_is_one_policy(store, tenancy, second):
    # equivalence class: every spelling of the effective default; the spelled-out UUID4 tenant id
    # is the one that fails when the id specs are not made canonical
    await guard_iri_policy(store, tenancy, settings_of(None))
    await guard_iri_policy(store, tenancy, settings_of(second))


async def test_a_policy_recorded_before_the_provenance_template_reads_as_the_default(
    store, tenancy
):
    """message-bus TC-07: the recorded JSON has no ``provenance_template``; it is not a change."""
    recorded = effective_of(IriPolicy()).model_dump(mode="json", exclude={"provenance_template"})
    record = Graph()
    record.add((RECORD_GRAPH, v.IRI_POLICY, Literal(json.dumps(recorded))))
    await store.put_graph(tenancy.system_database, RECORD_GRAPH, record)
    await guard_iri_policy(store, tenancy, settings_of(None))


async def test_a_non_default_policy_over_data_without_a_record_is_refused(store, tenancy):
    await tenancy.create("Ghent", library_slots(), Principal(id=ADA))
    with pytest.raises(IriPolicyChanged, match="default policy") as caught:
        await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    assert "object_id" in str(caught.value), "the refusal names the object id field"
    assert recording_updates(store) == [], "nothing is recorded"


async def test_the_default_policy_over_data_without_a_record_is_recorded(store, tenancy):
    await tenancy.create("Ghent", library_slots(), Principal(id=ADA))
    await guard_iri_policy(store, tenancy, settings_of(None))
    assert len(recording_updates(store)) == 1, (
        "the default policy is recorded with exactly one update"
    )
    with pytest.raises(IriPolicyChanged):
        await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))


async def test_tc09_a_refusal_is_one_constant_error_record_naming_the_fields(
    store, tenancy, caplog
):
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))
    with caplog.at_level(logging.ERROR), pytest.raises(IriPolicyChanged) as caught:
        await guard_iri_policy(store, tenancy, settings_of(TWELVE))
    [logged] = records_of(caplog, "iri-policy")
    assert (logged.levelno, logged.getMessage()) == (
        logging.ERROR,
        "the IRI policy cannot change once there is data",
    ), "the message is constant"
    fields = attributes(logged)["rp.iri_policy.fields"]
    assert isinstance(fields, list), "the fields are a list, not a joined text"
    assert fields == ["object_id.length"], "the list names the field that differs"
    assert all(name in str(caught.value) for name in fields), "the raised message names them too"


async def test_an_unreadable_record_is_logged_with_a_constant_message_and_the_reason(
    store, tenancy, caplog
):
    record = Graph()
    record.add((RECORD_GRAPH, v.IRI_POLICY, Literal("not json")))
    await store.put_graph(tenancy.system_database, RECORD_GRAPH, record)
    with caplog.at_level(logging.ERROR), pytest.raises(IriPolicyChanged, match="unreadable"):
        await guard_iri_policy(store, tenancy, settings_of(None))
    [logged] = records_of(caplog, "iri-policy")
    assert logged.getMessage() == "the recorded IRI policy is unreadable", "constant message"
    assert attributes(logged)["rp.error.detail"] == "it cannot be parsed", "the reason is data"


class RacingStore(FakeStore):
    """A store where another worker records ``rival`` just before this one's insert."""

    def __init__(self, rival: IriPolicy) -> None:
        super().__init__()
        self.rival = rival

    async def update(self, dataset: str, sparql: str) -> None:
        if not self.sent("update"):
            record = Graph()
            record.add(
                (RECORD_GRAPH, v.IRI_POLICY, Literal(effective_of(self.rival).model_dump_json()))
            )
            await self.put_graph(dataset, RECORD_GRAPH, record)
        await super().update(dataset, sparql)


def effective_of(policy: IriPolicy) -> IriPolicy:
    return Iris(settings_of(policy)).effective_policy


async def test_the_first_write_does_not_overwrite_a_rival_and_is_compared_with_it():
    store = RacingStore(THIRTEEN)
    tenancy = Tenancy(
        store,
        FakeFileStore(),
        SETTINGS,
        mapper=toy_mapper(),
        root_class=Library,
        access_class=LibraryAccess,
    )
    await tenancy.ensure_system_database()
    with pytest.raises(IriPolicyChanged, match="object_id"):
        await guard_iri_policy(store, tenancy, settings_of(None))
    await guard_iri_policy(store, tenancy, settings_of(THIRTEEN))


# -- app-level-data PD-1, PD-11, TC-48: a record from before the application template existed -------


async def record_without_application_template(store: FakeStore, tenancy: Tenancy) -> None:
    """The system database holds the default policy as an older service wrote it: no ``application_template``."""
    text = effective_of(IriPolicy()).model_dump_json(exclude={"application_template"})
    assert "application_template" not in text, "the record is the old shape"
    record = Graph()
    record.add((RECORD_GRAPH, v.IRI_POLICY, Literal(text)))
    await store.put_graph(tenancy.system_database, RECORD_GRAPH, record)


async def test_tc48_a_record_without_the_application_template_is_the_default_policy(store, tenancy):
    await record_without_application_template(store, tenancy)
    await guard_iri_policy(store, tenancy, settings_of(None))
    assert store.sent("update") == [], "the old record is read as it is, not rewritten"


async def test_tc48_a_record_without_the_application_template_refuses_another_one_naming_it(
    store, tenancy
):
    await record_without_application_template(store, tenancy)
    renamed = IriPolicy(application_template="{base}application")
    with pytest.raises(IriPolicyChanged, match="application_template"):
        await guard_iri_policy(store, tenancy, settings_of(renamed))
