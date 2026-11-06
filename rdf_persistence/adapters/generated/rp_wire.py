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

class BadRequestMeans(str, Enum):
    "What an answer of 400 means to a call. Zitadel answers 400 to a state change that is already done, and to a grant of a role the project lacks, and the call knows which."
    FAILURE = "failure"
    "The request was wrong; this is an error like any other status."
    ALREADY_DONE = "already_done"
    "The state change had already happened, so the call has nothing left to do."
    MISSING_ROLE = "missing_role"
    "The project has no such role."



class ZitadelEmailQuery(ConfiguredBaseModel):
    "The search term that finds a user by email address."
    emailAddress: str = Field(default=..., title="Zitadel email address", description="The address to search for.")
    method: Optional[Literal["TEXT_QUERY_METHOD_EQUALS"]] = Field(default="TEXT_QUERY_METHOD_EQUALS", title="Zitadel text method", description="How the search term is compared.")


class ZitadelOrganisationQuery(ConfiguredBaseModel):
    "The search term that keeps the users of one organisation."
    organizationId: str = Field(default=..., title="Zitadel organisation id", description="The id of an organisation.")


class ZitadelProjectQuery(ConfiguredBaseModel):
    "The search term that keeps the grants of one project."
    projectId: str = Field(default=..., title="Zitadel project id", description="The id of a project.")


class ZitadelUserQuery(ConfiguredBaseModel):
    "The search term that keeps the grants of one user."
    userId: str = Field(default=..., title="Zitadel user id", description="The id of a user.")


class ZitadelQuery(ConfiguredBaseModel):
    "One term of a search; exactly one of its slots is set."
    emailQuery: Optional[ZitadelEmailQuery] = Field(default=None, title="Zitadel email query", description="A term that finds users by email address.")
    organizationIdQuery: Optional[ZitadelOrganisationQuery] = Field(default=None, title="Zitadel organisation id query", description="A term that keeps one organisation.")
    projectIdQuery: Optional[ZitadelProjectQuery] = Field(default=None, title="Zitadel project id query", description="A term that keeps one project.")
    userIdQuery: Optional[ZitadelUserQuery] = Field(default=None, title="Zitadel user id query", description="A term that keeps one user.")


class ZitadelWindow(ConfiguredBaseModel):
    "The part of a search result a page asks for."
    offset: int = Field(default=..., title="Zitadel offset", description="How many results to skip.")
    limit: int = Field(default=..., title="Zitadel limit", description="How many results to return at most.")


class ZitadelSearch(ConfiguredBaseModel):
    "The body of a search request: a window and the terms that all must hold."
    query: ZitadelWindow = Field(default=..., title="Zitadel window", description="The part of the result to return.")
    queries: list[ZitadelQuery] = Field(default=..., title="Zitadel queries", description="The terms that all must hold.")


class ZitadelGrantRequest(ConfiguredBaseModel):
    "The body that grants roles of a project to a user, or replaces the roles of a grant."
    projectId: Optional[str] = Field(default=None, title="Zitadel project id", description="The id of a project.")
    roleKeys: list[str] = Field(default=..., title="Zitadel role keys", description="The keys of project roles.")


class ZitadelProjectRequest(ConfiguredBaseModel):
    "The body that creates a project."
    name: str = Field(default=..., title="Zitadel name", description="The display name of a project or a machine user.")


class ZitadelRoleRequest(ConfiguredBaseModel):
    "The body that adds a role to a project."
    roleKey: str = Field(default=..., title="Zitadel role key", description="The key of a project role.")
    displayName: str = Field(default=..., title="Zitadel display name", description="The name a role is shown with.")


class ZitadelMachineUserRequest(ConfiguredBaseModel):
    "The body that creates a machine user whose access tokens are JWTs."
    userName: str = Field(default=..., title="Zitadel user name", description="The login name of a machine user.")
    name: str = Field(default=..., title="Zitadel name", description="The display name of a project or a machine user.")
    accessTokenType: Optional[Literal["ACCESS_TOKEN_TYPE_JWT"]] = Field(default="ACCESS_TOKEN_TYPE_JWT", title="Zitadel access token type", description="The kind of access token the user gets.")


