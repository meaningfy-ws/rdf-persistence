"""The annotations the toolkit reads from a schema (dependent-aggregates PD-1)."""

from linkml_runtime.linkml_model.annotations import Annotation
from linkml_runtime.linkml_model.meta import ClassDefinition

from rdf_persistence.core.domain.generated.rp_core import RpAnnotation
from rdf_persistence.schema.services.schema_structure import annotation


def test_rp_dependent_on_is_an_annotation_the_toolkit_reads() -> None:
    assert RpAnnotation("rp_dependent_on") is RpAnnotation.RP_DEPENDENT_ON, (
        "the tag is one entry of the annotation enum"
    )
    cls = ClassDefinition(name="Result")
    cls.annotations["rp_dependent_on"] = Annotation(tag="rp_dependent_on", value="run")
    assert annotation(cls, RpAnnotation.RP_DEPENDENT_ON) == "run", (
        "the annotation reads as the name of the pointer slot"
    )
