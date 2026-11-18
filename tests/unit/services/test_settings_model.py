"""The generated settings (PD-6, DEC-5): every default is the value the toolkit used before, the bounds hold, and a group is never absent.

The test sits in ``tests/unit/services/``, not ``tests/unit/domain/`` as ``tasks.md`` names it: the
domain tests import nothing above the domain (``domain-tests-stay-in-the-domain``), and the settings
are generated into ``rdf_persistence.services.generated.settings``.
"""

import pytest
from pydantic import BaseModel, ValidationError

from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
from rdf_persistence.persistence.services.generated.settings.rp_persistence_settings import (
    LimitSettings,
)
from rdf_persistence.services.generated.settings.rp_settings import (
    DirectorySettings,
    EventSettings,
    JwksSettings,
    SseSettings,
    ToolkitSettings,
)

ALGORITHMS = [
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
]

# One row of PD-6's table each; the values are written here, never read from the constants they replace.
DEFAULTS = [
    ("http", "connect_timeout_seconds", 5.0),
    ("http", "read_timeout_seconds", 30.0),
    ("http", "max_attempts", 3),
    ("jwks", "ttl_seconds", 600.0),
    ("jwks", "unknown_kid_cooldown_seconds", 10.0),
    ("jwks", "allowed_algorithms", ALGORITHMS),
    ("jwks", "leeway_seconds", 30.0),
    ("directory", "page_size", 100),
    ("events", "stream", "rp-events"),
    ("events", "retention_seconds", 604800),
    ("events", "claim_idle_seconds", 30.0),
    ("events", "polling_interval_ms", 100),
    ("events", "relay_interval_seconds", 5.0),
    ("events", "publish_timeout_seconds", 10.0),
    ("events", "hub_queue_size", 1000),
    ("sse", "max_lifetime_seconds", 300.0),
    ("sse", "access_ttl_seconds", 1.0),
    ("sse", "keep_alive_seconds", 15.0),
    ("sse", "resume_window_seconds", 604800),
    ("limits", "max_messages", 100),
    ("limits", "max_roots", 500),
    ("limits", "max_document_nodes", 10000),
    ("limits", "max_manifest_bytes", 65536),
]
GROUPS = {
    "http": HttpSettings,
    "jwks": JwksSettings,
    "directory": DirectorySettings,
    "events": EventSettings,
    "sse": SseSettings,
    "limits": LimitSettings,
}


@pytest.mark.parametrize(("group", "slot", "expected"), DEFAULTS, ids=lambda v: str(v)[:40])
def test_every_default_is_the_value_the_toolkit_used_before(
    group: str, slot: str, expected: object
) -> None:
    """TC-25"""
    assert getattr(getattr(ToolkitSettings(), group), slot) == expected, f"{group}.{slot}"


def test_the_table_names_every_slot_of_every_group() -> None:
    """TC-25: a slot added without a default row fails here."""
    named = {(group, slot) for group, slot, _ in DEFAULTS}
    declared = {(group, slot) for group, cls in GROUPS.items() for slot in cls.model_fields}
    assert named == declared, f"unlisted: {declared - named}, stale: {named - declared}"


@pytest.mark.parametrize(
    "build",
    [
        lambda: HttpSettings(read_timeout_seconds=0),
        lambda: HttpSettings(connect_timeout_seconds=0),
        lambda: LimitSettings(max_roots=0),
        lambda: JwksSettings(allowed_algorithms=["HS256"]),
        lambda: JwksSettings(allowed_algorithms=["hs512"]),
        lambda: JwksSettings(allowed_algorithms=["none"]),
        lambda: JwksSettings(allowed_algorithms=["NONE"]),
        lambda: JwksSettings(allowed_algorithms=["RS256", "HS384"]),
        lambda: HttpSettings(read_timeout_seconds=None),
        lambda: LimitSettings(max_roots=None),
        lambda: ToolkitSettings(http=None),
    ],
    ids=[
        "read-0",
        "connect-0",
        "roots-0",
        "HS256",
        "hs512",
        "none",
        "NONE",
        "mixed-HS384",
        "read-None",
        "roots-None",
        "group-None",
    ],
)
def test_a_value_out_of_bounds_or_a_shared_secret_algorithm_is_refused(build) -> None:  # type: ignore[no-untyped-def]
    """TC-26"""
    with pytest.raises(ValidationError):
        build()


def test_asymmetric_algorithms_are_accepted() -> None:
    """TC-27"""
    assert JwksSettings(allowed_algorithms=["EdDSA", "PS384"]).allowed_algorithms == [
        "EdDSA",
        "PS384",
    ]


def test_an_algorithm_name_the_schema_does_not_know_is_accepted() -> None:
    """TC-59: the schema refuses only `none` and `HS*`; the verifier checks the rest at start-up (RISK-8)."""
    assert JwksSettings(allowed_algorithms=["ML-DSA-44", "RS256"]).allowed_algorithms == [
        "ML-DSA-44",
        "RS256",
    ]


def test_a_group_is_a_default_instance_and_two_settings_share_none() -> None:
    """TC-56"""
    first, second = ToolkitSettings(), ToolkitSettings()
    assert isinstance(first.http, HttpSettings), "the group is an instance, not None"
    assert first.http == HttpSettings(), "the group holds the defaults"
    for name in GROUPS:
        assert getattr(first, name) is not getattr(second, name), f"{name} is shared"


def test_every_group_of_the_toolkit_settings_is_present() -> None:
    """TC-56: the six groups, each an instance of its class."""
    settings = ToolkitSettings()
    for name, cls in GROUPS.items():
        group = getattr(settings, name)
        assert isinstance(group, cls), name
        assert isinstance(group, BaseModel), name


@pytest.mark.parametrize(
    ("leeway", "valid"), [(0, True), (300, True), (301, False)], ids=["0", "300", "301"]
)
def test_the_leeway_is_within_zero_to_three_hundred(leeway: float, valid: bool) -> None:
    """TC-57"""
    if valid:
        assert JwksSettings(leeway_seconds=leeway).leeway_seconds == leeway
    else:
        with pytest.raises(ValidationError):
            JwksSettings(leeway_seconds=leeway)


def test_the_algorithm_list_may_not_be_empty() -> None:
    """TC-57"""
    with pytest.raises(ValidationError):
        JwksSettings(allowed_algorithms=[])
