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

from rdf_persistence.adapters.generated.rp_wire import DiscoveryDocument, JwtClaims
from rdf_persistence.core.adapters._http import HttpAdapter
from rdf_persistence.core.domain.exceptions import IdentityUnavailable, InvalidToken
from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
from rdf_persistence.services.generated.service.rp_service import VerifiedCaller
from rdf_persistence.services.generated.settings.rp_settings import JwksSettings
from rdf_persistence.services.iris import DEFAULT_IRIS, Iris
from rdf_persistence.services.tokens import EpochClock

RS256 = "RS256"  # the testkit signs with it
# Asymmetric only (DEC-1): `none` and the HS* family are refused at construction, even when listed
# (the settings model refuses them too; this holds for a group built without its checks).
UNSIGNED_ALGORITHM = "none"
SYMMETRIC_PREFIX = "HS"
HTTPS_PREFIX = "https://"
DISCOVERY_PATH = "/.well-known/openid-configuration"
SIGNATURE_USE = "sig"
VERIFY_OPERATION = "verify"
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
        jwks: JwksSettings | None = None,
        http: HttpSettings | None = None,
    ) -> None:
        """Verify tokens of ``issuer``, which must be an https URL unless ``allow_insecure_issuer`` (test containers).

        ``jwks`` holds the signature algorithms accepted (``allowed_algorithms``), the clock skew allowed
        on ``exp`` and ``nbf`` (``leeway_seconds``, within 0 to 300 by the settings model), and the key
        cache's lifetime and refresh cooldown; ``ValueError`` for a cooldown longer than the TTL, or an algorithm list that is empty or holds
        ``none``, an ``HS*`` name (any case) or a name PyJWT does not implement. ``http`` sets the client's
        timeouts. Each defaults to a fresh default instance.
        """
        jwks = jwks or JwksSettings()
        for name, value in (
            ("issuer", issuer),
            ("audience", audience),
            ("roles_claim", roles_claim),
        ):
            if not value:
                raise ValueError(f"the {name} must not be empty")
        if not allow_insecure_issuer and not issuer.startswith(HTTPS_PREFIX):
            raise ValueError("the issuer must be an https URL")
        self._algorithms = frozenset(_checked_algorithms(jwks.allowed_algorithms))
        self._leeway = jwks.leeway_seconds
        self._ttl = jwks.ttl_seconds
        # Keys are refreshed at most this often (stale or unknown kid alike), so neither an outage nor a
        # burst of forged kids can hammer the provider; inside it the verifier answers at once.
        self._cooldown = jwks.unknown_kid_cooldown_seconds
        if self._cooldown > self._ttl:
            raise ValueError(
                f"the refresh cooldown ({self._cooldown} s) must not be longer than the key cache "
                f"TTL ({self._ttl} s): every token would be refused for the difference"
            )
        super().__init__(transport=transport, http=http)
        self._issuer = issuer
        self._iris = iris
        self._audience = audience
        self._roles_claim = roles_claim
        self._jwks_uri = jwks_uri
        self._clock = clock
        self._keys: dict[str, Mapping[str, object]] = {}
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
        jwk = await self._key_for(kid)
        claims = self._decode(token, self._bound_key(jwk, algorithm), algorithm)
        return VerifiedCaller(
            principal=self._principal(claims.sub), global_roles=self._roles(claims)
        )

    def _header(self, token: str) -> tuple[str, str]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise InvalidToken("the token is malformed") from error
        algorithm, kid = header.get("alg"), header.get("kid")
        if not isinstance(algorithm, str) or algorithm not in self._algorithms:
            raise InvalidToken("the token's algorithm is not accepted")
        if not isinstance(kid, str) or not kid:
            raise InvalidToken("the token names no key (kid)")
        return algorithm, kid

    @staticmethod
    def _bound_key(jwk: Mapping[str, object], algorithm: str) -> jwt.PyJWK:
        """The key of ``jwk`` bound to the token's (already allowed) ``algorithm``.

        A JWK that names another ``alg`` is refused; one that names none is bound to the token's, since
        PyJWT would otherwise infer ``RS256`` for every RSA key. A key type the algorithm cannot use is refused.
        """
        named = jwk.get("alg")
        if named is not None and named != algorithm:
            raise InvalidToken("the token's algorithm does not match its key")
        try:
            return jwt.PyJWK(dict(jwk), algorithm=algorithm)
        except (jwt.InvalidKeyError, jwt.PyJWKError) as error:
            raise InvalidToken("the token's key does not fit its algorithm") from error

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

    async def _key_for(self, kid: str) -> Mapping[str, object]:
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
        return self._fetched_at is None or self._clock() - self._fetched_at >= self._ttl

    def _cooled_down(self) -> bool:
        return self._attempted_at is None or self._clock() - self._attempted_at >= self._cooldown

    async def _refresh(self) -> None:
        self._attempted_at = self._clock()
        uri = self._jwks_uri or await self._discover()
        try:
            keys = self._usable_keys(json.loads(await self._fetch(uri)))
        except (ValueError, jwt.PyJWTError, TypeError, AttributeError) as error:
            raise IdentityUnavailable("the issuer's key set is unusable") from error
        self._keys = keys
        self._fetched_at = self._clock()
        self._jwks_uri = uri

    @staticmethod
    def _usable_keys(document: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
        """The JWKs of ``document`` by ``kid``: those that build into a ``PyJWK``, name a ``kid`` and may verify.

        As ``PyJWKSet`` does, a key that does not build is skipped; no usable key is an error.
        A key whose ``use`` is present and not ``sig``, or whose ``key_ops`` is present and lacks
        ``verify``, is skipped (RFC 7517 sections 4.2 and 4.3).
        """
        usable: dict[str, Mapping[str, object]] = {}
        for jwk in document["keys"]:  # type: ignore[attr-defined]
            kid = jwk.get("kid") if isinstance(jwk, Mapping) else None
            if not isinstance(kid, str) or not kid:
                continue
            if not JwksTokenVerifier._may_verify(jwk):
                continue
            try:
                jwt.PyJWK(dict(jwk))
            except jwt.PyJWTError:
                continue
            usable[kid] = jwk
        if not usable:
            raise jwt.PyJWKSetError("the key set has no usable key")
        return usable

    @staticmethod
    def _may_verify(jwk: Mapping[str, object]) -> bool:
        """Whether the key's ``use`` and ``key_ops``, when present, allow verifying signatures."""
        if jwk.get("use", SIGNATURE_USE) != SIGNATURE_USE:
            return False
        key_ops = jwk.get("key_ops")
        return key_ops is None or (isinstance(key_ops, list) and VERIFY_OPERATION in key_ops)

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
