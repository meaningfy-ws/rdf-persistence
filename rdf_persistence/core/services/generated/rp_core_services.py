from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal as _Decimal
from enum import Enum as _Enum
from typing import (
    Any as _Any,
    ClassVar as _ClassVar,
    Literal as _Literal,
    Optional as _Optional,
    Union as _Union
)

from pydantic import (
    BaseModel as _BaseModel,
    ConfigDict as _ConfigDict,
    Field as _Field,
    RootModel as _RootModel,
    SerializationInfo as _SerializationInfo,
    SerializerFunctionWrapHandler as _SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None


class HttpSettings(ConfiguredBaseModel):
    "The timeouts and the attempts of every HTTP client of the toolkit: the SPARQL store, the identity provider and the object store."
    connect_timeout_seconds: float = _Field(default=5.0, title="Connect timeout", description="The seconds an HTTP client waits to open a connection.", ge=0.001, le=31536000)
    read_timeout_seconds: float = _Field(default=30.0, title="Read timeout", description="The seconds an HTTP client waits for the answer.", ge=0.001, le=31536000)
    max_attempts: int = _Field(default=3, title="Maximum attempts", description="The most times the object store client tries a request.", ge=1)


class LogContext(ConfiguredBaseModel):
    "The data of one step of an operation: the step and whatever else the call site knows. Only the step is required."
    step: str = _Field(default=..., alias="rp.step", title="Step", description="The step of the operation a record or a span stands for, one constant per call site.")
    tenant_id: _Optional[str] = _Field(default=None, alias="rp.tenant.id", title="Tenant id", description="The id of the tenant the operation works on.")
    resource: _Optional[str] = _Field(default=None, alias="rp.resource", title="Resource", description="The resource an operation of a sweep or a dump works on.")
    store_name: _Optional[str] = _Field(default=None, alias="rp.store.name", title="Store name", description="The name of the store a record concerns, as the registry records it.")
    found_store_name: _Optional[str] = _Field(default=None, alias="rp.store.found_name", title="Found store name", description="The name of the store where the tenant was found instead.")
    schema_id: _Optional[str] = _Field(default=None, alias="rp.schema.id", title="Schema id", description="The id of the schema a migration moves a tenant to.")
    migration_name: _Optional[str] = _Field(default=None, alias="rp.migration.name", title="Migration name", description="The name of the migration step a record concerns.")
    blob_count: _Optional[int] = _Field(default=None, alias="rp.blob.count", title="Blob count", description="The number of blobs an operation removed or kept.")
    source_tenant_id: _Optional[str] = _Field(default=None, alias="rp.restore.source_tenant.id", title="Source tenant id", description="The id of the tenant a restore reads from.")
    policy_fields: _Optional[list[str]] = _Field(default=None, alias="rp.iri_policy.fields", title="Policy fields", description="The fields of the IRI policy that changed.")
    system_created: _Optional[bool] = _Field(default=None, alias="rp.sweep.system_created", title="System created", description="Whether this start-up just created the system database, so the sweep is skipped.")
    resources: _Optional[list[str]] = _Field(default=None, alias="rp.sweep.resources", title="Resources", description="The resources a sweep reached.")
    activity_id: _Optional[str] = _Field(default=None, alias="rp.activity.id", title="Activity id", description="The id of the activity a record concerns.")
    activity_class: _Optional[str] = _Field(default=None, alias="rp.activity.class", title="Activity class", description="The Python class name of the activity.")
    activity_class_iri: _Optional[str] = _Field(default=None, alias="rp.activity.class_iri", title="Activity class iri", description="The class IRI an event envelope carries.")
    event_origin: _Optional[str] = _Field(default=None, alias="rp.event.origin", title="Event origin", description="The deployment that published an event.")
    observer_name: _Optional[str] = _Field(default=None, alias="rp.observer.name", title="Observer name", description="The name of an observer of the message bus.")
    message_limit: _Optional[int] = _Field(default=None, alias="rp.message.limit", title="Message limit", description="The limit on the messages of a commit.")
    error_detail: _Optional[str] = _Field(default=None, alias="rp.error.detail", title="Error detail", description="The detail of a validation error, free of the data that failed it.")
    response_body: _Optional[str] = _Field(default=None, alias="rp.store.response_body", title="Response body", description="The body a store answered with; written at DEBUG only.")
    db_system_name: _Optional[str] = _Field(default=None, alias="db.system.name", title="Db system name", description="The database system, an OpenTelemetry stable attribute.")
    db_namespace: _Optional[str] = _Field(default=None, alias="db.namespace", title="Db namespace", description="The database name, an OpenTelemetry stable attribute.")
    db_operation_name: _Optional[str] = _Field(default=None, alias="db.operation.name", title="Db operation name", description="The database operation, an OpenTelemetry stable attribute.")
    db_response_status_code: _Optional[str] = _Field(default=None, alias="db.response.status_code", title="Db response status code", description="The status code a database answered with, an OpenTelemetry stable attribute.")
    error_type: _Optional[str] = _Field(default=None, alias="error.type", title="Error type", description="The qualified class name of an exception, or the code a service answered with.")
    exception_type: _Optional[str] = _Field(default=None, alias="exception.type", title="Exception type", description="The qualified class name of an exception, on the `exception` event of a span; the only attribute of that event, an OpenTelemetry stable attribute.")
    http_response_status_code: _Optional[int] = _Field(default=None, alias="http.response.status_code", title="Http response status code", description="The HTTP status of a response, an OpenTelemetry stable attribute.")
    messaging_system_name: _Optional[str] = _Field(default=None, alias="messaging.system.name", title="Messaging system name", description="The messaging system, an OpenTelemetry development attribute (v1.45.0).")
    messaging_destination_name: _Optional[str] = _Field(default=None, alias="messaging.destination.name", title="Messaging destination name", description="The messaging destination, an OpenTelemetry development attribute (v1.45.0).")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
HttpSettings.model_rebuild()
LogContext.model_rebuild()
