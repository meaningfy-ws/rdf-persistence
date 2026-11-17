"""The toolkit's OpenAPI components sit with the generated service models, under ``services`` (TC-54)."""

from rdf_persistence.services.components import TOOLKIT_FOLDER


def test_the_toolkit_components_file_is_found_under_services_generated_service():
    assert TOOLKIT_FOLDER.parts[-3:] == ("services", "generated", "service")
    assert (TOOLKIT_FOLDER / "openapi-components.json").is_file()
