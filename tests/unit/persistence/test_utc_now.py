"""The session's default clock is timezone-aware UTC and reads the current time (PD-11)."""

from datetime import UTC, datetime, timedelta

from rdf_persistence.persistence.services.session import utc_now


def test_the_default_clock_is_timezone_aware_utc() -> None:
    now = utc_now()
    assert now.tzinfo is not None, "a naive stamp would mix with aware ones in a comparison"
    assert now.utcoffset() == timedelta(0), "the default clock reads UTC, not local time"


def test_the_default_clock_reads_the_current_time() -> None:
    before = datetime.now(UTC)
    now = utc_now()
    after = datetime.now(UTC)
    assert before <= now <= after, "the stamp lies between two reads of the current time"
