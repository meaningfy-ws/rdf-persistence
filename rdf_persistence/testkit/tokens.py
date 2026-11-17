"""``TokenSigner``: issues JWTs and serves the matching JWKS and discovery document, in memory.

Pass ``signer.transport`` as the ``transport`` of a ``JwksTokenVerifier``; no network is involved.
"""

import functools
import time
from collections.abc import Callable, Mapping, Sequence
from http import HTTPStatus
from typing import Final

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

from rdf_persistence.adapters.generated.rp_wire import DiscoveryDocument
from rdf_persistence.adapters.jwks import DISCOVERY_PATH, RS256
from rdf_persistence.adapters.zitadel import zitadel_roles_claim
from rdf_persistence.services.tokens import EpochClock

ISSUER: Final = "https://idp.test"
AUDIENCE: Final = "rp-test"
PROJECT_ID: Final = "test-project"
DEFAULT_KID: Final = "test-key-1"
DEFAULT_LIFETIME_SECONDS: Final = 300.0
ORG_ID, ORG_DOMAIN = "org-1", "org.test"
KEYS_PATH = "/keys"


type SigningKey = rsa.RSAPrivateKey | ec.EllipticCurvePrivateKey | ed25519.Ed25519PrivateKey

type PublicKey = rsa.RSAPublicKey | ec.EllipticCurvePublicKey | ed25519.Ed25519PublicKey

EDDSA = "EdDSA"
EC_CURVES: Final[Mapping[str, Callable[[], ec.EllipticCurve]]] = {
    "ES256": ec.SECP256R1,
    "ES384": ec.SECP384R1,
    "ES512": ec.SECP521R1,
}


def new_key(algorithm: str = RS256) -> SigningKey:
    """A fresh signing key that fits ``algorithm``: RSA 2048 (RS*, PS*), the curve of ES256, ES384
    or ES512 (P-256, P-384, P-521), or Ed25519 (EdDSA). Generating an RSA key takes noticeable time,
    so share one where distinctness does not matter (see :func:`shared_key`)."""
    if algorithm in EC_CURVES:
        return ec.generate_private_key(EC_CURVES[algorithm]())
    if algorithm == EDDSA:
        return ed25519.Ed25519PrivateKey.generate()
    if algorithm.startswith(("RS", "PS")):
        return rsa.generate_private_key(public_exponent=65537, key_size=2048)
    raise ValueError(f"no signing key for the algorithm {algorithm!r}")


@functools.cache
def shared_key() -> rsa.RSAPrivateKey:
    """One signing key per process, for tests that need a key but not a distinct one.

    Never use it for a key the verifier must not trust (a forged or foreign signature): every
    caller gets the same key, so it would be trusted. Use :func:`new_key` there.
    """
    key = new_key()
    assert isinstance(key, rsa.RSAPrivateKey)  # RS256 gives RSA
    return key


class TokenSigner:
    """An identity provider for tests: signing keys, tokens, and the endpoints a verifier reads."""

    def __init__(
        self,
        *,
        kid: str = DEFAULT_KID,
        audience: str = AUDIENCE,
        roles_claim: str = zitadel_roles_claim(PROJECT_ID),
        clock: EpochClock = time.time,
        key: SigningKey | None = None,
        algorithm: str = RS256,
    ) -> None:
        """``key`` is the first signing key, for tests that share one; without it, a fresh one that fits
        ``algorithm``, the algorithm every token is signed with and every JWK names."""
        self.algorithm = algorithm
        self.kid = kid
        self.audience = audience
        self.roles_claim = roles_claim
        self.unreachable = False
        self.jwks_requests = 0
        self.discovery_requests = 0
        self._clock = clock
        self._keys: dict[str, SigningKey] = {kid: new_key(algorithm) if key is None else key}
        self.transport = httpx.MockTransport(self.handle)

    @property
    def public_key(self) -> PublicKey:
        """The public half of the current signing key."""
        return self._keys[self.kid].public_key()

    def rotate(self, kid: str) -> None:
        """Add a fresh key and sign with it from now on; earlier keys stay in the JWKS."""
        self._keys[kid] = new_key(self.algorithm)
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
            claims, key, algorithm=self.algorithm, headers={"kid": header_kid} if with_kid else None
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        """The provider: discovery at the well-known path, the JWKS at ``/keys``."""
        if self.unreachable:
            return httpx.Response(HTTPStatus.SERVICE_UNAVAILABLE)
        if request.url.path.endswith(DISCOVERY_PATH):
            self.discovery_requests += 1
            document = DiscoveryDocument(issuer=ISSUER, jwks_uri=f"{ISSUER}{KEYS_PATH}")
            return httpx.Response(HTTPStatus.OK, json=document.model_dump())
        self.jwks_requests += 1
        return httpx.Response(
            HTTPStatus.OK, json={"keys": [self._jwk(kid, key) for kid, key in self._keys.items()]}
        )

    def _jwk(self, kid: str, key: SigningKey) -> Mapping[str, object]:
        jwk = jwt.get_algorithm_by_name(self.algorithm).to_jwk(key.public_key(), as_dict=True)
        return {**jwk, "kid": kid, "use": "sig", "alg": self.algorithm}
