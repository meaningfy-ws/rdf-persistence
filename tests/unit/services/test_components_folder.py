"""The toolkit's OpenAPI components sit with the generated service models of each served schema (TC-54)."""

from rdf_persistence.services.components import served_folders


def test_the_toolkit_components_files_are_found_under_the_generated_service_models():
    iris, service = served_folders()
    assert iris.parts[-3:] == ("iris", "services", "generated"), "the iris theme's served schema"
    assert service.parts[-3:] == ("services", "generated", "service"), "the service schema"
    assert all((folder / "openapi-components.json").is_file() for folder in (iris, service))
