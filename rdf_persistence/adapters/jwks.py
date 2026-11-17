"""``TokenVerifier`` over a provider's JWKS: OIDC discovery, a timed key cache, JWT checks.

The principal is minted by ``Iris.principal``: by default ``{issuer}/users/{sub}``, where the issuer
already names the provider, so the IRI is stable and unique across providers, and ``sub`` is
percent-encoded so it cannot leave the path. A deployment's policy may set another template.
"""

import asyncio
import json
import math
import time
from collections.abc import Collection, Mapping
from http import HTTPMethod

import httpx
import jwt
from pydantic import ValidationError

from rdf_persistence.adapters._http import HttpAdapter
from rdf_persistence.adapters.generated.rp_wire import DiscoveryDocument, JwtClaims
from rdf_persistence.domain.exceptions import IdentityUnavailable, InvalidToken
from rdf_persistence.domain.generated.service.rp_service import VerifiedCaller
from rdf_persistence.domain.iris import DEFAULT_IRIS, Iris
from rdf_persistence.services.tokens import EpochClock

JWKS_TTL_SECONDS = 600.0
# Keys are refreshed at most this often (stale or unknown kid alike), so neither an outage nor a burst of
# forged kids can hammer the provider; inside it the verifier answers at once.
UNKNOWN_KID_COOLDOWN_SECONDS = 10.0
RS256 = "RS256"
# Asymmetric only (DEC-1): `none` and the HS* family are refused at construction, even when listed.
# The algorithms and the leeway are constructor parameters with these defaults; `technical-models`
# moves them into the generated settings model with the other JWKS values (DEC-3).
DEFAULT_ALGORITHMS = (
    RS256,
    "RS384",
    "RS512",
    "PS256",
    "PS384",
    "PS512",
    "ES256",
    "ES384",
    "ES512",
    "EdDSA",
)
DEFAULT_LEEWAY_SECONDS = 30.0
MAX_LEEWAY_SECONDS = 300.0
UNSIGNED_ALGORITHM = "none"
SYMMETRIC_PREFIX = "HS"
HTTPS_PREFIX = "https://"
DISCOVERY_PATH = "/.well-known/openid-configuration"
REQUIRED_CLAIMS = ("exp", "sub")
# A principal IRI ending in one of these is empty or a dot segment, which IRI normalisation resolves away (PD-14h).
UNUSABLE_SUBJECTS = ("", ".", "..")


def _checked_algorithms(algorithms: Collection[str]) -> Collection[str]:
    """``algorithms`` unchanged if each is a signature algorithm PyJWT implements, else ``ValueError``."""
    if not algorithms:
        raise ValueError("the algorithms must not be empty")
    implemented = jwt.algorithms.get_default_algorithms()
    for name in algorithms:
        if name.lower() == UNSIGNED_ALGORITHM.lower():
            raise ValueError(f"the algorithm {name!r} is unsigned and never accepted")
        if name.upper().startswith(SYMMETRIC_PREFIX):
            raise ValueError(f"the algorithm {name!r} is symmetric and never accepted")
        if name not in implemented:
            raise ValueError(
                f"the algorithm {name!r} is not implemented by the verification library"
            )
    return algorithms


