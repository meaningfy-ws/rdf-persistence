"""Migration files: loaded, checked, and turned into the one guarded update request (PD-4 to PD-8).

A migration is a reviewed YAML file of steps. Each step holds group graph patterns as text; the
toolkit wraps them into one request per migration and database whose every operation matches only
while the database's stamp is still ``from_version``, so a second sender changes nothing.
"""

import re
from collections.abc import Collection, Mapping
from pathlib import Path

from linkml_runtime.utils.schemaview import SchemaView
from pydantic import ValidationError
from pyparsing import ParseBaseException
from rdflib import Graph, Literal, URIRef
from rdflib.plugins.sparql.parser import parseUpdate
from rdflib.term import Node

from rdf_persistence.domain.exceptions import InvalidMigration, SparqlError, StoredDataInvalid
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.domain.sparql import (
    CODEPOINT_ESCAPE,
    SparqlTerm,
    checked_group,
    fill,
    fragment,
    term,
)
from rdf_persistence.services import vocabulary as v
from rdf_persistence.services.store import Store
from rdf_persistence.services.yaml_files import (
    MOST_PROBLEMS,
    SHOWN,
    problems_of,
    read_mapping,
    shown,
)

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


SchemaChain = tuple[str, Chain]  # the schema id and its chain


def chain_of(view: SchemaView, folder: Path) -> SchemaChain:
    """The schema id of ``view`` and the chain of ``folder`` that ends at the schema's version (PD-24.2).

    Raises:
        InvalidMigration: The schema has no ``version``, or ``load_chain`` refuses the folder.
    """
    schema_id = str(view.schema.id)
    if not view.schema.version:
        raise InvalidMigration(
            f"the schema {schema_id} has no version: add version: to the root schema"
        )
    return schema_id, load_chain(folder, schema_id, str(view.schema.version))


def versions(chain: Chain) -> tuple[str, ...]:
    """The versions of ``chain`` in order, the oldest first."""
    return chain[0]


def first_version(chain: Chain) -> str:
    """The version a database with no stamp is taken to be at (PD-10)."""
    return versions(chain)[0]


def current_version(chain: Chain) -> str:
    """The last version of ``chain``: the one the schema runs."""
    return versions(chain)[-1]


def pending_from(chain: Chain, version: str) -> tuple[Migration, ...] | None:
    """The migrations that bring ``version`` to the last one, in order; none at the last version.

    Returns None when ``version`` is not in the chain (data newer than the service, or foreign).
    """
    ordered, migrations = chain
    if version not in ordered:
        return None
    return migrations[ordered.index(version) :]


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


def stamp_problems(graph: Graph, wanted: Mapping[str, Collection[str]]) -> str | None:
    """How a dump's stamps ``graph`` differs from one stamp per schema of ``wanted`` (schema id to the versions
    it may be at), or None: the one rule behind a restore's stamps check and ``migrate_dataset`` (PD-24.1).

    A schema with no stamp, a second stamp, a stamp of another schema or at another version, and a statement
    that is not a stamp are each a problem; the first ``MOST_PROBLEMS`` are listed.
    """
    held = sorted(graph, key=str)
    found = _stamps_by_schema(held)
    problems = [f"the stamp of {schema} is missing" for schema in wanted if schema not in found]
    problems += [d for triple in held if (d := _stamp_difference(triple, wanted))]
    problems += [
        f"<{schema}> has more than one stamp: {', '.join(texts)}"
        for schema, texts in found.items()
        if schema in wanted and len(texts) > 1
    ]
    more = len(problems) - MOST_PROBLEMS
    if not problems:
        return None
    return "; ".join(problems[:MOST_PROBLEMS]) + (f"; +{more} more" if more > 0 else "")


def _stamps_by_schema(held: list[tuple[Node, Node, Node]]) -> dict[str, list[str]]:
    """The versions, as shown, that each schema is stamped with in ``held``."""
    found: dict[str, list[str]] = {}
    for subject, predicate, value in held:
        if predicate == v.DATA_SCHEMA_VERSION:
            found.setdefault(str(subject), []).append(shown(str(value)))
    return found


def _stamp_difference(
    triple: tuple[Node, Node, Node], wanted: Mapping[str, Collection[str]]
) -> str | None:
    """How one statement of a dump's stamps graph differs from ``wanted``, or None."""
    subject, predicate, value = triple
    text, schema = shown(str(value)), shown(str(subject))
    if predicate != v.DATA_SCHEMA_VERSION or not _is_plain_literal(value):
        return f"{schema} {shown(str(predicate))} {text} is not a stamp"
    if str(subject) not in wanted:
        return f"{schema}, a schema this service does not run, is at {text}"
    accepted = wanted[str(subject)]
    if str(value) not in accepted:
        listed = ", ".join(repr(version) for version in accepted)
        return f"{schema} is at {text}, not {'one of ' if len(accepted) > 1 else ''}{listed}"
    return None


def _is_plain_literal(value: Node) -> bool:
    """A stamp is a string literal with no language tag and no datatype: the one the runner's guard matches.

    rdflib parses ``"1"`` to no datatype and ``"1"^^xsd:string`` to ``xsd:string``, and the two are unequal.
    """
    return isinstance(value, Literal) and value.language is None and value.datatype is None


SELECT_STAMPS = "SELECT ?schema ?version WHERE { GRAPH $graph { ?schema $p_stamp ?version } }"
# The first writer wins: the stamp is inserted only if the schema has none (as the IRI policy record is).
INSERT_STAMP = (
    "INSERT { GRAPH $graph { $schema $p_stamp $version } } "
    "WHERE { FILTER NOT EXISTS { GRAPH $graph { $schema $p_stamp ?any } } }"
)


async def stamps(store: Store, database: str, stamps_graph: URIRef) -> dict[str, str]:
    """The version each schema's data follows in ``database``: schema id to version.

    Raises:
        StoredDataInvalid: One schema has two stamps; the message names both versions.
    """
    text = fill(SELECT_STAMPS, graph=term(stamps_graph), p_stamp=term(v.DATA_SCHEMA_VERSION))
    found: dict[str, set[str]] = {}
    for row in await store.query(database, text):
        found.setdefault(str(row.schema), set()).add(str(row.version))  # type: ignore[union-attr]
    for schema, held in found.items():
        if len(held) > 1:
            both = " and ".join(repr(version) for version in sorted(held))
            raise StoredDataInvalid(f"{database} holds two stamps of {schema}: {both}")
    return {schema: next(iter(held)) for schema, held in found.items()}


async def stamp_if_none(
    store: Store, database: str, stamps_graph: URIRef, schema_id: str, version: str
) -> None:
    """Stamp ``database`` with ``version`` for ``schema_id`` unless it has a stamp for it: first writer wins."""
    text = fill(
        INSERT_STAMP,
        graph=term(stamps_graph),
        schema=term(URIRef(schema_id)),
        p_stamp=term(v.DATA_SCHEMA_VERSION),
        version=term(Literal(version)),
    )
    await store.update(database, text)
