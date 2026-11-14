"""Migration files: loaded, checked, and turned into the one guarded update request (PD-4 to PD-8).

A migration is a reviewed YAML file of steps. Each step holds group graph patterns as text; the
toolkit wraps them into one request per migration and database whose every operation matches only
while the database's stamp is still ``from_version``, so a second sender changes nothing.
"""

import re
from pathlib import Path

import yaml
from pydantic import ValidationError
from pyparsing import ParseBaseException
from rdflib import Literal, URIRef
from rdflib.plugins.sparql import prepareQuery, prepareUpdate
from rdflib.plugins.sparql.parser import parseUpdate

from rdf_persistence.domain.exceptions import InvalidMigration, SparqlError
from rdf_persistence.domain.generated.rp_core import RegistryKind
from rdf_persistence.domain.generated.service.rp_service import Migration, MigrationStep
from rdf_persistence.domain.sparql import SparqlTerm, fragment, term
from rdf_persistence.services import vocabulary as v

SHOWN = 200  # characters of a parser's message that an error carries

# The one place a user's text meets the template: a pattern that load_migration has checked.
_STEP = (
    "$delete $insert WHERE { GRAPH $stamps { $schema $p_stamp $from } "
    "GRAPH ?rp_graph { $where } FILTER (?rp_graph != $stamps) "
    "FILTER NOT EXISTS { GRAPH ?rp_registry { ?rp_graph $p_kind $loaded } } }"
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

# What a keyword search must not look inside: strings, IRIs and comments (the first that matches wins).
_OPAQUE = re.compile(
    r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\''
    r"|<[^<>\s]*>|#[^\n]*"
)
_BLANK_NODE = re.compile(r"_:|\[|\(")
_ESCAPES_GROUP = re.compile(r"(?<![\w?$:])(?:GRAPH|SERVICE)(?![\w:-])", re.IGNORECASE)
_PREFIXED = re.compile(
    r"(?<![\w?$])[A-Za-z][\w.-]*:|(?<![\w?$]):\w"
)  # the request has no PREFIX (D-4)
_RESERVED = re.compile(r"[?$](rp_\w*)")
_GRAPH_VARIABLE = "rp_graph"


def load_migration(path: Path) -> Migration:
    """The migration in the YAML file ``path``, validated and checked step by step (PD-6).

    Raises:
        InvalidMigration: The file cannot be read, is not YAML or not a migration, or a step is a
            draft, lacks a pattern, holds a pattern that does not parse alone or has a blank node,
            ``GRAPH``, ``SERVICE`` or a reserved variable, or the request built from the migration
            does not parse into the expected operations; the message names the file and the step.
    """
    migration = _validated(path, _read_mapping(path))
    for number, step in enumerate(migration.steps or [], start=1):
        if problem := _step_problem(step):
            raise InvalidMigration(f"{path}: step {number} ({step.title}): {problem}")
    if problem := _request_problem(migration):
        raise InvalidMigration(f"{path}: {problem}")
    return migration


def _read_mapping(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise InvalidMigration(f"cannot read the migration {path}: {error}") from error
    except UnicodeDecodeError as error:
        raise InvalidMigration(f"{path} is not UTF-8 text: {str(error)[:SHOWN]}") from error
    except yaml.YAMLError as error:
        raise InvalidMigration(f"{path} is not valid YAML: {str(error)[:SHOWN]}") from error
    except RecursionError as error:
        raise InvalidMigration(f"{path} is nested too deeply to read") from error
    if not isinstance(data, dict):
        raise InvalidMigration(f"{path} must hold one migration, a mapping")
    return data


def _validated(path: Path, data: dict) -> Migration:
    try:
        return Migration.model_validate(data)
    except ValidationError as error:
        problems = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {str(e['msg'])[:SHOWN]}" for e in error.errors()
        )
        raise InvalidMigration(f"{path}: {problems}") from error


def migration_request(migration: Migration, stamps: URIRef) -> str:
    """The one update request that moves a database from ``from_version`` to ``to_version`` (PD-7).

    Every step as PD-5 states it, then, if there is a step, the rotation of every ``rp:version``
    token (PD-8), then the stamp move; each operation matches only the ``from_version`` stamp. The
    patterns are the text of a migration that ``load_migration`` has checked.

    Raises:
        SparqlError: The schema id is not an IRI that SPARQL can carry.
    """
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
    return ";\n".join(operations)


def _step_operation(step: MigrationStep, guard: dict[str, SparqlTerm]) -> SparqlTerm:
    return fragment(
        _STEP,
        delete=_clause("DELETE", step.delete_pattern),
        insert=_clause("INSERT", step.insert_pattern),
        where=SparqlTerm(step.where_pattern or ""),
        p_kind=term(v.REGISTRY_KIND),
        loaded=term(v.REGISTRY_KIND_IRIS[RegistryKind.LOADED_GRAPH]),
        **guard,
    )


def _clause(verb: str, pattern: str | None) -> SparqlTerm:
    if not (pattern and pattern.strip()):
        return SparqlTerm("")
    return fragment(_CLAUSE, verb=SparqlTerm(verb), pattern=SparqlTerm(pattern))


def _step_problem(step: MigrationStep) -> str | None:
    """What is wrong with one step, or None."""
    if step.unresolved:
        return f"is a draft, unresolved: {step.unresolved}"
    if not (step.where_pattern and step.where_pattern.strip()):
        return "has no where_pattern"
    patterns = {
        "where_pattern": step.where_pattern,
        "delete_pattern": step.delete_pattern,
        "insert_pattern": step.insert_pattern,
    }
    given = {name: text for name, text in patterns.items() if text and text.strip()}
    if given.keys() == {"where_pattern"}:
        return "has neither delete_pattern nor insert_pattern"
    for name, text in given.items():
        if problem := _pattern_problem(name, text):
            return problem
    return None


def _pattern_problem(name: str, text: str) -> str | None:
    if not _parses_alone(name, text):
        return f"{name} does not parse alone as a group graph pattern"
    bare = _OPAQUE.sub(" ", text)
    if name != "where_pattern" and _BLANK_NODE.search(bare):
        return f"{name} has a blank node (_:, [ ] or a collection), which a migration cannot mint"
    if _PREFIXED.search(bare):
        return f"{name} has a prefixed name; write the full IRI in angle brackets"
    if _ESCAPES_GROUP.search(bare):
        return f"{name} contains GRAPH or SERVICE: a step works inside one graph"
    for found in _RESERVED.findall(bare):
        if found != _GRAPH_VARIABLE:
            return (
                f"{name} uses the reserved variable ?{found}; only ?{_GRAPH_VARIABLE} is open to it"
            )
    return None


def _parses_alone(name: str, text: str) -> bool:
    try:
        if name == "where_pattern":
            prepareQuery(f"ASK {{ {text} }}")
        else:
            prepareUpdate(f"INSERT {{ {text} }} WHERE {{}}")
    except Exception:  # rdflib raises a bare Exception for a name it cannot resolve
        return False
    return True


def _request_problem(migration: Migration) -> str | None:
    """What is wrong with the request built from the migration, or None."""
    expected = len(migration.steps or []) + (1 if migration.steps else 0) + 1
    try:
        found = len(parseUpdate(migration_request(migration, URIRef("urn:stamps"))).request)
    except SparqlError as error:
        return f"cannot build the request: {error}"
    except (ParseBaseException, RecursionError) as error:
        return f"the request does not parse: {str(error)[:SHOWN]}"
    if found != expected:
        return f"the request parses into {found} operations, not the {expected} a migration makes"
    return None
