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


class JwksSettings(ConfiguredBaseModel):
    "How the token verifier caches the identity provider\u0027s keys and which signatures it accepts."
    ttl_seconds: float = Field(default=600.0, title="Key cache lifetime", description="The seconds a fetched set of signing keys is used before it is fetched again.", ge=0.001, le=31536000)
    unknown_kid_cooldown_seconds: float = Field(default=10.0, title="Key refresh cooldown", description="The most often, in seconds, that the keys are fetched again, whether they are stale or a token names a key id that is not in the cache.", ge=1, le=31536000)
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


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
JwksSettings.model_rebuild()
DirectorySettings.model_rebuild()