class JwksTokenVerifier(HttpAdapter):
    """Verifies JWT access tokens against the keys of an OIDC issuer."""

    service = "The issuer"
    unavailable = IdentityUnavailable

    def __init__(
        self,
        issuer: str,
        audience: str,
        roles_claim: str,
        *,
        jwks_uri: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: EpochClock = time.time,
        allow_insecure_issuer: bool = False,
        iris: Iris = DEFAULT_IRIS,
        algorithms: Collection[str] = DEFAULT_ALGORITHMS,
        leeway_seconds: float = DEFAULT_LEEWAY_SECONDS,
    ) -> None:
        """Verify tokens of ``issuer``, which must be an https URL unless ``allow_insecure_issuer`` (test containers).

        ``algorithms`` are the signature algorithms accepted; ``ValueError`` for an empty collection,
        ``none``, an ``HS*`` name (any case) or a name PyJWT does not implement. ``leeway_seconds`` is the
        clock skew allowed on ``exp`` and ``nbf``; ``ValueError`` unless finite and within 0 to 300.
        """
        for name, value in (
            ("issuer", issuer),
            ("audience", audience),
            ("roles_claim", roles_claim),
        ):
            if not value:
                raise ValueError(f"the {name} must not be empty")
        if not allow_insecure_issuer and not issuer.startswith(HTTPS_PREFIX):
            raise ValueError("the issuer must be an https URL")
        self._algorithms = frozenset(_checked_algorithms(algorithms))
        if not math.isfinite(leeway_seconds) or not 0 <= leeway_seconds <= MAX_LEEWAY_SECONDS:
            raise ValueError(
                f"the leeway must be finite and within 0 to {MAX_LEEWAY_SECONDS:g} seconds, got {leeway_seconds}"
            )
        self._leeway = leeway_seconds
        super().__init__(transport=transport)
        self._issuer = issuer
        self._iris = iris
        self._audience = audience
        self._roles_claim = roles_claim
        self._jwks_uri = jwks_uri
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def iris(self) -> Iris:
        return self._iris

    async def verify(self, token: str) -> VerifiedCaller:
        if not token:
            raise InvalidToken("the token is missing")
        algorithm, kid = self._header(token)
        key = await self._key_for(kid)
        claims = self._decode(token, key, algorithm)
        return VerifiedCaller(
            principal=self._principal(claims.sub), global_roles=self._roles(claims)
        )

    def _header(self, token: str) -> tuple[str, str]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise InvalidToken("the token is malformed") from error
        algorithm, kid = header.get("alg"), header.get("kid")
        if algorithm not in self._algorithms:
            raise InvalidToken("the token's algorithm is not accepted")
        if not isinstance(kid, str) or not kid:
            raise InvalidToken("the token names no key (kid)")
        return algorithm, kid

    def _decode(self, token: str, key: jwt.PyJWK, algorithm: str) -> JwtClaims:
        now = self._clock()
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                issuer=self._issuer,
                audience=self._audience,
                # exp and nbf are checked below against the injected clock.
                options={
                    "verify_exp": False,
                    "verify_nbf": False,
                    "require": ["iss", "aud", *REQUIRED_CLAIMS],
                },
            )
        except jwt.PyJWTError as error:
            raise InvalidToken("the token is not valid") from error
        try:
            claims = JwtClaims.model_validate(payload)
        except ValidationError as error:
            raise InvalidToken("the token's claims are malformed") from error
        if not all(math.isfinite(t) for t in (claims.exp, claims.nbf or 0.0)):
            raise InvalidToken("the token's times are malformed")
        if claims.sub in UNUSABLE_SUBJECTS:
            raise InvalidToken("the token's subject cannot name a principal")
        if claims.exp + self._leeway <= now:
            raise InvalidToken("the token has expired")
        if claims.nbf is not None and claims.nbf - self._leeway > now:
            raise InvalidToken("the token is not yet valid")
        return claims

    def _principal(self, subject: str) -> str:
        return str(self._iris.principal(self._issuer, subject))

    def _roles(self, claims: JwtClaims) -> list[str]:
        claim = (claims.model_extra or {}).get(self._roles_claim)
        if isinstance(claim, Mapping | list):
            return [str(role) for role in claim]
        return []

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        if self._is_stale() or kid not in self._keys:
            await self._renew(kid)
        try:
            return self._keys[kid]
        except KeyError:
            raise InvalidToken("the token's key is unknown to the issuer") from None

    async def _renew(self, kid: str) -> None:
        """Refresh the keys if the cooldown allows; answer at once if it does not.

        The lock only makes a refresh single-flight: whoever gets it re-checks first, so requests that
        waited on a refresh share its outcome instead of starting another.
        """
        if not self._is_stale() and not self._cooled_down():
            return  # an unknown kid inside the cooldown: refused by the caller, no network
        async with self._lock:
            if (self._is_stale() or kid not in self._keys) and self._cooled_down():
                await self._refresh()
            if self._is_stale():
                raise IdentityUnavailable("the issuer's keys are out of date and cannot be renewed")

    def _is_stale(self) -> bool:
        return self._fetched_at is None or self._clock() - self._fetched_at >= JWKS_TTL_SECONDS

    def _cooled_down(self) -> bool:
        return (
            self._attempted_at is None
            or self._clock() - self._attempted_at >= UNKNOWN_KID_COOLDOWN_SECONDS
        )

    async def _refresh(self) -> None:
        self._attempted_at = self._clock()
        uri = self._jwks_uri or await self._discover()
        try:
            keys = jwt.PyJWKSet.from_dict(json.loads(await self._fetch(uri))).keys
        except (ValueError, jwt.PyJWTError, TypeError, AttributeError) as error:
            raise IdentityUnavailable("the issuer's key set is unusable") from error
        self._keys = {key.key_id: key for key in keys if key.key_id}
        self._fetched_at = self._clock()
        self._jwks_uri = uri

    async def _discover(self) -> str:
        content = await self._fetch(self._issuer.rstrip("/") + DISCOVERY_PATH)
        try:
            document = DiscoveryDocument.model_validate_json(content)
        except ValidationError as error:
            raise IdentityUnavailable("the issuer's discovery document is unusable") from error
        if document.issuer != self._issuer:
            raise IdentityUnavailable("the discovery document names another issuer")
        return document.jwks_uri

    async def _fetch(self, uri: str) -> bytes:
        response = await self.request(HTTPMethod.GET, uri)
        if not response.is_success:
            raise IdentityUnavailable(f"the issuer answered {response.status_code}")
        return response.content
