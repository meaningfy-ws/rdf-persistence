"""``ServiceKit`` refuses an activity template that a schema root's IRIs fall inside (activity-iri-policy PD-3c)."""

import pytest

from rdf_persistence.core.domain.exceptions import InvalidIri
from rdf_persistence.iris.services.generated.rp_iris_services import IriPolicy
from tests.toy_service import ToyService


def test_a_kit_whose_schema_root_is_minted_inside_the_activity_template_does_not_start():
    with pytest.raises(InvalidIri, match=r"IRIs of 'book' fall inside the activity_template"):
        ToyService(iri_policy=IriPolicy(activity_template="{tenant}/books/{id}"))


def test_a_kit_whose_activity_segment_no_root_uses_starts():
    kit = ToyService(iri_policy=IriPolicy(activity_template="{tenant}/activity/{id}")).kit
    assert kit.iris.is_activity(
        None, f"{kit.iris.application}/activity/{'0' * 8}-0000-4000-8000-{'0' * 12}"
    ), "the kit's Iris reads the template"
