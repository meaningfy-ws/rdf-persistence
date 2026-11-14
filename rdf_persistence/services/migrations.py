"""Migration files: loaded, checked, and turned into the one guarded update request (PD-4 to PD-8).

A migration is a reviewed YAML file of steps. Each step holds group graph patterns as text; the
toolkit wraps them into one request per migration and database whose every operation matches only
while the database's stamp is still ``from_version``, so a second sender changes nothing.
"""

import re
from pathlib import Path

from pydantic import ValidationError
from pyparsing import ParseBaseException
from rdflib import Literal, URIRef
from rdflib.plugins.sparql.parser import parseUpdate

from rdf_persistence.domain.exceptions import InvalidMigration, SparqlError
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.domain.sparql import (
    CODEPOINT_ESCAPE,
    SparqlTerm,
    checked_group,
    fragment,
    term,
)
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.yaml_files import SHOWN, problems_of, read_mapping, shown

# The toolkit's own predicates: a step may read them, never write them (PD-22 item 3).
_OWN_PREDICATES = (v.VERSION, v.REGISTRY_KIND, v.DATA_SCHEMA_VERSION)
_CHECKED_STAMPS = URIRef("urn:stamps")  # any graph IRI will do to check the shape of the request

# The one place a user's text meets the template: a pattern that checked_group has accepted.
_STEP = (
    "$delete $insert WHERE { GRAPH $stamps { $schema $p_stamp $from } "
    "GRAPH ?rp_graph { $where } FILTER (?rp_graph != $stamps) "
    "FILTER NOT EXISTS { GRAPH ?rp_registry { ?rp_graph $p_kind $loaded } } "
    "FILTER NOT EXISTS { GRAPH ?rp_graph { ?rp_entry $p_kind ?rp_kind } } }"  # a registry graph (PD-21)
)
_CLAUSE = "$verb { GRAPH ?rp_graph { $pattern } }"
# Every token: a step may have changed any graph, and the request cannot tell which (PD-8).
_ROTATION = (
    "DELETE { GRAPH ?rp_graph { ?rp_graph $p_version ?rp_old } } "
    "INSERT { GRAPH ?rp_graph { ?rp_graph $p_version ?rp_new } } "
    "WHERE { GRAPH $stamps { $schema $p_stamp $from } "
    "GRAPH ?rp_graph { ?rp_graph $p_version ?rp_old } FILTER (?rp_graph != $stamps) "
    "BIND (STRUUID() AS ?rp_new) }"
)
_STAMP_MOVE = (
    "DELETE { GRAPH $stamps { $schema $p_stamp $from } } "
    "INSERT { GRAPH $stamps { $schema $p_stamp $to } } "
    "WHERE { GRAPH $stamps { $schema $p_stamp $from } }"
)


def load_migration(path: Path) -> Migration:
    """The migration in the YAML file ``path``, validated and checked step by step (PD-6).

    Raises:
        InvalidMigration: The file cannot be read, is not YAML or not a migration, or a step is a
            draft, lacks a pattern, holds a pattern that does not parse alone, is too long to check,
            has a codepoint escape, a prefixed name, or (in what the parser understood) a blank node
            or one of the toolkit's own predicates in a template, a graph or service pattern or a
            reserved variable, or the request built from the migration does not parse into the
            expected operations; the file has a key twice, or a schema id or version has a codepoint
            escape; the message names the file and the step.
    """
    migration = _validated(path, read_mapping(path, "migration", InvalidMigration))
    for field in ("schema_id", "from_version", "to_version"):
        if CODEPOINT_ESCAPE.search(getattr(migration, field)):
            raise InvalidMigration(f"{path}: {field} has a codepoint escape (\\u or \\U)")
    for number, step in enumerate(migration.steps or [], start=1):
        if problem := _step_problem(step):
            raise InvalidMigration(f"{path}: step {number} ({shown(step.title)}): {problem}")
    if problem := _request_problem(migration):
        raise InvalidMigration(f"{path}: {problem}")
    return migration


_NOT_IN_NAME = re.compile(r"[^A-Za-z0-9.-]")


