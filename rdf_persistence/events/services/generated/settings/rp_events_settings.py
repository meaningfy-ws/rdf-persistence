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


from rdf_persistence.core.domain.base import RpModel as ConfiguredBaseModel



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


class EventSettings(ConfiguredBaseModel):
    "The event bus, the relay that publishes from the outbox, and the hub that fans events out."
    stream: str = Field(default="rp-events", title="Stream", description="The name of the event stream.")
    retention_seconds: float = Field(default=604800, title="Retention", description="The seconds an event stays in the stream.", ge=0.001, le=31536000)
    claim_idle_seconds: float = Field(default=30.0, title="Claim idle time", description="The seconds a delivered event may stay unacknowledged before it is delivered again.", ge=0.001, le=31536000)
    polling_interval_ms: int = Field(default=100, title="Polling interval", description="The milliseconds between two reads of the stream.", ge=1)
    relay_interval_seconds: float = Field(default=5.0, title="Relay interval", description="The seconds the relay waits between two looks at the outbox.", ge=0.001, le=31536000)
    publish_timeout_seconds: float = Field(default=10.0, title="Publish timeout", description="The seconds the relay waits for the bus to take one event.", ge=0.001, le=31536000)
    hub_queue_size: int = Field(default=1000, title="Hub queue size", description="The events a subscriber of the hub may have waiting before it is reset.", ge=1)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
EventSettings.model_rebuild()
