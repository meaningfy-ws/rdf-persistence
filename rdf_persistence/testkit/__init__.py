"""Test helpers shipped with the toolkit.

This package imports nothing heavy: the token signer and the Zitadel provisioning (which load
``PyJWT`` and ``cryptography``) are loaded on first use. The container fixtures live in
``rdf_persistence.testkit.containers`` and need the extra ``rdf-persistence[testkit]``.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from rdf_persistence.testkit.bootstrap import wait_until, wait_until_async
from rdf_persistence.testkit.exceptions import TokenRefusedError
from rdf_persistence.testkit.fakes import FakeFileStore, FakeIdentity, FakeStore, fake_session
from rdf_persistence.testkit.guards import assert_models_generated
from rdf_persistence.testkit.model_shape import model_shape_diff
from rdf_persistence.testkit.network import no_network
from rdf_persistence.testkit.public_imports import assert_public_imports
from rdf_persistence.testkit.shape_snapshot import (
    class_shapes,
    read_snapshot,
    snapshot_diff,
    write_snapshot,
)

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence.testkit.conformance import Conformance
    from rdf_persistence.testkit.conformance import run as conformance_problems
    from rdf_persistence.testkit.roundtrip import round_trip
    from rdf_persistence.testkit.strategies import aggregate
    from rdf_persistence.testkit.tokens import TokenSigner
    from rdf_persistence.testkit.zitadel import access_token, create_machine_user, provision_project

# public name -> (module, attribute); the conformance, round-trip and strategy modules load
# ``pyshacl`` or ``hypothesis``
_LAZY_MODULES = {
    "TokenSigner": ("rdf_persistence.testkit.tokens", "TokenSigner"),
    "access_token": ("rdf_persistence.testkit.zitadel", "access_token"),
    "create_machine_user": ("rdf_persistence.testkit.zitadel", "create_machine_user"),
    "provision_project": ("rdf_persistence.testkit.zitadel", "provision_project"),
    "Conformance": ("rdf_persistence.testkit.conformance", "Conformance"),
    "conformance_problems": ("rdf_persistence.testkit.conformance", "run"),
    "round_trip": ("rdf_persistence.testkit.roundtrip", "round_trip"),
    "aggregate": ("rdf_persistence.testkit.strategies", "aggregate"),
}


def __getattr__(name: str) -> Any:
    """Load a token, Zitadel, conformance or strategy helper on first use, then keep it."""
    if name not in _LAZY_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module, attribute = _LAZY_MODULES[name]
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value


__all__ = [
    "Conformance",
    "assert_models_generated",
    "assert_public_imports",
    "FakeFileStore",
    "FakeIdentity",
    "FakeStore",
    "TokenRefusedError",
    "TokenSigner",
    "access_token",
    "aggregate",
    "class_shapes",
    "conformance_problems",
    "create_machine_user",
    "fake_session",
    "model_shape_diff",
    "no_network",
    "provision_project",
    "read_snapshot",
    "round_trip",
    "snapshot_diff",
    "wait_until",
    "wait_until_async",
    "write_snapshot",
]
