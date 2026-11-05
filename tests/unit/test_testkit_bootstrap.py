"""The wait, parse and environment helpers behind the container fixtures (PD-16)."""

import os

import pytest

from rdf_persistence.testkit.bootstrap import environment, redact_secrets, value_after, wait_until


class FakeClock:
    """A clock whose sleep advances time, so waits take no real time."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def _wait(probe, clock: FakeClock, **kwargs):
    return wait_until(
        probe, "thing", timeout=10, sleep=clock.sleep, monotonic=clock.monotonic, **kwargs
    )


def test_wait_retries_a_probe_that_fails_twice_then_returns_its_value() -> None:
    clock = FakeClock()
    answers = iter([False, "", "node-1"])
    assert _wait(lambda: next(answers), clock) == "node-1"
    assert len(clock.sleeps) == 2


def test_wait_retries_the_listed_errors_only() -> None:
    clock = FakeClock()
    calls = []

    def probe() -> bool:
        calls.append(1)
        if len(calls) < 3:
            raise ConnectionError("not yet")
        return True

    assert _wait(probe, clock, retry_on=(OSError,)) is True
    with pytest.raises(ValueError):
        _wait(lambda: (_ for _ in ()).throw(ValueError("bug")), clock, retry_on=(OSError,))


def test_wait_times_out_naming_what_it_waited_for() -> None:
    clock = FakeClock()
    with pytest.raises(TimeoutError, match="thing did not answer within 10s"):
        _wait(lambda: False, clock)


OUTPUT = "==== KEY INFORMATION ====\nKey name: rp\nKey ID: GK123\nSecret key: s3cr3t\n"


def test_value_after_reads_the_labelled_line() -> None:
    assert value_after("key id", OUTPUT) == "GK123"
    assert value_after("secret key", OUTPUT) == "s3cr3t"


def test_value_after_names_the_missing_label_but_not_the_output() -> None:
    with pytest.raises(ValueError) as error:
        value_after("bucket", OUTPUT)
    assert "bucket" in str(error.value)
    assert "s3cr3t" not in str(error.value)


def test_redact_secrets_drops_the_secret_line() -> None:
    redacted = redact_secrets(OUTPUT)
    assert "s3cr3t" not in redacted
    assert "GK123" in redacted


def test_environment_sets_variables_and_restores_every_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RP_TEST_KEPT", "before")
    monkeypatch.delenv("RP_TEST_NEW", raising=False)
    with pytest.raises(RuntimeError), environment(RP_TEST_KEPT="during", RP_TEST_NEW="x"):
        assert os.environ["RP_TEST_KEPT"] == "during"
        assert os.environ["RP_TEST_NEW"] == "x"
        raise RuntimeError("boom")
    assert os.environ["RP_TEST_KEPT"] == "before", "a changed variable was not restored"
    assert "RP_TEST_NEW" not in os.environ, "a new variable was not removed"
