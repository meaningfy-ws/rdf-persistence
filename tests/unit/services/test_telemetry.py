"""The log context and its helpers (otel-observability PD-1 to PD-3, PD-12)."""

import logging

import pytest
from opentelemetry.semconv.attributes import (
    db_attributes,
    error_attributes,
    http_attributes,
)
from pydantic import ValidationError

from rdf_persistence.domain.exceptions import NotFound
from rdf_persistence.services.generated.telemetry.rp_telemetry import LogContext
from rdf_persistence.services.telemetry import error_type, log_extra
from tests.logs import attributes, records_of

STABLE_ALIASES = {
    "db_system_name": db_attributes.DB_SYSTEM_NAME,
    "db_namespace": db_attributes.DB_NAMESPACE,
    "db_operation_name": db_attributes.DB_OPERATION_NAME,
    "db_response_status_code": db_attributes.DB_RESPONSE_STATUS_CODE,
    "error_type": error_attributes.ERROR_TYPE,
    "http_response_status_code": http_attributes.HTTP_RESPONSE_STATUS_CODE,
}
# Development in v1.45.0: no constant in the stable package, so the names are pinned here.
DEVELOPMENT_ALIASES = {
    "messaging_system_name": "messaging.system.name",
    "messaging_destination_name": "messaging.destination.name",
}
FULL = {
    "step": "s",
    "tenant_id": "t",
    "resource": "r",
    "store_name": "n",
    "found_store_name": "f",
    "schema_id": "i",
    "migration_name": "m",
    "blob_count": 1,
    "source_tenant_id": "o",
    "policy_fields": ["a", "b"],
    "system_created": True,
    "resources": ["x"],
    "activity_id": "a1",
    "activity_class": "C",
    "activity_class_iri": "https://e/C",
    "event_origin": "d",
    "observer_name": "ob",
    "message_limit": 5,
    "error_detail": "e",
    "response_body": "b",
    "db_system_name": "fuseki",
    "db_namespace": "ns",
    "db_operation_name": "op",
    "db_response_status_code": "500",
    "error_type": "x.Y",
    "http_response_status_code": 500,
    "messaging_system_name": "redis",
    "messaging_destination_name": "q",
}


def test_log_extra_keeps_the_set_slots_under_their_attribute_names():
    context = LogContext(step="x", tenant_id="t")

    assert log_extra(context) == {"rp.step": "x", "rp.tenant.id": "t"}


@pytest.mark.parametrize("kwargs", [{}, {"step": "x", "tenant": "t"}])
def test_log_context_refuses_a_missing_step_and_an_unknown_field(kwargs):
    with pytest.raises(ValidationError):
        LogContext(**kwargs)


@pytest.mark.parametrize("kwargs", [{"blob_count": "many"}, {"policy_fields": "a"}])
def test_log_context_refuses_a_value_of_the_wrong_type(kwargs):
    with pytest.raises(ValidationError):
        LogContext(step="x", **kwargs)


def test_every_alias_is_dotted_and_free_of_a_log_record_attribute(caplog):
    reserved = set(vars(logging.makeLogRecord({})))
    aliases = {field.alias for field in LogContext.model_fields.values()}

    assert len(aliases) == 28
    assert all("." in alias and alias not in reserved for alias in aliases)

    with caplog.at_level(logging.INFO):
        logging.getLogger("t").info("m", extra=log_extra(LogContext(**FULL)))

    (record,) = caplog.records
    assert set(attributes(record)) == aliases


def test_records_of_selects_the_records_of_one_step(caplog):
    log = logging.getLogger("t")
    with caplog.at_level(logging.INFO):
        log.info("a", extra=log_extra(LogContext(step="one")))
        log.info("b", extra=log_extra(LogContext(step="two")))
        log.info("c")

    assert [r.getMessage() for r in records_of(caplog, "one")] == ["a"]


@pytest.mark.parametrize("slot", STABLE_ALIASES)
def test_a_stable_alias_is_the_constant_of_the_semantic_conventions(slot):
    assert LogContext.model_fields[slot].alias == STABLE_ALIASES[slot]


@pytest.mark.parametrize("slot", DEVELOPMENT_ALIASES)
def test_a_development_alias_is_the_name_pinned_at_v1_45_0(slot):
    assert LogContext.model_fields[slot].alias == DEVELOPMENT_ALIASES[slot]


@pytest.mark.parametrize(
    ("error", "spelling"),
    [
        (NotFound("n"), "rdf_persistence.domain.exceptions.NotFound"),
        (ValueError(), "builtins.ValueError"),
    ],
)
def test_error_type_is_the_module_and_qualified_name(error, spelling):
    assert error_type(error) == spelling
