"""``JwksTokenVerifier``'s key handling: discovery, the cache, one refresh per unknown kid, an unreachable provider."""

import asyncio
import base64
import json
import math

import httpx
import jwt
import pytest

from rdf_persistence.adapters.jwks import DISCOVERY_PATH, JwksTokenVerifier
from rdf_persistence.domain.exceptions import IdentityUnavailable, InvalidToken
from rdf_persistence.services.generated.service.rp_service import IriPolicy, ServiceSettings
from rdf_persistence.services.generated.settings.rp_settings import JwksSettings
from rdf_persistence.services.iris import Iris
from rdf_persistence.testkit import TokenSigner, shared_key
from rdf_persistence.testkit.tokens import ISSUER, new_key

TTL_SECONDS = JwksSettings().ttl_seconds
PAST_COOLDOWN = 11.0
WITHIN_COOLDOWN = 1.0


class ManualClock:
    """A clock a test moves by hand."""

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock()


@pytest.fixture
def signer(clock: ManualClock) -> TokenSigner:
    return TokenSigner(clock=clock, key=shared_key())


def verifier_for(signer: TokenSigner, clock: ManualClock, **kwargs: object) -> JwksTokenVerifier:
    return JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        transport=signer.transport,
        clock=clock,
        **kwargs,
    )


async def test_keys_are_fetched_once_and_cached(signer: TokenSigner, clock: ManualClock) -> None:
    verifier = verifier_for(signer, clock)
    for _ in range(3):
        await verifier.verify(signer.issue())
    assert signer.jwks_requests == 1, "three valid tokens, one fetch"


async def test_an_explicit_jwks_uri_skips_discovery(
    signer: TokenSigner, clock: ManualClock
) -> None:
    seen: list[str] = []

    def spy(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return signer.handle(request)

    verifier = JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        jwks_uri=f"{ISSUER}/keys",
        transport=httpx.MockTransport(spy),
        clock=clock,
    )
    await verifier.verify(signer.issue())
    assert DISCOVERY_PATH not in seen, "no discovery request when the JWKS address is given"


async def test_the_cache_expires_after_the_ttl(signer: TokenSigner, clock: ManualClock) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    clock.now += TTL_SECONDS - 1
    await verifier.verify(signer.issue())
    assert signer.jwks_requests == 1, "still cached just before the TTL"
    clock.now += 2
    await verifier.verify(signer.issue())
    assert signer.jwks_requests == 2, "fetched again once the TTL has passed"


async def test_the_cache_lifetime_is_the_jwks_settings_ttl(
    signer: TokenSigner, clock: ManualClock
) -> None:
    """TC-30: a TTL of 1 second, the clock advanced 2 seconds: the keys are fetched again.

    The cooldown is 1 second as well: it also spaces the refresh of stale keys (10 seconds by
    default), so a TTL under it could not be seen to expire.
    """
    jwks = JwksSettings(ttl_seconds=1, unknown_kid_cooldown_seconds=1)
    verifier = verifier_for(signer, clock, jwks=jwks)
    await verifier.verify(signer.issue())
    clock.now += 2
    await verifier.verify(signer.issue())
    assert signer.jwks_requests == 2, "the keys were fetched again after the group's TTL"


async def test_the_refresh_cooldown_is_the_jwks_settings_cooldown(
    signer: TokenSigner, clock: ManualClock
) -> None:
    """TC-30: the cooldown of the group, not a constant, spaces the refreshes of an unknown kid."""
    verifier = verifier_for(signer, clock, jwks=JwksSettings(unknown_kid_cooldown_seconds=100))
    await verifier.verify(signer.issue())
    signer.rotate("k2")
    clock.now += PAST_COOLDOWN
    with pytest.raises(InvalidToken):
        await verifier.verify(signer.issue(kid="k2"))
    assert signer.jwks_requests == 1, "11 seconds is inside a cooldown of 100: no refresh"


