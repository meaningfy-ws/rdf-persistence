"""The imports a consumer schema can resolve (rp-generation: the schemas a consumer imports)."""

from pathlib import Path

import rdf_persistence
from rdf_persistence.schema.services.schema import MODEL_PREFIX, PACKAGE_DIR, metamodel_importmap

# The metamodel's modules, as they stood before the schema theme moved (thematic-structure TC-34).
METAMODEL_MODULES = (
    "rp",
    "rp_access",
    "rp_annotations",
    "rp_collaboration",  # the new root of the collaboration theme (domain-model-per-theme DEC-5)
    "rp_collections",
    "rp_core",
    "rp_discussion",
    "rp_files",
    "rp_provenance",
    "rp_tenancy",
    "rp_workflow",
)


def test_the_import_map_keeps_every_metamodel_key_from_before_the_move():  # TC-34, consumer-write-rules TC-1
    package = Path(rdf_persistence.__file__).resolve().parent
    importmap = metamodel_importmap()
    expected = {
        f"rdf_persistence/model/{stem}": str(package / "model" / stem) for stem in METAMODEL_MODULES
    }

    assert package == PACKAGE_DIR, "the package folder is still rdf_persistence/, not its theme"
    assert {key: importmap.get(key) for key in expected} == expected, (
        "an existing key or value changed"
    )


def test_the_import_map_holds_the_metamodel_and_the_technical_modules_only():  # TC-1
    package = PACKAGE_DIR
    model = package / "model"
    expected = {f"rdf_persistence/model/{path.stem}" for path in model.glob("*.yaml")} | {
        f"rdf_persistence/model/{path.relative_to(model).with_suffix('').as_posix()}"
        for path in model.glob("technical/**/*.yaml")
    }

    assert set(metamodel_importmap()) == expected, (
        "only model/*.yaml and model/technical/** are mapped"
    )
    assert not [
        key for key in metamodel_importmap() if key.startswith(f"{MODEL_PREFIX}/migrations/")
    ], "model/migrations stays unmapped"


def test_a_consumer_imports_rp_core_and_a_technical_schema():  # TC-1
    importmap = metamodel_importmap()
    technical = f"{MODEL_PREFIX}/technical/api/rp_api_entrypoints"

    assert f"{MODEL_PREFIX}/rp_core" in importmap
    assert Path(importmap[f"{MODEL_PREFIX}/rp_core"]).with_suffix(".yaml").is_file()
    assert technical in importmap, "a technical module is importable by its path under model/"
    assert importmap[technical] == str(PACKAGE_DIR / "model/technical/api/rp_api_entrypoints")
    assert Path(importmap[technical]).with_suffix(".yaml").is_file(), (
        "the key resolves to the existing file"
    )