class ZitadelKeyRequest(ConfiguredBaseModel):
    "The body that creates a key for a machine user."
    type: Optional[Literal["KEY_TYPE_JSON"]] = Field(default="KEY_TYPE_JSON", title="Zitadel key type", description="The format of the key.")


class ZitadelAssertion(ConfiguredBaseModel):
    "The claims of the JWT a machine user signs to ask for an access token (the JWT-profile grant)."
    iss: str = Field(default=..., title="Zitadel issuer", description="The machine user that signed the assertion.")
    sub: str = Field(default=..., title="Zitadel subject", description="The machine user the assertion speaks for.")
    aud: str = Field(default=..., title="Zitadel audience", description="The instance the assertion is for.")
    iat: int = Field(default=..., title="Zitadel issued at", description="When the assertion was signed, in seconds since the epoch.")
    exp: int = Field(default=..., title="Zitadel expires at", description="When the assertion stops being valid, in seconds since the epoch.")


class ZitadelTokenRequest(ConfiguredBaseModel):
    "The form that asks for an access token with a signed assertion."
    grant_type: Optional[Literal["urn:ietf:params:oauth:grant-type:jwt-bearer"]] = Field(default="urn:ietf:params:oauth:grant-type:jwt-bearer", title="Zitadel grant type", description="The OAuth grant type.")
    scope: str = Field(default=..., title="Zitadel scope", description="The space-separated OAuth scopes.")
    assertion: str = Field(default=..., title="Zitadel assertion", description="The signed JWT that proves the machine user\u0027s identity.")


class ZitadelEmail(ConfiguredBaseModel):
    "The email address of a person, as Zitadel reports it."
    model_config = ConfigDict(extra="allow")

    email: str = Field(default=..., title="Zitadel email", description="The email address.")


class ZitadelHuman(ConfiguredBaseModel):
    "What Zitadel reports about a person; a service account has none."
    model_config = ConfigDict(extra="allow")

    email: Optional[ZitadelEmail] = Field(default=None, title="Zitadel human email", description="The email of the person.")


class ZitadelUser(ConfiguredBaseModel):
    "One user of an organisation, as the user search reports it."
    model_config = ConfigDict(extra="allow")

    userId: str = Field(default=..., title="Zitadel user id", description="The id of a user.")
    state: str = Field(default=..., title="Zitadel state", description="The state of the account; the active one is `USER_STATE_ACTIVE`.")
    username: str = Field(default=..., title="Zitadel username", description="The name the account signs in with.")
    human: Optional[ZitadelHuman] = Field(default=None, title="Zitadel human", description="The person behind the account, if it is a person\u0027s.")


class ZitadelUserGrant(ConfiguredBaseModel):
    "The roles of a project that a user holds, as the grant search reports them."
    model_config = ConfigDict(extra="allow")

    id: str = Field(default=..., title="Zitadel id", description="The id of a created or listed thing.")
    userId: str = Field(default=..., title="Zitadel user id", description="The id of a user.")
    roleKeys: Optional[list[str]] = Field(default=None, title="Zitadel role keys", description="The keys of project roles.")


class ZitadelUserPage(ConfiguredBaseModel):
    "One page of the user search."
    model_config = ConfigDict(extra="allow")

    result: Optional[list[ZitadelUser]] = Field(default=None, title="Zitadel users", description="The users of the page.")


class ZitadelGrantPage(ConfiguredBaseModel):
    "One page of the grant search."
    model_config = ConfigDict(extra="allow")

    result: Optional[list[ZitadelUserGrant]] = Field(default=None, title="Zitadel grants", description="The grants of the page.")


class ZitadelCreated(ConfiguredBaseModel):
    "The answer to creating a project, or the organisation inside the answer that reads it."
    model_config = ConfigDict(extra="allow")

    id: str = Field(default=..., title="Zitadel id", description="The id of a created or listed thing.")


class ZitadelOrganisationAnswer(ConfiguredBaseModel):
    "The answer that reads the organisation of the caller."
    model_config = ConfigDict(extra="allow")

    org: ZitadelCreated = Field(default=..., title="Zitadel org", description="The organisation of the caller.")


