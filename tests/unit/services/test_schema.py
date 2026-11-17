"""The imports a consumer schema can resolve (rp-generation: the schemas a consumer imports)."""

from pathlib import Path

from rdf_persistence.services.schema import MODEL_PREFIX, metamodel_importmap

TECHNICAL_MARKERS = ("technical", "rp_service", "rp_wire")


def test_a_consumer_imports_rp_core_and_no_technical_schema():
    importmap = metamodel_importmap()

    assert f"{MODEL_PREFIX}/rp_core" in importmap
    assert Path(importmap[f"{MODEL_PREFIX}/rp_core"]).with_suffix(".yaml").is_file()
    leaked = [key for key in importmap if any(marker in key for marker in TECHNICAL_MARKERS)]
    assert leaked == [], "a technical schema must not be importable by a consumer"
