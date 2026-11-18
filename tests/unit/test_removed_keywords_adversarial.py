"""Adversarial tests of the removed per-value keywords (technical-models stage 3, DEC-5, D-28 to D-36).

Attacks: 'an old keyword still accepted somewhere'. A scan of every constructor and public function
of the package for the names the settings groups replaced, and a probe of each constructor that had
one.
"""

import importlib
import inspect
import pkgutil
import warnings

import pytest

import rdf_persistence
from rdf_persistence.adapters.jwks import JwksTokenVerifier
from rdf_persistence.adapters.redis_events import RedisEventBus
from rdf_persistence.adapters.zitadel import ZitadelIdentity
from rdf_persistence.files.adapters.s3 import S3FileStore
from rdf_persistence.persistence.adapters.fuseki import FusekiStore
from rdf_persistence.persistence.services.mapper import Mapper
from rdf_persistence.services.event_hub import EventHub
from rdf_persistence.services.messagebus import MessageBus

REMOVED = {
    "retention",
    "claim_idle",
    "interval",
    "publish_timeout",
    "max_queue",
    "max_roots",
    "algorithms",
    "leeway_seconds",
    "access_ttl",
    "keep_alive",
    "resume_window",
    "max_lifetime",
    "connect_timeout",
    "read_timeout",
    "max_attempts",
    "page_size",
    "max_messages",
    "max_document_nodes",
    "max_manifest_bytes",
}
# a name that is still a parameter for a reason that is not a settings value, found by the scan:
# the service function the events route calls with the group's values, and a byte-counting helper
ALLOWED = {
    ("rdf_persistence.services.event_stream", "event_stream"),
    ("rdf_persistence.services.event_stream", "_live"),
    ("rdf_persistence.services.tenant_dump", "_Counted"),
    ("rdf_persistence.services.tenant_dump", "_Budget"),
}


def modules():
    for info in pkgutil.walk_packages(rdf_persistence.__path__, "rdf_persistence."):
        if ".generated" in info.name:
            continue
        with warnings.catch_warnings():  # the testkit shims warn on import (generator-package PD-3)
            warnings.simplefilter("ignore", DeprecationWarning)
            module = importlib.import_module(info.name)
        yield module


def test_no_constructor_or_function_of_the_package_has_a_removed_keyword() -> None:
    """Invariant: no constructor in ``rdf_persistence/`` still accepts a removed per-value keyword."""
    found = []
    for module in modules():
        for name, held in vars(module).items():
            if getattr(held, "__module__", None) != module.__name__:
                continue
            if not (inspect.isclass(held) or inspect.isfunction(held)):
                continue
            if name.startswith("_") or (module.__name__, name) in ALLOWED:
                continue  # a private helper's parameter is no consumer's keyword
            target = held.__init__ if inspect.isclass(held) else held
            try:
                parameters = inspect.signature(target).parameters
            except (TypeError, ValueError):
                continue
            found += [f"{module.__name__}.{name}({p})" for p in parameters if p in REMOVED]
    assert found == [], f"a removed keyword is still a parameter: {found}"


@pytest.mark.parametrize(
    ("build", "keyword"),
    [
        (lambda **k: JwksTokenVerifier("https://idp.test", "aud", "roles", **k), "algorithms"),
        (lambda **k: JwksTokenVerifier("https://idp.test", "aud", "roles", **k), "leeway_seconds"),
        (lambda **k: RedisEventBus("redis://localhost:1", deployment="d", **k), "stream"),
        (lambda **k: RedisEventBus("redis://localhost:1", deployment="d", **k), "retention"),
        (lambda **k: RedisEventBus("redis://localhost:1", deployment="d", **k), "claim_idle"),
        (lambda **k: FusekiStore("http://f.test", "u", "p", **k), "timeout"),
        (
            lambda **k: S3FileStore("http://s3.test", "id", "secret", "eu-west-1", **k),
            "max_attempts",
        ),
        (lambda **k: ZitadelIdentity("https://z.test", "t", "org", "project", **k), "page_size"),
        (lambda **k: EventHub(**k), "max_queue"),
        (lambda **k: MessageBus({}, {}, **k), "limit"),
        (lambda **k: Mapper(None, None, **k), "max_roots"),  # type: ignore[arg-type]
    ],
)
def test_a_removed_keyword_is_a_type_error_naming_it(build, keyword: str) -> None:
    """Error matrix: a consumer passes a removed keyword (``stream=``, ``limit=``) → ``TypeError`` at construction."""
    with pytest.raises(TypeError, match=keyword):
        build(**{keyword: 5})
