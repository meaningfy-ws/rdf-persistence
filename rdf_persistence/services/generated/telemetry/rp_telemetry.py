from __future__ import annotations

import re
import sys
from datetime import (
    date,
    datetime,
    time
)
from decimal import Decimal
from enum import Enum
from typing import (
    Any,
    ClassVar,
    Literal,
    Optional,
    Union
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer
)


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.domain.base import RpModel as ConfiguredBaseModel



class LinkMLMeta(RootModel):
    root: dict[str, Any] = {}
    model_config = ConfigDict(frozen=True)

    def __getattr__(self, key:str):
        return getattr(self.root, key)

    def __getitem__(self, key:str):
        return self.root[key]

    def __setitem__(self, key:str, value):
        self.root[key] = value

    def __contains__(self, key:str) -> bool:
        return key in self.root


linkml_meta = None


class LogContext(ConfiguredBaseModel):
    "The data of one step of an operation: the step and whatever else the call site knows. Only the step is required."
    step: str = Field(default=..., alias="rp.step", title="Step", description="The step of the operation a record or a span stands for, one constant per call site.")
    tenant_id: Optional[str] = Field(default=None, alias="rp.tenant.id", title="Tenant id", description="The id of the tenant the operation works on.")
    resource: Optional[str] = Field(default=None, alias="rp.resource", title="Resource", description="The resource an operation of a sweep or a dump works on.")
    store_name: Optional[str] = Field(default=None, alias="rp.store.name", title="Store name", description="The name of the store a record concerns, as the registry records it.")
    found_store_name: Optional[str] = Field(default=None, alias="rp.store.found_name", title="Found store name", description="The name of the store where the tenant was found instead.")
    schema_id: Optional[str] = Field(default=None, alias="rp.schema.id", title="Schema id", description="The id of the schema a migration moves a tenant to.")
    migration_name: Optional[str] = Field(default=None, alias="rp.migration.name", title="Migration name", description="The name of the migration step a record concerns.")
    blob_count: Optional[int] = Field(default=None, alias="rp.blob.count", title="Blob count", description="The number of blobs an operation removed or kept.")
    source_tenant_id: Optional[str] = Field(default=None, alias="rp.restore.source_tenant.id", title="Source tenant id", description="The id of the tenant a restore reads from.")
    policy_fields: Optional[list[str]] = Field(default=None, alias="rp.iri_policy.fields", title="Policy fields", description="The fields of the IRI policy that changed.")
    system_created: Optional[bool] = Field(default=None, alias="rp.sweep.system_created", title="System created", description="Whether a sweep reached the resource as a system-created one.")
    resources: Optional[list[str]] = Field(default=None, alias="rp.sweep.resources", title="Resources", description="The resources a sweep reached.")
    activity_id: Optional[str] = Field(default=None, alias="rp.activity.id", title="Activity id", description="The id of the activity a record concerns.")
    activity_class: Optional[str] = Field(default=None, alias="rp.activity.class", title="Activity class", description="The Python class name of the activity.")
    activity_class_iri: Optional[str] = Field(default=None, alias="rp.activity.class_iri", title="Activity class iri", description="The class IRI an event envelope carries.")
    event_origin: Optional[str] = Field(default=None, alias="rp.event.origin", title="Event origin", description="The deployment that published an event.")
    observer_name: Optional[str] = Field(default=None, alias="rp.observer.name", title="Observer name", description="The name of an observer of the message bus.")
    message_limit: Optional[int] = Field(default=None, alias="rp.message.limit", title="Message limit", description="The limit on the messages of a commit.")
    error_detail: Optional[str] = Field(default=None, alias="rp.error.detail", title="Error detail", description="The detail of a validation error, free of the data that failed it.")
    response_body: Optional[str] = Field(default=None, alias="rp.store.response_body", title="Response body", description="The body a store answered with; written at DEBUG only.")
    db_system_name: Optional[str] = Field(default=None, alias="db.system.name", title="Db system name", description="The database system, an OpenTelemetry stable attribute.")
    db_namespace: Optional[str] = Field(default=None, alias="db.namespace", title="Db namespace", description="The database name, an OpenTelemetry stable attribute.")
    db_operation_name: Optional[str] = Field(default=None, alias="db.operation.name", title="Db operation name", description="The database operation, an OpenTelemetry stable attribute.")
    db_response_status_code: Optional[str] = Field(default=None, alias="db.response.status_code", title="Db response status code", description="The status code a database answered with, an OpenTelemetry stable attribute.")
    error_type: Optional[str] = Field(default=None, alias="error.type", title="Error type", description="The class of an error, as `module.QualifiedName`, an OpenTelemetry stable attribute.")
    http_response_status_code: Optional[int] = Field(default=None, alias="http.response.status_code", title="Http response status code", description="The HTTP status of a response, an OpenTelemetry stable attribute.")
    messaging_system_name: Optional[str] = Field(default=None, alias="messaging.system.name", title="Messaging system name", description="The messaging system, an OpenTelemetry development attribute (v1.45.0).")
    messaging_destination_name: Optional[str] = Field(default=None, alias="messaging.destination.name", title="Messaging destination name", description="The messaging destination, an OpenTelemetry development attribute (v1.45.0).")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
LogContext.model_rebuild()
