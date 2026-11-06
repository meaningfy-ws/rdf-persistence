"""``TokenVerifier`` over a provider's JWKS: OIDC discovery, a timed key cache, JWT checks.

The principal is ``{issuer}/users/{sub}``: the issuer already names the provider, so the IRI is
stable and unique across providers, and ``sub`` is percent-encoded so it cannot leave the path.
"""

import asyncio
import json
import time
from collections.abc import Callable, Mapping
from types import TracebackType
from typing import Self

import httpx
import jwt

from rdf_persistence.domain.exceptions import IdentityUnavailable, InvalidToken
from rdf_persistence.domain.generated.service.rp_service import VerifiedCaller
from rdf_persistence.domain.iris import principal_iri

JWKS_TTL_SECONDS = 600.0
# An unknown kid refreshes the keys at most this often, so a burst of forged kids cannot hammer the provider.
UNKNOWN_KID_COOLDOWN_SECONDS = 10.0
# Asymmetric only: `none` and the HS* family never verify.
ALLOWED_ALGORITHMS = ("RS256", "ES256")
DISCOVERY_PATH = "/.well-known/openid-configuration"
HTTP_TIMEOUT_SECONDS = 10.0
REQUIRED_CLAIMS = ("exp", "sub")

Clock = Callable[[], float]


class JwksTokenVerifier:
    """Verifies JWT access tokens against the keys of an OIDC issuer."""

    def __init__(
        self,
        issuer: str,
        audience: str,
        roles_claim: str,
        *,
        jwks_uri: str | None = None,
        http_client: httpx.AsyncClient | None = None,
        clock: Clock = time.time,
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._roles_claim = roles_claim
        self._jwks_uri = jwks_uri
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._attempted_at: float | None = None
        self._lock = asyncio.Lock()

    async def aclose(self) -> None:
        """Close the HTTP client, if this verifier made it."""
        if self._owns_client:
            await self._http.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def verify(self, token: str) -> VerifiedCaller:
        if not token:
            raise InvalidToken("the token is missing")
        algorithm, kid = self._header(token)
        key = await self._key_for(kid)
        claims = self._decode(token, key, algorithm)
        return VerifiedCaller(
            principal=self._principal(claims["sub"]), global_roles=self._roles(claims)
        )

    @staticmethod
    def _header(token: str) -> tuple[str, str]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as error:
            raise InvalidToken("the token is malformed") from error
        algorithm, kid = header.get("alg"), header.get("kid")
        if algorithm not in ALLOWED_ALGORITHMS:
            raise InvalidToken(f"the token's algorithm {algorithm!r} is not accepted")
        if not isinstance(kid, str) or not kid:
            raise InvalidToken("the token names no key (kid)")
        return algorithm, kid

    def _decode(self, token: str, key: jwt.PyJWK, algorithm: str) -> Mapping[str, object]:
        now = self._clock()
        try:
            claims = jwt.decode(
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
            raise InvalidToken(f"the token is not valid: {error}") from error
        if claims["exp"] <= now:
            raise InvalidToken("the token has expired")
        if claims.get("nbf", now) > now:
            raise InvalidToken("the token is not yet valid")
        return claims

    def _principal(self, subject: object) -> str:
        return str(principal_iri(self._issuer, str(subject)))

    def _roles(self, claims: Mapping[str, object]) -> list[str]:
        claim = claims.get(self._roles_claim)
        if isinstance(claim, Mapping | list):
            return [str(role) for role in claim]
        return []

    async def _key_for(self, kid: str) -> jwt.PyJWK:
        async with self._lock:
            if self._is_stale() or (kid not in self._keys and self._cooled_down()):
                await self._refresh()
        try:
            return self._keys[kid]
        except KeyError:
            raise InvalidToken(f"no key {kid!r} at the issuer") from None

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
        document = await self._get_json(uri)
        try:
            keys = jwt.PyJWKSet.from_dict(document).keys
        except (jwt.PyJWTError, TypeError, AttributeError) as error:
            raise IdentityUnavailable("the issuer's key set is unusable") from error
        self._keys = {key.key_id: key for key in keys if key.key_id}
        self._fetched_at = self._clock()
        self._jwks_uri = uri

    async def _discover(self) -> str:
        document = await self._get_json(self._issuer.rstrip("/") + DISCOVERY_PATH)
        uri = document.get("jwks_uri")
        if not isinstance(uri, str):
            raise IdentityUnavailable("the issuer's discovery document names no jwks_uri")
        return uri

    async def _get_json(self, uri: str) -> dict[str, object]:
        try:
            response = await self._http.get(uri)
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as error:
            raise IdentityUnavailable(f"cannot read {uri}") from error
        if not isinstance(document, dict):
            raise IdentityUnavailable(f"{uri} did not answer with a JSON object")
        return document
