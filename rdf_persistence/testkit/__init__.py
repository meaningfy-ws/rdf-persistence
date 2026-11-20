"""Test helpers shipped with the toolkit.

This package imports nothing heavy: the token signer and the Zitadel provisioning (which load
``PyJWT`` and ``cryptography``) are loaded on first use. The container fixtures live in
``rdf_persistence.testkit.containers`` and need the extra ``rdf-persistence[testkit]``.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from rdf_persistence.testkit.bootstrap import wait_until, wait_until_async
from rdf_persistence.testkit.exceptions import TokenRefusedError
from rdf_persistence.testkit.fakes import (
    FakeFileStore,
    FakeIdentity,
    FakeStore,
    InMemoryBroker,
    InMemoryEventBus,
    fake_session,
)
from rdf_persistence.testkit.generated.rp_testkit import OpenedStream, StreamEvent
from rdf_persistence.testkit.guards import assert_models_generated
from rdf_persistence.testkit.messages import RecordingObserver
from rdf_persistence.testkit.model_shape import model_schema_diff, model_shape_diff
from rdf_persistence.testkit.network import no_network
from rdf_persistence.testkit.public_imports import assert_public_imports
from rdf_persistence.testkit.shape_snapshot import (
    class_shapes,
    read_snapshot,
    snapshot_diff,
    write_snapshot,
)

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence.testkit.graphs import assert_isomorphic
    from rdf_persistence.testkit.streams import open_event_stream
    from rdf_persistence.testkit.tokens import TokenSigner, new_key, shared_key
    from rdf_persistence.testkit.zitadel import access_token, create_machine_user, provision_project

# public name -> (module, attribute); the token and Zitadel modules load ``PyJWT`` and
# ``cryptography`` (``graphs`` needs ``rdflib`` only)
_LAZY_NAMES = {
    "TokenSigner": ("rdf_persistence.testkit.tokens", "TokenSigner"),
    "new_key": ("rdf_persistence.testkit.tokens", "new_key"),
    "shared_key": ("rdf_persistence.testkit.tokens", "shared_key"),
    "access_token": ("rdf_persistence.testkit.zitadel", "access_token"),
    "create_machine_user": ("rdf_persistence.testkit.zitadel", "create_machine_user"),
    "provision_project": ("rdf_persistence.testkit.zitadel", "provision_project"),
    "assert_isomorphic": ("rdf_persistence.testkit.graphs", "assert_isomorphic"),
    "open_event_stream": ("rdf_persistence.testkit.streams", "open_event_stream"),
}


def __getattr__(name: str) -> Any:
    """Load a token, Zitadel or graph helper on first use, then keep it."""
    if name not in _LAZY_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = _LAZY_NAMES[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value


__all__ = [
    "assert_isomorphic",
    "assert_models_generated",
    "assert_public_imports",
    "FakeFileStore",
    "FakeIdentity",
    "FakeStore",
    "InMemoryBroker",
    "InMemoryEventBus",
    "OpenedStream",
    "RecordingObserver",
    "StreamEvent",
    "TokenRefusedError",
    "TokenSigner",
    "new_key",
    "access_token",
    "class_shapes",
    "create_machine_user",
    "fake_session",
    "model_schema_diff",
    "model_shape_diff",
    "no_network",
    "open_event_stream",
    "provision_project",
    "read_snapshot",
    "shared_key",
    "snapshot_diff",
    "wait_until",
    "wait_until_async",
    "write_snapshot",
]
