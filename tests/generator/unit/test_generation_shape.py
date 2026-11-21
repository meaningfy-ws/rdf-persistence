"""The generator's own model is the shape of its generated classes (generator-package TC-14b)."""

from pathlib import Path

from rdf_persistence.testkit.model_shape import model_shape_diff
from rdf_persistence.testkit.shape_snapshot import class_shapes
from rdf_persistence_generation.config import TOOLKIT_ROOTS
from tests.metamodel import METAMODEL_PACKAGE, generated_models

ROOT = Path(__file__).parents[3]
GENERATION = ROOT / "rdf_persistence_generation" / "model" / "rp_generation.yaml"
GENERATION_PACKAGE = "rdf_persistence_generation.generated"


def test_generated_classes_match_the_induced_slots() -> None:
    """TC-14b: ``rp_generation.yaml`` read with the generator's roots induces what the code has."""
    models = generated_models(GENERATION_PACKAGE) + generated_models(METAMODEL_PACKAGE)
    shapes = class_shapes([GENERATION], roots=TOOLKIT_ROOTS)
    own = {m.__name__ for m in generated_models(GENERATION_PACKAGE)}
    assert own, "the scan found no generated class"
    assert own <= {s.class_name for s in shapes}, "every generated class has a shape"
    assert model_shape_diff(shapes, models) == [], "generated code differs from the current schema"
