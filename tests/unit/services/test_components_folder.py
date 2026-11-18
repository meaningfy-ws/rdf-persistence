"""The toolkit's OpenAPI components sit with the generated service models, under ``services`` (TC-54)."""

from rdf_persistence.services.components import served_folders


def test_the_toolkit_components_file_is_found_under_services_generated_service():
    (folder,) = served_folders()
    assert folder.parts[-3:] == ("services", "generated", "service")
    assert (folder / "openapi-components.json").is_file()
