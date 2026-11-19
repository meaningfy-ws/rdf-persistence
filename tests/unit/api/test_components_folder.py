"""The toolkit's OpenAPI components sit with the generated service models of each served schema (TC-54)."""

from rdf_persistence.api.services.components import served_folders


def test_the_toolkit_components_files_are_found_under_the_generated_service_models():
    iris, persistence, migrations, access, tenancy, events, collaboration, service = (
        served_folders()
    )
    assert iris.parts[-3:] == ("iris", "services", "generated"), "the iris theme's served schema"
    assert persistence.parts[-3:] == ("persistence", "services", "generated"), "persistence's"
    assert migrations.parts[-3:] == ("migrations", "services", "generated"), "migrations'"
    assert access.parts[-3:] == ("access", "services", "generated"), "access'"
    assert tenancy.parts[-3:] == ("tenancy", "services", "generated"), "tenancy's"
    assert events.parts[-3:] == ("events", "services", "generated"), "events'"
    assert collaboration.parts[-3:] == ("collaboration", "services", "generated"), "collaboration's"
    assert service.parts[-3:] == ("api", "entrypoints", "generated"), "the api theme's schema"
    folders = (iris, persistence, migrations, access, tenancy, events, collaboration, service)
    assert all((folder / "openapi-components.json").is_file() for folder in folders)
