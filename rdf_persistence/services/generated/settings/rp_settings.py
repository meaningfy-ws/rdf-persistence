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


class HttpSettings(ConfiguredBaseModel):
    "The timeouts and the attempts of every HTTP client of the toolkit: the SPARQL store, the identity provider and the object store."
    connect_timeout_seconds: float = Field(default=5.0, title="Connect timeout", description="The seconds an HTTP client waits to open a connection.", ge=0.001)
    read_timeout_seconds: float = Field(default=30.0, title="Read timeout", description="The seconds an HTTP client waits for the answer.", ge=0.001)
    max_attempts: int = Field(default=3, title="Maximum attempts", description="The most times the object store client tries a request.", ge=1)


class JwksSettings(ConfiguredBaseModel):
    "How the token verifier caches the identity provider\u0027s keys and which signatures it accepts."
    ttl_seconds: float = Field(default=600.0, title="Key cache lifetime", description="The seconds a fetched set of signing keys is used before it is fetched again.", ge=0.001)
    unknown_kid_cooldown_seconds: float = Field(default=10.0, title="Key refresh cooldown", description="The most often, in seconds, that the keys are fetched again, whether they are stale or a token names a key id that is not in the cache.", ge=0.001)
    allowed_algorithms: list[str] = Field(default=['RS256', 'RS384', 'RS512', 'PS256', 'PS384', 'PS512', 'ES256', 'ES384', 'ES512', 'EdDSA'], title="Allowed algorithms", description="The JWS algorithms a token may be signed with. Any name but `none` and the shared-secret `HS*` family is accepted here; the token verifier checks each name against the installed JWT library when it is built.", min_length=1)
    leeway_seconds: float = Field(default=30.0, title="Clock leeway", description="The seconds a token\u0027s expiry and not-before times may be off, to allow for clock drift.", ge=0, le=300)

    @field_validator("allowed_algorithms")
    def pattern_allowed_algorithms(cls, v):
        pattern=re.compile("(?i)^(?!none$|hs)\\S+$")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid allowed_algorithms format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid allowed_algorithms format: " + str(v)
            raise ValueError(err_msg)
        return v


class DirectorySettings(ConfiguredBaseModel):
    "How the user directory of the identity provider is read."
    page_size: int = Field(default=100, title="Page size", description="The users read from the directory in one request.", ge=1)


class EventSettings(ConfiguredBaseModel):
    "The event bus, the relay that publishes from the outbox, and the hub that fans events out."
    stream: str = Field(default="rp-events", title="Stream", description="The name of the event stream.")
    retention_seconds: float = Field(default=604800, title="Retention", description="The seconds an event stays in the stream.", ge=0.001)
    claim_idle_seconds: float = Field(default=30.0, title="Claim idle time", description="The seconds a delivered event may stay unacknowledged before it is delivered again.", ge=0.001)
    polling_interval_ms: int = Field(default=100, title="Polling interval", description="The milliseconds between two reads of the stream.", ge=1)
    relay_interval_seconds: float = Field(default=5.0, title="Relay interval", description="The seconds the relay waits between two looks at the outbox.", ge=0.001)
    publish_timeout_seconds: float = Field(default=10.0, title="Publish timeout", description="The seconds the relay waits for the bus to take one event.", ge=0.001)
    hub_queue_size: int = Field(default=1000, title="Hub queue size", description="The events a subscriber of the hub may have waiting before it is reset.", ge=1)


class SseSettings(ConfiguredBaseModel):
    "The lifetime, the access check, the keep-alive and the resume window of the events route."
    max_lifetime_seconds: float = Field(default=300.0, title="Maximum lifetime", description="The seconds an events connection stays open before the client must reconnect.", ge=0.001)
    access_ttl_seconds: float = Field(default=1.0, title="Access check lifetime", description="The seconds the result of an access check is kept.", ge=0.001)
    keep_alive_seconds: float = Field(default=15.0, title="Keep-alive interval", description="The seconds of silence after which the events route sends a comment line.", ge=0.001)
    resume_window_seconds: float = Field(default=604800, title="Resume window", description="The seconds back from now a client may resume from with its last event id.", ge=0.001)


class LimitSettings(ConfiguredBaseModel):
    "The most the toolkit takes in one message bus run, one commit, one body and one restore manifest."
    max_messages: int = Field(default=100, title="Maximum messages", description="The most messages one run of the message bus handles.", ge=1)
    max_roots: int = Field(default=500, title="Maximum roots", description="The most aggregate roots one commit transaction holds.", ge=1)
    max_document_nodes: int = Field(default=10000, title="Maximum document nodes", description="The most objects and list values one JSON-LD body may hold.", ge=1)
    max_manifest_bytes: int = Field(default=65536, title="Maximum manifest size", description="The most bytes the manifest of a tenant dump may hold.", ge=1)


class ToolkitSettings(ConfiguredBaseModel):
    "Every group of settings; each group is a new instance of its class with its own defaults, never absent."
    http: HttpSettings = Field(default_factory=HttpSettings, title="HTTP", description="The HTTP client settings.")
    jwks: JwksSettings = Field(default_factory=JwksSettings, title="JWKS", description="The key cache and signature settings of the token verifier.")
    directory: DirectorySettings = Field(default_factory=DirectorySettings, title="Directory", description="The user directory settings.")
    events: EventSettings = Field(default_factory=EventSettings, title="Events", description="The event bus, relay and hub settings.")
    sse: SseSettings = Field(default_factory=SseSettings, title="Server-sent events", description="The settings of the events route.")
    limits: LimitSettings = Field(default_factory=LimitSettings, title="Limits", description="The size and count limits.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
HttpSettings.model_rebuild()
JwksSettings.model_rebuild()
DirectorySettings.model_rebuild()
EventSettings.model_rebuild()
SseSettings.model_rebuild()
LimitSettings.model_rebuild()
ToolkitSettings.model_rebuild()
