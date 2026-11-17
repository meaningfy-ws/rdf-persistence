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


class SlotShape(ConfiguredBaseModel):
    "The shape of one slot of a class, as the schema induces it."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a user).")
    required: bool = Field(default=..., title="Required", description="Whether a value is required.")
    multivalued: bool = Field(default=..., title="Multivalued", description="Whether the slot takes several values.")
    range: str = Field(default=..., title="Range", description="The name of the type, enum or class the slot\u0027s values belong to.")
    alias: Optional[str] = Field(default=None, title="Alias", description="The name the slot\u0027s field carries in code and JSON when it differs from the slot\u0027s name; absent otherwise.")


class ClassShape(ConfiguredBaseModel):
    "The reviewed shape of one class, its name and the shape of each of its slots."
    class_name: str = Field(default=..., title="Class name", description="The name of a class of the schema.")
    slots: Optional[list[SlotShape]] = Field(default=None, title="Slots", description="The shapes of a class\u0027s slots, in schema order.")


class FieldFlags(ConfiguredBaseModel):
    "The two flags a field of a generated model and a slot of a schema are compared by: whether a value is required and whether the field takes several."
    required: bool = Field(default=..., title="Required", description="Whether a value is required.")
    multivalued: bool = Field(default=..., title="Multivalued", description="Whether the slot takes several values.")


class Violation(ConfiguredBaseModel):
    "A hand-written model or a generated artefact that a guard found out of place."
    where: str = Field(default=..., title="Where", description="The place of a violation, a file and a line or a path.")
    what: str = Field(default=..., title="What", description="What is wrong at that place.")


class ContainerMarker(ConfiguredBaseModel):
    "A pytest marker of the container tests, the container it starts and its help text."
    marker: str = Field(default=..., title="Marker", description="The name of a pytest marker.")
    container: str = Field(default=..., title="Container", description="The name of a container the testkit starts.")
    help: str = Field(default=..., title="Help", description="A line of help text.")


class ExecResult(ConfiguredBaseModel):
    "What a command run inside a container printed, and how it ended."
    stdout: str = Field(default=..., title="Standard output", description="What the command wrote to its standard output.")
    stderr: str = Field(default=..., title="Standard error", description="What the command wrote to its standard error.")
    exit_code: int = Field(default=..., title="Exit code", description="The exit code the command ended with.")


class FusekiServer(ConfiguredBaseModel):
    "Where the test Fuseki answers, and the one user it admits."
    url: str = Field(default=..., title="URL", description="The base URL a server answers on.")
    user: str = Field(default=..., title="User", description="The user name the server admits.")
    password: str = Field(default=..., title="Password", description="The password of the user.", repr=False)


class GarageServer(ConfiguredBaseModel):
    "The S3 endpoint of the test Garage and the key bootstrapped on it."
    endpoint: str = Field(default=..., title="Endpoint", description="The URL of the S3 endpoint.")
    key_id: str = Field(default=..., title="Key id", description="The id of the access key.")
    secret: str = Field(default=..., title="Secret", description="The secret of the access key.", repr=False)
    region: str = Field(default=..., title="Region", description="The region name the S3 client signs for.")


class ZitadelServer(ConfiguredBaseModel):
    "Where the test Zitadel answers, and the admin machine user\u0027s personal access token, which authenticates the management API for provisioning a project, an application and machine users."
    url: str = Field(default=..., title="URL", description="The base URL a server answers on.")
    admin_pat: str = Field(default=..., title="Admin PAT", description="The personal access token of the admin machine user.", repr=False)


class MachineUser(ConfiguredBaseModel):
    "A service account provisioned in the test Zitadel, with the private key it signs its JWT-profile assertions with."
    name: str = Field(default=..., title="Name", description="The name of the thing a record describes (a slot, a user).")
    user_id: str = Field(default=..., title="User id", description="The id of a user in the identity provider.")
    key_id: str = Field(default=..., title="Key id", description="The id of the access key.")
    private_key: str = Field(default=..., title="Private key", description="The PEM private key of a machine user\u0027s key pair.", repr=False)


class ZitadelProject(ConfiguredBaseModel):
    "The project provisioned in the test Zitadel: the organisation and project ids, the machine users of the test principals, and the server that holds them."
    server: ZitadelServer = Field(default=..., title="Server", description="The test server a provisioned resource lives on.")
    organisation_id: str = Field(default=..., title="Organisation id", description="The id of the organisation that owns the provisioned resources.")
    project_id: str = Field(default=..., title="Project id", description="The id of the provisioned project, whose audience scope puts it in a token.")
    machine_users: Optional[list[MachineUser]] = Field(default=None, title="Machine users", description="The service accounts of the test principals.")


# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
SlotShape.model_rebuild()
ClassShape.model_rebuild()
FieldFlags.model_rebuild()
Violation.model_rebuild()
ContainerMarker.model_rebuild()
ExecResult.model_rebuild()
FusekiServer.model_rebuild()
GarageServer.model_rebuild()
ZitadelServer.model_rebuild()
MachineUser.model_rebuild()
ZitadelProject.model_rebuild()
