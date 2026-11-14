"""Migration files: loaded, checked, and turned into the one guarded update request (PD-4 to PD-8).

A migration is a reviewed YAML file of steps. Each step holds group graph patterns as text; the
toolkit wraps them into one request per migration and database whose every operation matches only
while the database's stamp is still ``from_version``, so a second sender changes nothing.
"""

import re
from collections.abc import Hashable, Iterable, Iterator
from pathlib import Path

import yaml
from pydantic import ValidationError
from pyparsing import ParseBaseException
from rdflib import RDF, BNode, Literal, URIRef, Variable
from rdflib.plugins.sparql import prepareQuery, prepareUpdate
from rdflib.plugins.sparql.parser import parseUpdate
from rdflib.plugins.sparql.parserutils import CompValue

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

# What a keyword search must not look inside: strings, IRIs and comments (the first that matches wins).
_OPAQUE = re.compile(
    r'"""(?:.|\n)*?"""|\'\'\'(?:.|\n)*?\'\'\'|"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\''
    r"|<[^<>\s]*>|#[^\n]*"
)
_PREFIXED = re.compile(
    r"(?<![\w?$])[A-Za-z][\w.-]*:|(?<![\w?$]):\w"
)  # the request has no PREFIX (D-4)
# SPARQL expands \uXXXX and \UXXXXXXXX before it reads a word, so no text scan can be trusted (PD-21).
_CODEPOINT_ESCAPE = re.compile(r"\\[uU]")
_GRAPH_VARIABLE = "rp_graph"
_RESERVED_PREFIX = "rp_"
# The parse-tree nodes of a graph pattern and of a service pattern, as rdflib names them: the
# translated algebra (Graph, Service) and the raw tree inside FILTER EXISTS (the *GraphPattern).
_GRAPH_NODES = frozenset({"Graph", "GraphGraphPattern", "Service", "ServiceGraphPattern"})


def load_migration(path: Path) -> Migration:
    """The migration in the YAML file ``path``, validated and checked step by step (PD-6).

    Raises:
        InvalidMigration: The file cannot be read, is not YAML or not a migration, or a step is a
            draft, lacks a pattern, holds a pattern that does not parse alone, is too long to check,
            has a codepoint escape, or (in what the parser understood) a blank node in a template,
            a graph or service pattern or a reserved variable, or the request built from the
            migration does not parse into the expected operations; the file has a key twice, or a
            schema id or version has a codepoint escape; the message names the file and the step.
    """
    migration = _validated(path, _read_mapping(path))
    for field in ("schema_id", "from_version", "to_version"):
        if _CODEPOINT_ESCAPE.search(getattr(migration, field)):
            raise InvalidMigration(f"{path}: {field} has a codepoint escape (\\u or \\U)")
    for number, step in enumerate(migration.steps or [], start=1):
        if problem := _step_problem(step):
            raise InvalidMigration(f"{path}: step {number} ({step.title}): {problem}")
    if problem := _request_problem(migration):
        raise InvalidMigration(f"{path}: {problem}")
    return migration


_NOT_IN_NAME = re.compile(r"[^A-Za-z0-9.-]")

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
    return chain[0][0]


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
        return f"is for the schema {migration.schema_id}, not {schema_id}"
    expected = "__".join(
        _NOT_IN_NAME.sub("_", v) for v in (migration.from_version, migration.to_version)
    )
    if path.name != f"{expected}.yaml":
        return f"holds the step {migration.from_version} to {migration.to_version}, so it is named {expected}.yaml"
    return None


def _one_per(files: dict[Path, Migration], field: str, verb: str) -> dict[str, Path]:
    """The file for each value of ``field``; two files for one value are a fork or a duplicate."""
    found: dict[str, Path] = {}
    for path, migration in files.items():
        value = getattr(migration, field)
        if value in found:
            other = found[value]
            raise InvalidMigration(
                f"{other.name} and {path.name} both {verb} {value}: a fork or a duplicate step"
            )
        found[value] = path
    return found


class _UniqueKeyLoader(yaml.SafeLoader):
    """A safe loader that refuses a mapping key given twice: a reviewer reads what runs (PD-21)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[Hashable] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue  # the parent refuses it
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found the key {key!r} twice", key_node.start_mark
                )
            seen.add(key)
        mapping: dict = super().construct_mapping(node, deep)
        return mapping


def _read_mapping(path: Path) -> dict:
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
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
    """What is wrong with one pattern, read as the parser understood it (PD-6, PD-21)."""
    if _CODEPOINT_ESCAPE.search(text):
        return f"{name} has a codepoint escape (\\u or \\U); write the character itself"
    try:
        tree = _parsed(name, text)
        problem = next(filter(None, (_node_problem(name, n) for n in _nodes(tree))), None)
    except RecursionError:  # rdflib's parser gives up at about a hundred triple patterns
        return f"{name} is too long to check; split the step into smaller steps"
    except Exception:  # rdflib raises a bare Exception for a name it cannot resolve
        return f"{name} does not parse alone as a group graph pattern"
    if problem:
        return problem
    if _PREFIXED.search(_OPAQUE.sub(" ", text)):
        return f"{name} has a prefixed name; write the full IRI in angle brackets"
    return None


def _parsed(name: str, text: str) -> object:
    """The algebra rdflib reads from the pattern alone, as a where or as a template."""
    if name == "where_pattern":
        return prepareQuery(f"ASK {{ {text} }}").algebra
    return prepareUpdate(f"INSERT {{ {text} }} WHERE {{}}").algebra


def _nodes(node: object) -> Iterator[object]:
    """``node`` and everything inside it: every nested parse node, list, tuple, set and dict value."""
    yield node
    if isinstance(node, dict):  # a CompValue is an ordered dict; the keys of a plain one are terms
        children: Iterable[object] = [*node.keys(), *node.values()]
    elif isinstance(node, list | tuple | set | frozenset):
        children = node
    else:
        return
    for child in children:
        yield from _nodes(child)


def _node_problem(name: str, node: object) -> str | None:
    # In a template rdflib moves each GRAPH block into the ``quads`` of its clause.
    if isinstance(node, CompValue) and (node.name in _GRAPH_NODES or dict.get(node, "quads")):
        return f"{name} contains GRAPH or SERVICE: a step works inside one graph"
    if (
        isinstance(node, Variable)
        and node.startswith(_RESERVED_PREFIX)
        and str(node) != _GRAPH_VARIABLE
    ):
        return f"{name} uses the reserved variable ?{node}; only ?{_GRAPH_VARIABLE} is open to it"
    # rdf:nil is what ( ) parses to: a collection is a template's blank nodes, so the empty one goes too
    if name != "where_pattern" and (isinstance(node, BNode) or node == RDF.nil):
        return f"{name} has a blank node (_:, [ ] or a collection), which a migration cannot mint"
    return None


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