def migration_file_name(from_version: str, to_version: str) -> str:
    """``<from>__<to>.yaml``, each version with every character outside ``[A-Za-z0-9.-]`` as ``_`` (PD-4)."""
    return f"{_NOT_IN_NAME.sub('_', from_version)}__{_NOT_IN_NAME.sub('_', to_version)}.yaml"


# The ordered versions, and the migration from each version to the next (versions[i] to
# versions[i + 1] is migrations[i]). A plain pair: a record class would be a hand-written model.
Chain = tuple[tuple[str, ...], tuple[Migration, ...]]


def load_chain(folder: Path, schema_id: str, current: str) -> Chain:
    """The versions of one schema in order and the migration between each pair (PD-4).

    Reads every ``*.yaml`` of ``folder`` with ``load_migration``; other files, the lock among them,
    are ignored. With no file the chain is ``current`` alone.

    Raises:
        InvalidMigration: The folder is missing, a file fails ``load_migration``, a file's schema id
            is not ``schema_id`` or its name is not ``<from>__<to>.yaml`` of its fields, or the files
            do not form one line ending at ``current`` (a fork, two files reaching one version, a
            file leaving ``current``, a gap, a cycle, two files for one step); the message names the
            files.
    """
    files = _checked_files(folder, schema_id)
    by_from = _one_per(files, "from_version", "leave")
    by_to = _one_per(files, "to_version", "reach")
    if current in by_from:
        raise InvalidMigration(f"{by_from[current]} leaves {current}, the version the schema runs")
    line = _line_ending_at(files, by_to, current)
    if stranded := sorted(path.name for path in files if path not in line):
        raise InvalidMigration(
            f"{', '.join(stranded)} not on the one line of versions that ends at {current}"
            " (a gap or a cycle)"
        )
    migrations = tuple(files[path] for path in line)
    return (*(m.from_version for m in migrations), current), migrations


def _checked_files(folder: Path, schema_id: str) -> dict[Path, Migration]:
    if not folder.is_dir():
        raise InvalidMigration(f"the migrations folder {folder} does not exist")
    files = {path: load_migration(path) for path in sorted(folder.glob("*.yaml"))}
    for path, migration in files.items():
        if problem := _file_problem(path, migration, schema_id):
            raise InvalidMigration(f"{path}: {problem}")
    return files


def _line_ending_at(
    files: dict[Path, Migration], by_to: dict[str, Path], current: str
) -> list[Path]:
    """The files from the oldest step to the one reaching ``current``."""
    line: list[Path] = []
    version = current
    while version in by_to:
        line.append(by_to[version])
        version = files[by_to[version]].from_version
    return line[::-1]


def first_version(chain: Chain) -> str:
    """The version a database with no stamp is taken to be at (PD-10)."""
    versions, _ = chain
    return versions[0]


def pending_from(chain: Chain, version: str) -> tuple[Migration, ...] | None:
    """The migrations that bring ``version`` to the last one, in order; none at the last version.

    Returns None when ``version`` is not in the chain (data newer than the service, or foreign).
    """
    versions, migrations = chain
    if version not in versions:
        return None
    return migrations[versions.index(version) :]


def _file_problem(path: Path, migration: Migration, schema_id: str) -> str | None:
    if migration.schema_id != schema_id:
        return f"is for the schema {shown(migration.schema_id)}, not {shown(schema_id)}"
    expected = migration_file_name(migration.from_version, migration.to_version)
    if path.name != expected:
        steps = f"{shown(migration.from_version)} to {shown(migration.to_version)}"
        return f"holds the step {steps}, so it is named {shown(expected)}"
    return None


def _one_per(files: dict[Path, Migration], field: str, verb: str) -> dict[str, Path]:
    """The file for each value of ``field``; two files for one value are a fork or a duplicate."""
    found: dict[str, Path] = {}
    for path, migration in files.items():
        value = getattr(migration, field)
        if value in found:
            other = found[value]
            raise InvalidMigration(
                f"{other.name} and {path.name} both {verb} {shown(value)}: a fork or a duplicate step"
            )
        found[value] = path
    return found


