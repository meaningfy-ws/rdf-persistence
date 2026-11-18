"""The filter of an activity's parts by what the caller may read (PD-11; TC-33, TC-34)."""

from datetime import UTC, datetime

from rdf_persistence.core.domain.generated.rp_discussion import PostComment
from rdf_persistence.core.domain.generated.rp_provenance import Activity, Generation, Invalidation
from rdf_persistence.provenance.services.visible_part import visible_part

DUNE = "https://lib.example/book/dune"
EMMA = "https://lib.example/book/emma"


ACTIVITY = "https://lib.example/activity/1"
AT = datetime(2026, 1, 1, tzinfo=UTC)


def _gen(entity: str) -> Generation:
    return Generation(activity=ACTIVITY, at_time=AT, entity=entity, entity_version=f"{entity}#1")


def _inv(entity: str) -> Invalidation:
    return Invalidation(activity=ACTIVITY, at_time=AT, entity=entity, entity_version=f"{entity}#0")


def _activity(**parts) -> Activity:
    return Activity(id="https://lib.example/activity/1", **parts)


def _except(*hidden: str):
    return lambda iri: iri not in hidden


def test_a_hidden_generation_is_dropped_and_the_other_kept():
    activity = _activity(generations=[_gen(DUNE), _gen(EMMA)])

    seen = visible_part(activity, _except(DUNE))

    assert [g.entity for g in seen.generations] == [EMMA], (
        "the hidden generation is dropped and the other kept"
    )


def test_a_hidden_invalidation_is_dropped_and_the_other_kept():
    activity = _activity(generations=[_gen(EMMA)], invalidations=[_inv(DUNE), _inv(EMMA)])

    seen = visible_part(activity, _except(DUNE))

    assert [i.entity for i in seen.invalidations] == [EMMA], (
        "the hidden invalidation is dropped and the other kept"
    )


def test_an_activity_with_every_part_hidden_is_not_sent():
    activity = _activity(generations=[_gen(DUNE)], invalidations=[_inv(DUNE)])

    assert visible_part(activity, _except(DUNE)) is None, (
        "an activity with every part hidden is not sent"
    )


def test_an_activity_with_no_parts_is_not_sent():
    assert visible_part(_activity(), lambda _: True) is None, (
        "an activity with no parts is not sent"
    )


def test_a_hidden_used_resource_hides_the_activity():
    comment = PostComment(
        id="https://lib.example/activity/2", used_resource=DUNE, generations=[_gen(EMMA)]
    )

    assert visible_part(comment, _except(DUNE)) is None, (
        "the activity whose used resource is hidden is not sent"
    )


def test_a_readable_used_resource_keeps_the_activity():
    comment = PostComment(
        id="https://lib.example/activity/2", used_resource=DUNE, generations=[_gen(EMMA)]
    )

    assert visible_part(comment, lambda _: True) == comment, "the readable activity is kept"


def test_the_input_is_left_unchanged():
    activity = _activity(generations=[_gen(DUNE), _gen(EMMA)], invalidations=[_inv(DUNE)])
    before = activity.model_copy(deep=True)

    visible_part(activity, _except(DUNE))

    assert activity == before, "the input activity is left unchanged"