async def test_an_unknown_kid_triggers_one_refresh_then_is_accepted(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    signer.rotate("k2")
    clock.now += PAST_COOLDOWN
    caller = await verifier.verify(signer.issue(sub="u2"))
    assert caller.principal.endswith("/u2"), "the rotated key is picked up"
    assert signer.jwks_requests == 2, "exactly one refresh"


async def test_a_burst_of_unknown_kids_refreshes_once(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    clock.now += PAST_COOLDOWN
    for _ in range(5):
        with pytest.raises(InvalidToken):
            await verifier.verify(signer.issue(kid="forged"))
    assert signer.jwks_requests == 2, (
        "the first unknown kid refreshes; the rest do not hammer the provider"
    )


async def test_discovery_is_not_repeated_on_refresh(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    clock.now += TTL_SECONDS + 1
    await verifier.verify(signer.issue())
    assert signer.discovery_requests == 1, "the JWKS address found once is kept"


async def test_unreachable_provider_with_no_cached_keys_is_unavailable(
    signer: TokenSigner, clock: ManualClock
) -> None:
    signer.unreachable = True
    with pytest.raises(IdentityUnavailable):
        await verifier_for(signer, clock).verify(signer.issue())


async def test_unreachable_provider_serves_cached_keys_until_the_ttl(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    signer.unreachable = True
    clock.now += TTL_SECONDS - 1
    await verifier.verify(signer.issue())
    clock.now += 2
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(signer.issue())


async def test_a_refresh_for_an_unknown_kid_that_fails_is_unavailable(
    signer: TokenSigner, clock: ManualClock
) -> None:
    verifier = verifier_for(signer, clock)
    await verifier.verify(signer.issue())
    signer.unreachable = True
    clock.now += PAST_COOLDOWN
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(signer.issue(kid="forged"))


async def test_a_transport_error_is_unavailable(clock: ManualClock) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    verifier = JwksTokenVerifier(
        ISSUER, "aud", "roles", transport=httpx.MockTransport(refuse), clock=clock
    )
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


@pytest.mark.parametrize(
    "body", ["not json", '{"no": "jwks_uri"}'], ids=["not-json", "no-jwks-uri"]
)
async def test_a_broken_discovery_document_is_unavailable(body: str, clock: ManualClock) -> None:
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, text=body))
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", transport=transport, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


async def test_a_jwks_without_a_usable_key_is_unavailable(clock: ManualClock) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == DISCOVERY_PATH:
            return httpx.Response(200, json={"jwks_uri": f"{ISSUER}/keys"})
        return httpx.Response(200, json={"keys": "oops"})

    transport = httpx.MockTransport(respond)
    verifier = JwksTokenVerifier(ISSUER, "aud", "roles", transport=transport, clock=clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(TokenSigner(clock=clock).issue())


# --- availability (PD-28a): a request never queues on the network for another's sake ----------


class StallingProvider:
    """A provider a test can hold: every request is counted, and waits for ``release`` while ``stalled``."""

    def __init__(self, signer: TokenSigner) -> None:
        self._signer = signer
        self.stalled = False
        self.calls = 0
        self.release = asyncio.Event()
        self.transport = httpx.MockTransport(self._handle)

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.calls += 1
        if self.stalled:
            await self.release.wait()
        return self._signer.handle(request)


async def let_tasks_run() -> None:
    for _ in range(20):
        await asyncio.sleep(0)


@pytest.fixture
def provider(signer: TokenSigner) -> StallingProvider:
    return StallingProvider(signer)


def verifier_over(provider: StallingProvider, signer: TokenSigner, clock: ManualClock):
    return JwksTokenVerifier(
        ISSUER, signer.audience, signer.roles_claim, transport=provider.transport, clock=clock
    )


async def test_a_forged_kid_during_a_slow_provider_does_not_delay_a_valid_token(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    good = signer.issue()
    await verifier.verify(good)
    clock.now += PAST_COOLDOWN
    provider.stalled = True
    forged = asyncio.create_task(verifier.verify(signer.issue(kid="forged")))
    await let_tasks_run()
    assert not forged.done(), "the forged-kid request is waiting on the provider"
    caller = await asyncio.wait_for(verifier.verify(good), timeout=1)
    assert caller.principal, "a cached key needs no lock and no network"
    provider.release.set()
    with pytest.raises(InvalidToken):
        await forged


async def test_requests_after_the_expiry_during_an_outage_make_one_provider_call(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    good = signer.issue()
    await verifier.verify(good)
    clock.now += TTL_SECONDS + 1
    signer.unreachable = True
    provider.stalled = True
    provider.calls = 0
    requests = [asyncio.create_task(verifier.verify(good)) for _ in range(5)]
    await let_tasks_run()
    provider.release.set()
    results = await asyncio.gather(*requests, return_exceptions=True)
    assert all(isinstance(result, IdentityUnavailable) for result in results), (
        "every request during the outage answers identity unavailable"
    )
    assert provider.calls == 1, "one refresh is made; the rest share its outcome"


async def test_stale_keys_inside_the_cooldown_are_unavailable_without_a_call(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    good = signer.issue()
    await verifier.verify(good)
    clock.now += TTL_SECONDS + 1
    signer.unreachable = True
    provider.calls = 0
    for _ in range(3):
        with pytest.raises(IdentityUnavailable):
            await verifier.verify(good)
        clock.now += WITHIN_COOLDOWN
    assert provider.calls == 1, "the cooldown holds for stale keys too"
    clock.now += PAST_COOLDOWN
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(good)
    assert provider.calls == 2, "and ends"


async def test_an_unknown_kid_during_an_outage_is_refused_not_unavailable(
    signer: TokenSigner, provider: StallingProvider, clock: ManualClock
) -> None:
    verifier = verifier_over(provider, signer, clock)
    await verifier.verify(signer.issue())
    clock.now += PAST_COOLDOWN
    signer.unreachable = True
    provider.calls = 0
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(signer.issue(kid="forged"))
    for _ in range(3):
        with pytest.raises(InvalidToken):
            await verifier.verify(signer.issue(kid="forged"))
    assert provider.calls == 1, "inside the cooldown the answer is immediate: 401, not 503"


# --- the issuer (PD-28a) -------------------------------------------------------------------


async def test_a_discovery_document_naming_another_issuer_is_unavailable(
    signer: TokenSigner, clock: ManualClock
) -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        if request.url.path == DISCOVERY_PATH:
            return httpx.Response(
                200, json={"issuer": "https://evil.test", "jwks_uri": f"{ISSUER}/keys"}
            )
        return signer.handle(request)

    verifier = JwksTokenVerifier(
        ISSUER,
        signer.audience,
        signer.roles_claim,
        transport=httpx.MockTransport(respond),
        clock=clock,
    )
    with pytest.raises(IdentityUnavailable, match="issuer"):
        await verifier.verify(signer.issue())


def test_an_issuer_that_is_not_https_is_refused() -> None:
    with pytest.raises(ValueError, match="https"):
        JwksTokenVerifier("http://idp.test", "aud", "roles")


def test_an_insecure_issuer_is_allowed_when_the_caller_opts_out() -> None:
    assert JwksTokenVerifier("http://idp.test", "aud", "roles", allow_insecure_issuer=True), (
        "a verifier that opts out of the secure-issuer rule is built"
    )


@pytest.mark.parametrize("field", ["issuer", "audience", "roles_claim"])
def test_an_empty_issuer_audience_or_roles_claim_is_refused(field: str) -> None:
    arguments = {"issuer": "https://idp.test", "audience": "aud", "roles_claim": "roles"}
    arguments[field] = ""
    with pytest.raises(ValueError, match=field):
        JwksTokenVerifier(**arguments)


# --- the principal IRI follows the IRI policy (PD-2, PD-3a) --------------------------------------

PRINCIPAL_BASE = "http://mwb.meaningfy.ws/"


async def test_the_default_principal_is_the_issuer_and_the_subject(
    signer: TokenSigner, clock: ManualClock
) -> None:
    caller = await verifier_for(signer, clock).verify(signer.issue(sub="user-1"))
    assert caller.principal == f"{ISSUER}/users/user-1", "the default principal IRI changed"


@pytest.mark.parametrize(
    ("sub", "segment"), [("a/b", "a%2Fb"), ("100%", "100%25"), ("a b", "a%20b")]
)
async def test_a_policy_principal_keeps_the_subject_in_one_segment(
    signer: TokenSigner, clock: ManualClock, sub: str, segment: str
) -> None:
    iris = Iris(
        ServiceSettings(
            base=PRINCIPAL_BASE,
            prefix="mwb",
            tenant_segment="projects",
            creator_role="owner",
            roles_claim=signer.roles_claim,
            deployment="k3f9a2x",
            iri_policy=IriPolicy(principal_template="{base}{deployment}/user/{sub}"),
        )
    )
    verifier = verifier_for(signer, clock, iris=iris)
    caller = await verifier.verify(signer.issue(sub=sub))
    assert caller.principal == f"{PRINCIPAL_BASE}k3f9a2x/user/{segment}", (
        "the subject left its segment"
    )


@pytest.mark.parametrize("sub", ["", ".", ".."])
async def test_a_dot_or_empty_subject_is_refused(
    signer: TokenSigner, clock: ManualClock, sub: str
) -> None:
    verifier = verifier_for(signer, clock)
    with pytest.raises(InvalidToken):
        await verifier.verify(signer.issue(sub=sub))


# --- the algorithm allow-list (PD-1, DEC-1) and the clock leeway (PD-3, DEC-2) -----------------

DEFAULT_ALGORITHM_NAMES = (
    "RS256",
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


@pytest.mark.parametrize("algorithm", DEFAULT_ALGORITHM_NAMES)
async def test_the_default_verifier_accepts_every_default_algorithm(
    clock: ManualClock, algorithm: str
) -> None:
    signer = TokenSigner(clock=clock, algorithm=algorithm)
    caller = await verifier_for(signer, clock).verify(signer.issue())
    assert caller.principal.endswith("/user-1"), f"a {algorithm} token was not accepted"


@pytest.mark.parametrize("named", ["ML-DSA-44", "ML-DSA-65"])
def test_an_algorithm_the_installed_pyjwt_does_not_implement_is_refused_at_construction(
    named: str,
) -> None:
    """TC-60: the settings model accepts the name (PD-6); the verifier's start-up check refuses it."""
    jwks = JwksSettings(allowed_algorithms=[named, "RS256"])
    with pytest.raises(ValueError, match=named):
        JwksTokenVerifier("https://idp.test", "aud", "roles", jwks=jwks)


@pytest.mark.parametrize(
    ("algorithms", "named"),
    [
        (["none"], "none"),
        (["NONE"], "NONE"),
        (["HS256"], "HS256"),
        (["hs512"], "hs512"),
        ([], "empty"),
        (["RS256", "HS512"], "HS512"),
    ],
    ids=["none", "NONE", "HS256", "hs512", "empty", "mixed"],
)
def test_a_group_that_got_past_the_schema_with_an_unusable_list_is_still_refused(
    algorithms: list[str], named: str
) -> None:
    """Defence in depth (DEC-1): ``model_construct`` skips the schema's checks, the verifier's hold."""
    jwks = JwksSettings.model_construct(allowed_algorithms=algorithms)
    with pytest.raises(ValueError, match=named):
        JwksTokenVerifier("https://idp.test", "aud", "roles", jwks=jwks)


async def test_a_token_outside_the_instance_algorithms_is_refused_before_any_key_fetch(
    signer: TokenSigner, clock: ManualClock
) -> None:
    """TC-31: A-3's test, through ``jwks=``."""
    verifier = verifier_for(signer, clock, jwks=JwksSettings(allowed_algorithms=["ES256"]))
    with pytest.raises(InvalidToken, match="algorithm"):
        await verifier.verify(signer.issue())
    assert signer.jwks_requests == 0, "the key set was fetched for a refused algorithm"


async def test_a_narrower_list_still_accepts_its_own_algorithm(clock: ManualClock) -> None:
    signer = TokenSigner(clock=clock, algorithm="ES256")
    """TC-31: A-3's test, through ``jwks=``."""
    jwks = JwksSettings(allowed_algorithms=["ES256"])
    caller = await verifier_for(signer, clock, jwks=jwks).verify(signer.issue())
    assert caller.principal, "an ES256 token under allowed_algorithms=['ES256'] was refused"


CLOCK_NOW = 1000.0


@pytest.mark.parametrize(
    ("exp", "accepted"),
    [(990, True), (971, True), (970, False), (940, False)],
)
async def test_the_default_leeway_lets_an_expired_token_through_for_30_seconds(
    signer: TokenSigner, clock: ManualClock, exp: float, accepted: bool
) -> None:
    clock.now = CLOCK_NOW
    verifier = verifier_for(signer, clock)
    token = signer.issue(expires_in=exp - CLOCK_NOW)
    if accepted:
        assert (await verifier.verify(token)).principal, f"exp {exp} should be within the leeway"
    else:
        with pytest.raises(InvalidToken, match="expired"):
            await verifier.verify(token)


@pytest.mark.parametrize(("nbf", "accepted"), [(1020, True), (1031, False)])
async def test_the_default_leeway_lets_an_early_token_through_for_30_seconds(
    signer: TokenSigner, clock: ManualClock, nbf: float, accepted: bool
) -> None:
    clock.now = CLOCK_NOW
    verifier = verifier_for(signer, clock)
    token = signer.issue(not_before_in=nbf - CLOCK_NOW)
    if accepted:
        assert (await verifier.verify(token)).principal, f"nbf {nbf} should be within the leeway"
    else:
        with pytest.raises(InvalidToken, match="not yet valid"):
            await verifier.verify(token)


@pytest.mark.parametrize(
    "leeway", [-1, 301, math.inf, math.nan], ids=["negative", "above-300", "inf", "nan"]
)
def test_a_leeway_outside_zero_to_300_or_not_finite_never_reaches_the_verifier(
    leeway: float,
) -> None:
    """TC-31: A-4's bounds test; the schema (TC-57) holds the bounds, so the group is refused."""
    with pytest.raises(ValueError, match="leeway_seconds"):
        JwksSettings(leeway_seconds=leeway)


async def test_a_zero_leeway_refuses_a_token_expiring_now(
    signer: TokenSigner, clock: ManualClock
) -> None:
    """TC-31: A-4's test, through ``jwks=``."""
    clock.now = CLOCK_NOW
    verifier = verifier_for(signer, clock, jwks=JwksSettings(leeway_seconds=0))
    with pytest.raises(InvalidToken, match="expired"):
        await verifier.verify(signer.issue(expires_in=0))


def test_the_verifier_exposes_the_iris_it_mints_with(
    signer: TokenSigner, clock: ManualClock
) -> None:
    iris = Iris(
        ServiceSettings(
            base="https://x.example/",
            prefix="rp",
            tenant_segment="t",
            creator_role="o",
            roles_claim="r",
        )
    )
    assert verifier_for(signer, clock, iris=iris).iris is iris, (
        "the verifier exposes the IRI policy it was given"
    )


# --- keys bound to the token's algorithm (PD-2) -----------------------------------------------


def _jwks_verifier(jwks: list[dict[str, object]], clock: ManualClock) -> JwksTokenVerifier:
    """A verifier over a JWKS the test wrote by hand, served by a mock transport."""
    transport = httpx.MockTransport(lambda _r: httpx.Response(200, json={"keys": jwks}))
    return JwksTokenVerifier(
        ISSUER, "aud", "roles", jwks_uri=f"{ISSUER}/keys", transport=transport, clock=clock
    )


def _public_jwk(key: object, algorithm: str, kid: str, **extra: object) -> dict[str, object]:
    jwk = jwt.get_algorithm_by_name(algorithm).to_jwk(key.public_key(), as_dict=True)  # type: ignore[attr-defined]
    return {**jwk, "kid": kid, **extra}


def _token(key: object, algorithm: str, kid: str, clock: ManualClock) -> str:
    claims = {"iss": ISSUER, "aud": "aud", "sub": "u1", "exp": clock.now + 300}
    return jwt.encode(claims, key, algorithm=algorithm, headers={"kid": kid})  # type: ignore[arg-type]


@pytest.mark.parametrize("algorithm", ["PS256", "RS384"])
async def test_an_rsa_key_without_alg_verifies_any_rsa_algorithm_the_token_names(
    clock: ManualClock, algorithm: str
) -> None:
    key = shared_key()
    verifier = _jwks_verifier([_public_jwk(key, "RS256", "k1")], clock)
    caller = await verifier.verify(_token(key, algorithm, "k1", clock))
    assert caller.principal.endswith("/u1"), f"a {algorithm} token on a key without alg was refused"


async def test_a_key_naming_another_algorithm_than_the_token_is_refused(
    clock: ManualClock,
) -> None:
    key = shared_key()
    verifier = _jwks_verifier([_public_jwk(key, "RS256", "k1", alg="RS256")], clock)
    with pytest.raises(InvalidToken, match="does not match its key"):
        await verifier.verify(_token(key, "PS256", "k1", clock))


async def test_a_key_of_a_type_that_does_not_fit_the_token_algorithm_is_refused(
    clock: ManualClock,
) -> None:
    ec_key = new_key("ES256")
    verifier = _jwks_verifier([_public_jwk(ec_key, "ES256", "k1")], clock)
    with pytest.raises(InvalidToken):
        await verifier.verify(_token(shared_key(), "RS256", "k1", clock))


async def test_a_jwks_whose_only_key_has_no_kty_is_unavailable(clock: ManualClock) -> None:
    verifier = _jwks_verifier([{"kid": "bad", "n": "AQAB", "e": "AQAB"}], clock)
    with pytest.raises(IdentityUnavailable):
        await verifier.verify(_token(shared_key(), "RS256", "bad", clock))


async def test_an_unusable_key_is_skipped_beside_a_good_one(clock: ManualClock) -> None:
    key = shared_key()
    verifier = _jwks_verifier([{"kid": "bad"}, _public_jwk(key, "RS256", "k1")], clock)
    assert (await verifier.verify(_token(key, "RS256", "k1", clock))).principal, (
        "the good key was refused beside a bad one"
    )
    with pytest.raises(InvalidToken, match="unknown to the issuer"):
        await verifier.verify(_token(key, "RS256", "bad", clock))


@pytest.mark.parametrize("alg", [["RS256"], {"a": 1}], ids=["list", "dict"])
async def test_a_token_whose_alg_is_not_a_string_is_refused(
    signer: TokenSigner, clock: ManualClock, alg: object
) -> None:
    def segment(value: object) -> str:
        return base64.urlsafe_b64encode(json.dumps(value).encode()).rstrip(b"=").decode()

    token = f"{segment({'alg': alg, 'kid': 'k1'})}.{segment({'sub': 'u1'})}.c2ln"
    with pytest.raises(InvalidToken, match="algorithm is not accepted"):
        await verifier_for(signer, clock).verify(token)
