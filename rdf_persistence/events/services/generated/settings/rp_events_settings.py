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


class EventSettings(ConfiguredBaseModel):
    "The event bus, the relay that publishes from the outbox, and the hub that fans events out."
    stream: str = _Field(default="rp-events", title="Stream", description="The name of the event stream.")
    retention_seconds: float = _Field(default=604800, title="Retention", description="The seconds an event stays in the stream.", ge=0.001, le=31536000)
    claim_idle_seconds: float = _Field(default=30.0, title="Claim idle time", description="The seconds a delivered event may stay unacknowledged before it is delivered again.", ge=0.001, le=31536000)
    polling_interval_ms: int = _Field(default=100, title="Polling interval", description="The milliseconds between two reads of the stream.", ge=1)
    relay_interval_seconds: float = _Field(default=5.0, title="Relay interval", description="The seconds the relay waits between two looks at the outbox.", ge=0.001, le=31536000)
    publish_timeout_seconds: float = _Field(default=10.0, title="Publish timeout", description="The seconds the relay waits for the bus to take one event.", ge=0.001, le=31536000)
    hub_queue_size: int = _Field(default=1000, title="Hub queue size", description="The events a subscriber of the hub may have waiting before it is reset.", ge=1)


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
EventSettings.model_rebuild()
