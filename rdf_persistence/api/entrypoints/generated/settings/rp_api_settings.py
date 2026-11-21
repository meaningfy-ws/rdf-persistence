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
from rdf_persistence.access.services.generated.settings.rp_access_settings import (
    DirectorySettings,
    JwksSettings
)
from rdf_persistence.core.services.generated.rp_core_services import (
    HttpSettings,
    LogContext
)
from rdf_persistence.events.services.generated.settings.rp_events_settings import EventSettings
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import LimitSettings


metamodel_version = "1.12.0"
version = "None"


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel

linkml_meta = None


class SseSettings(ConfiguredBaseModel):
    "The lifetime, the access check, the keep-alive and the resume window of the events route."
    max_lifetime_seconds: float = _Field(default=300.0, title="Maximum lifetime", description="The seconds an events connection stays open before the client must reconnect.", ge=0.001, le=31536000)
    access_ttl_seconds: float = _Field(default=1.0, title="Access check lifetime", description="The seconds the result of an access check is kept.", ge=0.001, le=31536000)
    keep_alive_seconds: float = _Field(default=15.0, title="Keep-alive interval", description="The seconds of silence after which the events route sends a comment line.", ge=0.001, le=31536000)
    resume_window_seconds: float = _Field(default=604800, title="Resume window", description="The seconds back from now a client may resume from with its last event id.", ge=0.001, le=31536000)


class ToolkitSettings(ConfiguredBaseModel):
    "Every group of settings; each group is a new instance of its class with its own defaults, never absent."
    http: HttpSettings = _Field(default_factory=HttpSettings, title="HTTP", description="The HTTP client settings.")
    jwks: JwksSettings = _Field(default_factory=JwksSettings, title="JWKS", description="The key cache and signature settings of the token verifier.")
    directory: DirectorySettings = _Field(default_factory=DirectorySettings, title="Directory", description="The user directory settings.")
    events: EventSettings = _Field(default_factory=EventSettings, title="Events", description="The event bus, relay and hub settings.")
    sse: SseSettings = _Field(default_factory=SseSettings, title="Server-sent events", description="The settings of the events route.")
    limits: LimitSettings = _Field(default_factory=LimitSettings, title="Limits", description="The size and count limits.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
SseSettings.model_rebuild()
ToolkitSettings.model_rebuild()