def _validated(path: Path, data: dict) -> Migration:
    try:
        return Migration.model_validate(data)
    except ValidationError as error:
        raise InvalidMigration(f"{path}: {problems_of(error)}") from error


def migration_request(migration: Migration, stamps: URIRef) -> str:
    """The one update request that moves a database from ``from_version`` to ``to_version`` (PD-7).

    Every step as PD-5 states it, then, if there is a step, the rotation of every ``rp:version``
    token (PD-8), then the stamp move; each operation matches only the ``from_version`` stamp. A
    pattern goes in only as ``checked_group`` answers it.

    Raises:
        SparqlError: The schema id is not an IRI that SPARQL can carry, or a pattern fails its check.
    """
    return ";\n".join(_operations(migration, stamps))


def _operations(migration: Migration, stamps: URIRef) -> list[SparqlTerm]:
    """The operations of the request, one each: the steps, the rotation if any, the stamp move."""
    guard = {
        "stamps": term(stamps),
        "schema": term(URIRef(migration.schema_id)),
        "p_stamp": term(v.DATA_SCHEMA_VERSION),
        "from": term(Literal(migration.from_version)),
    }
    steps = migration.steps or []
    operations = [_step_operation(step, guard) for step in steps]
    if steps:
        operations.append(fragment(_ROTATION, p_version=term(v.VERSION), **guard))
    operations.append(fragment(_STAMP_MOVE, to=term(Literal(migration.to_version)), **guard))
    return operations


def _step_operation(step: MigrationStep, guard: dict[str, SparqlTerm]) -> SparqlTerm:
    where, delete, insert = _checked_patterns(step)
    return fragment(
        _STEP,
        delete=_clause("DELETE", delete),
        insert=_clause("INSERT", insert),
        where=where,
        p_kind=term(v.REGISTRY_KIND),
        loaded=term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
        **guard,
    )


def _clause(verb: str, pattern: SparqlTerm) -> SparqlTerm:
    if not pattern:
        return SparqlTerm("")
    return fragment(_CLAUSE, verb=SparqlTerm(verb), pattern=pattern)


def _checked_patterns(step: MigrationStep) -> tuple[SparqlTerm, SparqlTerm, SparqlTerm]:
    """The where, delete and insert patterns of ``step`` as checked terms; a blank one is empty.

    Raises:
        SparqlError: A pattern breaks a check; the message starts with the pattern's name.
    """
    return (
        _checked("where_pattern", step.where_pattern, template=False),
        _checked("delete_pattern", step.delete_pattern, template=True),
        _checked("insert_pattern", step.insert_pattern, template=True),
    )


def _checked(name: str, text: str | None, *, template: bool) -> SparqlTerm:
    if not (text and text.strip()):
        return SparqlTerm("")
    try:
        return checked_group(text, template=template, forbidden=_OWN_PREDICATES if template else ())
    except SparqlError as error:
        raise SparqlError(f"{name} {str(error)[:SHOWN]}") from error


def _step_problem(step: MigrationStep) -> str | None:
    """What is wrong with one step, or None."""
    if step.unresolved:
        return f"is a draft, unresolved: {shown(step.unresolved)}"
    if not (step.where_pattern and step.where_pattern.strip()):
        return "has no where_pattern"
    if not any((text or "").strip() for text in (step.delete_pattern, step.insert_pattern)):
        return "has neither delete_pattern nor insert_pattern"
    try:
        _checked_patterns(step)
    except SparqlError as error:
        return str(error)
    return None


def _request_problem(migration: Migration) -> str | None:
    """What is wrong with the request built from the migration, or None."""
    try:
        expected = len(_operations(migration, _CHECKED_STAMPS))
        found = len(parseUpdate(migration_request(migration, _CHECKED_STAMPS)).request)
    except SparqlError as error:
        return f"cannot build the request: {str(error)[:SHOWN]}"
    except (ParseBaseException, RecursionError) as error:
        return f"the request does not parse: {str(error)[:SHOWN]}"
    if found != expected:
        return f"the request parses into {found} operations, not the {expected} a migration makes"
    return None
