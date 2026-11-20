"""Spec rp-testkit: the records `open_event_stream` returns are public and generated (PD-1)."""

from rdf_persistence.testkit import OpenedStream, StreamEvent

GENERATED_MODULE = "rdf_persistence.testkit.generated.rp_testkit"


def test_the_result_records_are_public_and_generated() -> None:
    assert StreamEvent(id="x").id == "x", "the field is read under its alias"
    assert StreamEvent().id is None, "an absent field is None"
    assert StreamEvent(data="").data == "", "an empty field is present and empty"
    assert OpenedStream.__module__ == GENERATED_MODULE
    assert StreamEvent.__module__ == GENERATED_MODULE
