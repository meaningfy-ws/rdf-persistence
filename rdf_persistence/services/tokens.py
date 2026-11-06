"""The token-verifier port (PD-1): the consumer wires an implementation, entrypoints call it.

Only JWT access tokens are supported; opaque tokens need introspection and are not (access-control,
identity).
"""

from collections.abc import Callable
from typing import Protocol

from rdf_persistence.domain.generated.service.rp_service import VerifiedCaller

EpochClock = Callable[[], float]
"""A clock that answers seconds since the epoch, as the ``exp`` and ``nbf`` claims count them."""


class TokenVerifier(Protocol):
    """Turns an access token into the caller it identifies."""

    async def verify(self, token: str) -> VerifiedCaller:
        """The caller a valid token identifies.

        Raises:
            InvalidToken: The token is missing, malformed, expired, not yet valid, badly signed,
                signed with an algorithm or key we do not accept, or for another issuer or audience.
            IdentityUnavailable: The provider's keys cannot be had and none are cached.
        """
        ...
