"""Readers of captured log records, for the tests of the toolkit's logging style."""

import logging

import pytest

STEP_ATTRIBUTE = "rp.step"


def attributes(record: logging.LogRecord) -> dict[str, object]:
    """The dotted attributes a call put on `record` through `extra=`."""
    return {name: value for name, value in vars(record).items() if "." in name}


def records_of(caplog: pytest.LogCaptureFixture, step: str) -> list[logging.LogRecord]:
    """The captured records whose `rp.step` is `step`, in order."""
    return [r for r in caplog.records if attributes(r).get(STEP_ATTRIBUTE) == step]
