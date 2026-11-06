"""Test helpers shipped with the toolkit.

This package imports nothing heavy: the token signer and the Zitadel provisioning (which load
``PyJWT`` and ``cryptography``) are loaded on first use. The container fixtures live in
``rdf_persistence.testkit.containers`` and need the extra ``rdf-persistence[testkit]``.
"""

from importlib import import_module
from typing import TYPE_CHECKING, Any

from rdf_persistence.testkit.fakes import FakeFileStore, FakeIdentity, FakeStore, fake_session
from rdf_persistence.testkit.network import no_network

if TYPE_CHECKING:  # what the lazy names are, for type checkers and editors
    from rdf_persistence.testkit.tokens import TokenSigner
    from rdf_persistence.testkit.zitadel import access_token, create_machine_user, provision_project

_LAZY_MODULES = {
    "TokenSigner": "rdf_persistence.testkit.tokens",
    "access_token": "rdf_persistence.testkit.zitadel",
    "create_machine_user": "rdf_persistence.testkit.zitadel",
    "provision_project": "rdf_persistence.testkit.zitadel",
}


def __getattr__(name: str) -> Any:
    """Load a token or Zitadel helper on first use, then keep it."""
    if name not in _LAZY_MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(_LAZY_MODULES[name]), name)
    globals()[name] = value
    return value


__all__ = [
    "FakeFileStore",
    "FakeIdentity",
    "FakeStore",
    "TokenSigner",
    "access_token",
    "create_machine_user",
    "fake_session",
    "no_network",
    "provision_project",
]
