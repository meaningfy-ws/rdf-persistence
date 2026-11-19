"""Steps of ``token_algorithms.feature``: the verifier follows the provider's signing algorithm, on the toy service with the fakes (rp-identity)."""

import asyncio
import re
import time
from collections.abc import Collection

import httpx
import jwt
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from rdf_persistence import JwksSettings
from rdf_persistence.access.adapters.jwks import RS256, JwksTokenVerifier
from rdf_persistence.testkit import TokenSigner, shared_key
from rdf_persistence.testkit.tokens import AUDIENCE, ISSUER
from tests.toy_service import TENANT_BODY, ToyService, assert_problem

scenarios("token_algorithms.feature")

KID = "provider-key"
KEYS_URI = f"{ISSUER}/keys"
SUBJECT = "ada"
LIFETIME_SECONDS = 300
MINUTE_SECONDS = 60
SKEW_SECONDS = 10


class Run:
    """One service, the verifier a scenario puts in front of it and what it has answered."""

    def __init__(self) -> None:
        self.toy = ToyService()
        asyncio.run(self.toy.kit.tenancy.ensure_system_database())
        self.service_verifier = self.toy.kit.verifier
        self.signer = TokenSigner(key=shared_key())
        self.token: str | None = None
        self.answer: httpx.Response | None = None
        self.algorithms: Collection[str] | None = None
        self.build_error: ValueError | None = None
        self.created = 0  # the libraries the accepted requests created

    def serve_with(self, verifier: JwksTokenVerifier) -> None:
        """Let ``verifier`` check the tokens of the service."""
        self.toy.kit.verifier = verifier

    def request(self, token: str) -> httpx.Response:
        """Create a library, the request a handler answers, with ``token``."""

        async def send() -> httpx.Response:
            async with self.toy.client() as http:
                return await http.post(
                    "/libraries", json=TENANT_BODY, headers={"Authorization": f"Bearer {token}"}
                )

        self.answer = asyncio.run(send())
        return self.answer

    def libraries_ada_has(self) -> list[dict]:
        """What the library service lists for Ada, asked with its own verifier."""
        self.toy.kit.verifier = self.service_verifier

        async def send() -> httpx.Response:
            async with self.toy.client() as http:
                return await http.get("/libraries", headers=self.toy.bearer(SUBJECT))

        listing = asyncio.run(send())
        assert listing.status_code == 200, listing.text
        return listing.json()["items"]


def verifier_of(signer: TokenSigner, **kwargs: object) -> JwksTokenVerifier:
    return JwksTokenVerifier(
        ISSUER, signer.audience, signer.roles_claim, transport=signer.transport, **kwargs
    )


def rsa_jwk(**extra: object) -> dict[str, object]:
    """The provider's published RSA key, with ``extra`` members (an ``alg``, say)."""
    jwk = jwt.get_algorithm_by_name(RS256).to_jwk(shared_key().public_key(), as_dict=True)
    return {**jwk, "kid": KID, "use": "sig", **extra}


def publish(run: Run, jwk: dict[str, object]) -> None:
    """Let the service trust a provider whose key set holds ``jwk``."""
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"keys": [jwk]}))
    run.serve_with(
        JwksTokenVerifier(
            ISSUER,
            AUDIENCE,
            run.signer.roles_claim,
            jwks_uri=KEYS_URI,
            transport=transport,
        )
    )


def token_signed_with_the_published_key(algorithm: str) -> str:
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": SUBJECT,
        "exp": time.time() + LIFETIME_SECONDS,
    }
    return jwt.encode(claims, shared_key(), algorithm=algorithm, headers={"kid": KID})


@pytest.fixture
def run() -> Run:
    return Run()


@given("a deployment with the default allowed algorithms")
def _default_algorithms(run: Run) -> None:
    run.signer = TokenSigner(algorithm="ES384")
    run.serve_with(verifier_of(run.signer))


@given("the provider publishes an RSA key that names no algorithm")
def _key_without_algorithm(run: Run) -> None:
    publish(run, rsa_jwk())


@given("the provider publishes an RSA key that names RS256")
def _key_naming_rs256(run: Run) -> None:
    publish(run, rsa_jwk(alg=RS256))


@given(parsers.parse("a deployment that lists {algorithm} among its allowed algorithms"))
def _lists_algorithm(run: Run, algorithm: str) -> None:
    run.algorithms = [RS256, algorithm]


@given(
    parsers.parse(
        "a deployment that lists {algorithm}, which the verification library does not implement"
    )
)
def _lists_unimplemented_algorithm(run: Run, algorithm: str) -> None:
    run.algorithms = [RS256, algorithm]


@given("the default clock skew")
def _default_skew(run: Run) -> None:
    run.serve_with(verifier_of(run.signer))


@when(parsers.re(r"a request carries a valid token signed with (?P<algorithm>\S+)"))
def _request_with_valid_token(run: Run, algorithm: str) -> None:
    assert run.signer.algorithm == algorithm, "the provider signs with that algorithm"
    run.request(run.signer.issue(sub=SUBJECT))


@when(parsers.parse("a request carries a valid token signed with that key and {algorithm}"))
def _request_signed_with_the_key(run: Run, algorithm: str) -> None:
    run.request(token_signed_with_the_published_key(algorithm))


@when(parsers.parse("a request carries a token with that key's id and the algorithm {algorithm}"))
def _request_with_the_keys_id(run: Run, algorithm: str) -> None:
    run.request(token_signed_with_the_published_key(algorithm))


@when("the service is built")
def _build(run: Run) -> None:
    assert run.algorithms is not None, "the deployment lists its algorithms"
    try:
        # the settings model refuses `none` and `HS*`, the verifier a name PyJWT lacks;
        # a pydantic ValidationError is a ValueError, so either refusal is caught here
        jwks = JwksSettings(allowed_algorithms=list(run.algorithms))
        verifier_of(run.signer, jwks=jwks)
    except ValueError as error:
        run.build_error = error


@when(parsers.parse("a request carries a token that expired {seconds} ago by the service's clock"))
def _request_with_an_expired_token(run: Run, seconds: str) -> None:
    ago = MINUTE_SECONDS if seconds == "a minute" else int(seconds.split()[0])
    run.request(run.signer.issue(sub=SUBJECT, expires_in=-ago))


@then("the request is accepted")
def _accepted(run: Run) -> None:
    assert run.answer is not None, "a request was answered"
    assert run.answer.status_code == 201, run.answer.text
    run.created += 1


@then("the answer is 401 and no handler runs")
def _refused(run: Run) -> None:
    assert run.answer is not None, "a request was answered"
    assert_problem(run.answer, 401, "invalid-token")
    assert len(run.libraries_ada_has()) == run.created, "the refused request created nothing"


@then(parsers.parse("building fails, naming {algorithm}"))
def _building_fails(run: Run, algorithm: str) -> None:
    assert run.build_error is not None, "the service was not built"
    assert re.search(re.escape(algorithm), str(run.build_error)), "the refusal names the algorithm"
