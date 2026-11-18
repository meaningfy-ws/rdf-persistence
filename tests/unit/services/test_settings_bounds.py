"""The durations of the settings model are finite and at most a year (technical-models D-55 1, D-55 2).

Without a bound, ``inf`` or ``1e309`` passed every ``*_seconds`` slot, ``timedelta`` raised
``OverflowError`` on a huge one, and an infinite JWKS cooldown stopped authentication.
"""

import pytest
from pydantic import ValidationError

from rdf_persistence.access.services.generated.settings.rp_access_settings import JwksSettings
from rdf_persistence.adapters.redis_events import RedisEventBus
from rdf_persistence.core.services.generated.rp_core_services import HttpSettings
from rdf_persistence.services.generated.settings.rp_settings import EventSettings, SseSettings

ONE_YEAR = 31_536_000.0

DURATIONS = [
    (HttpSettings, "connect_timeout_seconds"),
    (HttpSettings, "read_timeout_seconds"),
    (JwksSettings, "ttl_seconds"),
    (JwksSettings, "unknown_kid_cooldown_seconds"),
    (EventSettings, "retention_seconds"),
    (EventSettings, "claim_idle_seconds"),
    (EventSettings, "relay_interval_seconds"),
    (EventSettings, "publish_timeout_seconds"),
    (SseSettings, "max_lifetime_seconds"),
    (SseSettings, "access_ttl_seconds"),
    (SseSettings, "keep_alive_seconds"),
    (SseSettings, "resume_window_seconds"),
]


@pytest.mark.parametrize(("group", "slot"), DURATIONS)
@pytest.mark.parametrize("value", [float("inf"), float("nan"), 1e309, 1e19, ONE_YEAR + 1])
def test_a_duration_that_is_not_finite_or_over_a_year_is_refused(
    group: type, slot: str, value: float
) -> None:
    with pytest.raises(ValidationError):
        group(**{slot: value})


@pytest.mark.parametrize(("group", "slot"), DURATIONS)
def test_a_duration_of_exactly_a_year_is_accepted(group: type, slot: str) -> None:
    assert getattr(group(**{slot: ONE_YEAR}), slot) == ONE_YEAR


def test_the_event_bus_is_built_at_the_bound_and_never_reaches_overflow() -> None:
    settings = EventSettings(retention_seconds=ONE_YEAR, claim_idle_seconds=ONE_YEAR)
    RedisEventBus("redis://localhost:1", deployment="d", events=settings)


def test_an_overflow_sized_retention_is_refused_before_the_bus_sees_it() -> None:
    with pytest.raises(ValidationError):
        EventSettings(retention_seconds=1e19)


def test_a_cooldown_under_a_second_is_refused() -> None:
    with pytest.raises(ValidationError):
        JwksSettings(unknown_kid_cooldown_seconds=0.5)
    assert JwksSettings(unknown_kid_cooldown_seconds=1).unknown_kid_cooldown_seconds == 1
