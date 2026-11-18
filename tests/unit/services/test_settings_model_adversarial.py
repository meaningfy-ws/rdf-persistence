"""Adversarial tests of the generated settings model (technical-models stage 3, task 3.1, PD-6).

Attacks: PD-6's defaults table (a default that drifted, a slot added or dropped) and the rule that
no two default instances share a group or a list.
"""

import pytest

from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
from rdf_persistence.services.generated.settings.rp_settings import (
    DirectorySettings,
    EventSettings,
    JwksSettings,
    LimitSettings,
    SseSettings,
    ToolkitSettings,
)

# PD-6's table, written out here by hand: each value is the one the replaced code used.
OLD_DEFAULTS = {
    "http": {  # _http.py 5.0 / 30.0, s3.py (5, 30, 3)
        "connect_timeout_seconds": 5.0,
        "read_timeout_seconds": 30.0,
        "max_attempts": 3,
    },
    "jwks": {  # jwks.py JWKS_TTL_SECONDS, UNKNOWN_KID_COOLDOWN_SECONDS, DEFAULT_ALGORITHMS, 30.0
        "ttl_seconds": 600.0,
        "unknown_kid_cooldown_seconds": 10.0,
        "allowed_algorithms": [
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
        ],
        "leeway_seconds": 30.0,
    },
    "directory": {"page_size": 100},  # zitadel.py PAGE_SIZE
    "events": {  # RedisEventBus(stream, retention=7 days, claim_idle=30 s), POLLING_INTERVAL_MS,
        "stream": "rp-events",  # Relay(interval=5.0, publish_timeout=10.0), EventHub(max_queue=1000)
        "retention_seconds": 7 * 24 * 3600,
        "claim_idle_seconds": 30.0,
        "polling_interval_ms": 100,
        "relay_interval_seconds": 5.0,
        "publish_timeout_seconds": 10.0,
        "hub_queue_size": 1000,
    },
    "sse": {  # sse.py: 5 minutes, 1 second, 15.0, 7 days
        "max_lifetime_seconds": 300.0,
        "access_ttl_seconds": 1.0,
        "keep_alive_seconds": 15.0,
        "resume_window_seconds": 7 * 24 * 3600,
    },
    "limits": {  # messagebus limit=100, DEFAULT_MAX_ROOTS=500, MAX_NODES=10_000, 64 * 1024
        "max_messages": 100,
        "max_roots": 500,
        "max_document_nodes": 10_000,
        "max_manifest_bytes": 64 * 1024,
    },
}
GROUPS = {
    "http": HttpSettings,
    "jwks": JwksSettings,
    "directory": DirectorySettings,
    "events": EventSettings,
    "sse": SseSettings,
    "limits": LimitSettings,
}


def test_every_default_is_the_value_the_replaced_code_used() -> None:
    """Invariant: PD-6's table, held apart from the model; a drifted value or a slot added or dropped fails."""
    held = ToolkitSettings().model_dump()
    assert held == OLD_DEFAULTS, "the defaults of ToolkitSettings() differ from the old code's"


@pytest.mark.parametrize("group", GROUPS)
def test_a_group_built_alone_has_the_defaults_of_the_group_inside_the_toolkit(group: str) -> None:
    """Invariant: a constructor that defaults to ``Group()`` and the kit's ``ToolkitSettings().group`` agree."""
    alone = GROUPS[group]().model_dump()
    assert alone == getattr(ToolkitSettings(), group).model_dump(), f"{group} differs"


def test_two_default_toolkits_share_no_group_and_no_list() -> None:
    """Invariant: each ``ToolkitSettings()`` builds six new groups, and each algorithm list is its own."""
    first, second = ToolkitSettings(), ToolkitSettings()
    for group in GROUPS:
        assert getattr(first, group) is not getattr(second, group), f"{group} is shared"
    first.limits.max_roots = 7
    first.jwks.allowed_algorithms.append("PS999")
    assert second.limits.max_roots == 500, "an assignment on one toolkit reached the other"
    assert "PS999" not in second.jwks.allowed_algorithms, "a list change reached the other"
    assert ToolkitSettings().limits.max_roots == 500, "an assignment reached the next default"
    assert "PS999" not in JwksSettings().allowed_algorithms, (
        "a list change reached the class default"
    )