class ZitadelMachineUserAnswer(ConfiguredBaseModel):
    "The answer to creating a machine user."
    model_config = ConfigDict(extra="allow")

    userId: str = Field(default=..., title="Zitadel user id", description="The id of a user.")


class ZitadelKeyAnswer(ConfiguredBaseModel):
    "The answer to creating a key: the key file, base64 encoded."
    model_config = ConfigDict(extra="allow")

    keyDetails: str = Field(default=..., title="Zitadel key details", description="The key file, base64 encoded.")


class ZitadelKeyFile(ConfiguredBaseModel):
    "The key file a machine user signs its assertions with, once decoded."
    model_config = ConfigDict(extra="allow")

    keyId: str = Field(default=..., title="Zitadel key id", description="The id of the key.")
    key: str = Field(default=..., title="Zitadel key", description="The private key, in PEM.")


class ZitadelTokenAnswer(ConfiguredBaseModel):
    "The answer that grants an access token."
    model_config = ConfigDict(extra="allow")

    access_token: str = Field(default=..., title="Zitadel access token", description="The access token.")


class JwtClaims(ConfiguredBaseModel):
    "The claims of a verified access token that the toolkit reads; the roles claim, whose name is configured, stays among the extra fields."
    model_config = ConfigDict(extra="allow")

    sub: str = Field(default=..., title="JWT subject", description="The account the token is for.")
    iss: str = Field(default=..., title="JWT issuer", description="The issuer of the token.")
    aud: Any = Field(default=..., title="JWT audience", description="The audience of the token, one string or a list of them.")
    exp: float = Field(default=..., title="JWT expires at", description="When the token stops being valid, in seconds since the epoch.")
    nbf: Optional[float] = Field(default=None, title="JWT not before", description="When the token starts being valid, in seconds since the epoch.")
    azp: Optional[str] = Field(default=None, title="JWT authorized party", description="The client the token was issued to.")

    @field_validator("sub")
    def pattern_sub(cls, v):
        pattern=re.compile("[\\s\\S]+")
        if isinstance(v, list):
            for element in v:
                if isinstance(element, str) and not pattern.fullmatch(element):
                    err_msg = "Invalid sub format: " + str(element)
                    raise ValueError(err_msg)
        elif isinstance(v, str) and not pattern.fullmatch(v):
            err_msg = "Invalid sub format: " + str(v)
            raise ValueError(err_msg)
        return v


class DiscoveryDocument(ConfiguredBaseModel):
    "The part of an OpenID Connect discovery document the toolkit reads."
    model_config = ConfigDict(extra="allow")

    issuer: str = Field(default=..., title="Discovery issuer", description="The issuer the document describes.")
    jwks_uri: str = Field(default=..., title="Discovery JWKS URI", description="Where the issuer publishes its signing keys.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
ZitadelEmailQuery.model_rebuild()
ZitadelOrganisationQuery.model_rebuild()
ZitadelProjectQuery.model_rebuild()
ZitadelUserQuery.model_rebuild()
ZitadelQuery.model_rebuild()
ZitadelWindow.model_rebuild()
ZitadelSearch.model_rebuild()
ZitadelGrantRequest.model_rebuild()
ZitadelProjectRequest.model_rebuild()
ZitadelRoleRequest.model_rebuild()
ZitadelMachineUserRequest.model_rebuild()
ZitadelKeyRequest.model_rebuild()
ZitadelAssertion.model_rebuild()
ZitadelTokenRequest.model_rebuild()
ZitadelEmail.model_rebuild()
ZitadelHuman.model_rebuild()
ZitadelUser.model_rebuild()
ZitadelUserGrant.model_rebuild()
ZitadelUserPage.model_rebuild()
ZitadelGrantPage.model_rebuild()
ZitadelCreated.model_rebuild()
ZitadelOrganisationAnswer.model_rebuild()
ZitadelMachineUserAnswer.model_rebuild()
ZitadelKeyAnswer.model_rebuild()
ZitadelKeyFile.model_rebuild()
ZitadelTokenAnswer.model_rebuild()
JwtClaims.model_rebuild()
DiscoveryDocument.model_rebuild()
