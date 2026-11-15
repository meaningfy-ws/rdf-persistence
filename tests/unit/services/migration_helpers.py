"""What the migration tests share: the library schema's ids, the ISBN predicates and the builders of a chain.

Not collected as tests; ``test_migration_runner``, ``test_migrate_dataset`` and ``test_tenant_dump`` import from here.
"""

from pathlib import Path

import yaml
from rdflib import URIRef

from rdf_persistence.domain.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.services.migrations import Chain, load_chain

LIB = "https://example.org/ns/library"
RP = "https://meaningfy.ws/ns/rdf-persistence"
ISBN = URIRef("http://purl.org/ontology/bibo/isbn")
OLD_ISBN = URIRef("https://example.org/ns/library#oldIsbn")
MID_ISBN = URIRef("https://example.org/ns/library#midIsbn")


def rename(old: URIRef, new: URIRef) -> MigrationStep:
    return MigrationStep(
        title=f"rename {old}",
        where_pattern=f"?s <{old}> ?o .",
        delete_pattern=f"?s <{old}> ?o .",
        insert_pattern=f"?s <{new}> ?o .",
    )


def migration(schema: str, old: str, new: str, *steps: MigrationStep) -> Migration:
    return Migration(schema_id=schema, from_version=old, to_version=new, steps=list(steps) or None)


def chain_of(folder: Path, schema: str, *migrations: Migration, current: str) -> Chain:
    """The chain of the migration files written to ``folder``, ending at ``current``."""
    folder.mkdir(parents=True, exist_ok=True)
    for one in migrations:
        name = f"{one.from_version}__{one.to_version}.yaml"
        (folder / name).write_text(yaml.safe_dump(one.model_dump(exclude_none=True)), "utf-8")
    return load_chain(folder, schema, current)
