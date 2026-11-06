"""``TokenSigner``: issues JWTs and serves the matching JWKS and discovery document, in memory.

Pass ``signer.client`` as the ``http_client`` of a ``JwksTokenVerifier``; no network is involved.
"""

import time
from collections.abc import Callable, Mapping, Sequence
from typing import Final

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

ISSUER: Final = "https://idp.test"
AUDIENCE: Final = "rp-test"
ZITADEL_ROLES_CLAIM: Final = "urn:zitadel:iam:org:project:roles"
DEFAULT_KID: Final = "test-key-1"
DEFAULT_LIFETIME_SECONDS: Final = 300.0
ORG_ID, ORG_DOMAIN = "org-1", "org.test"
SERVICE_UNAVAILABLE = 503

Clock = Callable[[], float]


class TokenSigner:
    """An identity provider for tests: RSA keys, tokens, and the endpoints a verifier reads."""

    def __init__(
        self,
        *,
        kid: str = DEFAULT_KID,
        audience: str = AUDIENCE,
        roles_claim: str = ZITADEL_ROLES_CLAIM,
        clock: Clock = time.time,
    ) -> None:
        self.kid = kid
        self.audience = audience
        self.roles_claim = roles_claim
        self.unreachable = False
        self.jwks_requests = 0
        self.discovery_requests = 0
        self._clock = clock
        self._keys: dict[str, rsa.RSAPrivateKey] = {}
        self.rotate(kid)
        self.client = httpx.AsyncClient(transport=httpx.MockTransport(self.handle))

    @property
    def public_key(self) -> rsa.RSAPublicKey:
        """The public half of the current signing key."""
        return self._keys[self.kid].public_key()

    def rotate(self, kid: str) -> None:
        """Add a fresh key and sign with it from now on; earlier keys stay in the JWKS."""
        self._keys[kid] = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = kid

    def issue(
        self,
        *,
        sub: str | None = "user-1",
        roles: Sequence[str] | None = (),
        expires_in: float | None = DEFAULT_LIFETIME_SECONDS,
        not_before_in: float | None = None,
        issuer: str = ISSUER,
        audience: str | None = None,
        kid: str | None = None,
        with_kid: bool = True,
        extra: Mapping[str, object] | None = None,
    ) -> str:
        """A signed token; ``None`` for ``sub``, ``expires_in`` or ``roles`` leaves that claim out.

        ``kid`` names the key in the header; the token is signed with that key if the signer has it,
        otherwise with the current one. ``expires_in`` and ``not_before_in`` are seconds from the clock.
        """
        now = self._clock()
        claims: dict[str, object] = {"iss": issuer, "aud": audience or self.audience, "iat": now}
        if sub is not None:
            claims["sub"] = sub
        if expires_in is not None:
            claims["exp"] = now + expires_in
        if not_before_in is not None:
            claims["nbf"] = now + not_before_in
        if roles is not None:
            claims[self.roles_claim] = {role: {ORG_ID: ORG_DOMAIN} for role in roles}
        claims.update(extra or {})
        header_kid = kid or self.kid
        key = self._keys.get(header_kid, self._keys[self.kid])
        return jwt.encode(
            claims, key, algorithm="RS256", headers={"kid": header_kid} if with_kid else None
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        """The provider: discovery at the well-known path, the JWKS at ``/keys``."""
        if self.unreachable:
            return httpx.Response(SERVICE_UNAVAILABLE)
        if request.url.path.endswith("/.well-known/openid-configuration"):
            self.discovery_requests += 1
            return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": f"{ISSUER}/keys"})
        self.jwks_requests += 1
        return httpx.Response(
            200, json={"keys": [self._jwk(kid, key) for kid, key in self._keys.items()]}
        )

    @staticmethod
    def _jwk(kid: str, key: rsa.RSAPrivateKey) -> Mapping[str, object]:
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
        return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}
