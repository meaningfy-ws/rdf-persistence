"""The imports a consumer schema can resolve (rp-generation: the schemas a consumer imports)."""

from pathlib import Path

import rdf_persistence
from rdf_persistence.schema.services.schema import MODEL_PREFIX, PACKAGE_DIR, metamodel_importmap

TECHNICAL_MARKERS = ("technical", "rp_service", "rp_api_entrypoints", "rp_wire")
# The metamodel's modules, as they stood before the schema theme moved (thematic-structure TC-34).
METAMODEL_MODULES = (
    "rp",
    "rp_access",
    "rp_annotations",
    "rp_collections",
    "rp_core",
    "rp_discussion",
    "rp_files",
    "rp_provenance",
    "rp_tenancy",
    "rp_workflow",
)


def test_the_import_map_is_the_one_from_before_the_move():  # TC-34
    package = Path(rdf_persistence.__file__).resolve().parent

    assert package == PACKAGE_DIR, "the package folder is still rdf_persistence/, not its theme"
    assert metamodel_importmap() == {
        f"rdf_persistence/model/{stem}": str(package / "model" / stem) for stem in METAMODEL_MODULES
    }


def test_a_consumer_imports_rp_core_and_no_technical_schema():
    importmap = metamodel_importmap()

    assert f"{MODEL_PREFIX}/rp_core" in importmap
    assert Path(importmap[f"{MODEL_PREFIX}/rp_core"]).with_suffix(".yaml").is_file()
    leaked = [key for key in importmap if any(marker in key for marker in TECHNICAL_MARKERS)]
    assert leaked == [], "a technical schema must not be importable by a consumer"
