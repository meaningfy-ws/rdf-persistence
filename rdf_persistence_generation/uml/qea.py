"""The Enterprise Architect ``.qea`` reader (PD-3, PD-4): a model file in, ``UmlModel`` records out.

A ``.qea`` file is SQLite. The reader opens it read-only (A-6), checks every table and column it
needs before the first select, and copies what it needs into the generated ``Uml*`` records,
leaving every card, bound and note as the file writes it (the converter interprets them, D-11).
Everything it emits is sorted, whatever order SQLite returns rows in (A-5).

Two kinds of failure, kept apart: a *usage* error (not a SQLite file, a missing table or column,
an unknown or ambiguous package) raises ``QeaUsageError``, which the command line turns into
exit 2; a *model* problem (``no_rule``) is collected, all of them (A-9), and the reader then
returns the problems instead of a model.
"""

import re
import sqlite3
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from rdf_persistence.core.services.yaml_files import SHOWN
from rdf_persistence_generation.exceptions import QeaUsageError
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    UmlAttribute,
    UmlBoundary,
    UmlClass,
    UmlComposition,
    UmlLink,
    UmlLinkKind,
    UmlModel,
    UmlObject,
    UmlPackage,
    UmlRule,
    UmlRunValue,
    UmlStatechart,
    UmlStateFlow,
    UmlStateNode,
    UmlStateNodeKind,
    UmlTaggedValue,
)
from rdf_persistence_generation.problems import format_problem

# The tables and the columns read from them (PD-3, with `t_connector.Direction` from D-14).
TABLE_COLUMNS: dict[str, tuple[str, ...]] = {
    "t_package": ("Package_ID", "Name", "Parent_ID", "Notes", "ea_guid"),
    "t_object": (
        "Object_ID",
        "Object_Type",
        "Name",
        "Alias",
        "Note",
        "Package_ID",
        "Stereotype",
        "Abstract",
        "ea_guid",
        "Classifier",
        "RunState",
        "NType",
        "ParentID",
    ),
    "t_attribute": (
        "ID",
        "Object_ID",
        "Name",
        "Notes",
        "Type",
        "Classifier",
        "LowerBound",
        "UpperBound",
        "Pos",
        "Stereotype",
    ),
    "t_connector": (
        "Connector_ID",
        "Connector_Type",
        "SubType",
        "Stereotype",
        "Notes",
        "Direction",
        "Start_Object_ID",
        "End_Object_ID",
        "SourceRole",
        "SourceCard",
        "SourceIsAggregate",
        "DestRole",
        "DestCard",
        "DestIsAggregate",
        "PDATA1",
        "Name",
        "PDATA2",
        "PDATA3",
        "PDATA4",
        "PDATA5",
        "ea_guid",
    ),
    "t_objectproperties": ("Object_ID", "Property", "Value", "Notes"),
    "t_xref": ("Client", "Name", "Description"),
    "t_diagramobjects": ("Diagram_ID", "Object_ID"),
    "t_diagram": ("Diagram_ID", "Name", "Package_ID", "Diagram_Type"),
    "t_connectortag": ("ElementID", "Property", "VALUE", "NOTES"),
    "t_operation": ("Object_ID",),
}

CLASS_TYPE = "Class"
ENUMERATION_TYPE = "Enumeration"
BOUNDARY_TYPE = "Boundary"
OBJECT_TYPE = "Object"  # an instance of a drawn class: read as a UmlObject, never a problem
STATE_TYPE = "State"
STATE_NODE_TYPE = "StateNode"
STATE_TYPES = frozenset({STATE_TYPE, STATE_NODE_TYPE})
INITIAL_NODE_TYPE = 3  # the `NType` EA gives an Initial node
STATE_FLOW_TYPE = "StateFlow"
STATECHART_TYPE = "Statechart"
PDATA_COLUMNS = ("PDATA1", "PDATA2", "PDATA3", "PDATA4", "PDATA5")
CONVERTED_TYPES = frozenset({CLASS_TYPE, ENUMERATION_TYPE})
# Object types that are drawing furniture, never converted and never a problem.
PACKAGE_TYPE = "Package"  # the object that draws a package; it shares the package's ea_guid
IGNORED_TYPES = frozenset({PACKAGE_TYPE, "Note", "Text", BOUNDARY_TYPE})
LINK_KINDS: dict[str, UmlLinkKind] = {
    "Association": UmlLinkKind.ASSOCIATION,
    "Dependency": UmlLinkKind.DEPENDENCY,
    "Generalization": UmlLinkKind.GENERALISATION,
    "Generalisation": UmlLinkKind.GENERALISATION,
}
AGGREGATION_TYPE = "Aggregation"  # read as a UmlComposition, never a UmlLink (PD-1)
REALISATION_TYPES = frozenset({"Realisation", "Realization"})  # read into UmlObject.realised_ids
OWN_GRAPH_STEREOTYPE = "own graph"
NOT_MARKED, SHARED_MARK, COMPOSITE_MARK = 0, 1, 2  # the values of an end's ``IsAggregate`` column
ASSOCIATION_CLASS_SUB_TYPE = "class"
MEMO = "<memo>"
NO_CLASS = "0"  # what EA writes in `PDATA1` when no class backs the association
MULTIPLE_STEREOTYPES = 2
STEREOTYPES_XREF = "Stereotypes"
XREF_STEREOTYPE_NAME = re.compile(r"Name=([^;]+);")
ASSIGNMENT = "="  # splits `Key=value` at the first one, so `Op==` has the value `=`
RUN_STATE_BLOCK = re.compile(r"@VAR;(?P<body>.*?)@ENDVAR;", re.DOTALL)
PATH_SEPARATOR = "/"
SQLITE_HEADER = b"SQLite format 3\x00"


def read_qea(
    path: Path, package: str, excluded: Sequence[str] = ()
) -> UmlModel | list[CheckProblem]:
    """Read the subtree of ``package`` (a name, or a path ``A/B``) without the ``excluded`` paths.

    Returns the model, or every ``no_rule`` problem found, sorted.

    Raises:
        QeaUsageError: The path is no file, cannot be read, is not SQLite, any ``sqlite3.Error``
            occurs (corrupt, locked, changed during the read), a table or column is missing (a
            view or trigger named like a table is no table), or the package is unknown or
            ambiguous.
    """
    connection = _open(path)
    try:
        _check_schema(connection, path)
        return _Reading(connection, package, tuple(excluded)).read()
    except sqlite3.Error as error:
        raise _cannot_read(path, error) from error
    finally:
        connection.close()


def _cannot_read(path: Path, reason: object) -> QeaUsageError:
    return QeaUsageError(f"{path} cannot be read: {str(reason)[:SHOWN]}")


def _open(path: Path) -> sqlite3.Connection:
    """Open the file read-only after checking it is there, readable and SQLite (PD-1).

    With no ``-wal`` file beside it the file is opened ``immutable``, so SQLite creates no side
    file; with one (EA has the model open) it is opened ``mode=ro``, as the side files are there.
    """
    if not path.is_file():
        raise QeaUsageError(f"{path}: no such file")
    try:
        with path.open("rb") as handle:
            header = handle.read(len(SQLITE_HEADER))
    except OSError as error:
        raise _cannot_read(path, error.strerror or error) from error
    if header != SQLITE_HEADER:
        raise QeaUsageError(f"{path} is not an Enterprise Architect .qea (SQLite) file")
    mode = "mode=ro" if Path(f"{path}-wal").exists() else "immutable=1"
    connection = None
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?{mode}", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("pragma trusted_schema=OFF")
        connection.execute("pragma query_only=ON")
        connection.execute("select name from sqlite_master").fetchall()
    except sqlite3.Error as error:
        if connection is not None:
            connection.close()
        raise _cannot_read(path, error) from error
    return connection


def _check_schema(connection: sqlite3.Connection, path: Path) -> None:
    tables = {
        row[0] for row in connection.execute("select name from sqlite_master where type = 'table'")
    }
    for table in TABLE_COLUMNS:
        if table not in tables:
            raise QeaUsageError(f"{path} has no table {table}")
    for table, wanted in TABLE_COLUMNS.items():
        present = {row[1] for row in connection.execute(f"pragma table_info({table})")}
        for column in wanted:
            if column not in present:
                raise QeaUsageError(f"{path}: table {table} has no column {column}")


def _text(value: object) -> str | None:
    """The value as the file wrote it, ``None`` when it is ``NULL`` or empty (D-11)."""
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _integer(value: object) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _no_rule(element: str, what: str) -> CheckProblem:
    return CheckProblem(
        rule=UmlRule.NO_RULE.value, element=element, message=f"{what}: no rule converts it"
    )


def _is_within(path: str, base: str) -> bool:
    """Whether ``path`` is ``base``, below it, or (``base`` being a tail of a path) below its tail."""
    return f"/{base}/" in f"/{path}/"


def _package_paths(rows: Sequence[sqlite3.Row]) -> dict[int, str]:
    names = {row["Package_ID"]: row["Name"] or "" for row in rows}
    parents = {row["Package_ID"]: row["Parent_ID"] for row in rows}

    def path_of(package_id: int) -> str:
        parts: list[str] = []
        seen: set[int] = set()
        current = package_id
        while current in names and current not in seen:
            seen.add(current)
            parts.append(names[current])
            current = parents[current]
        return PATH_SEPARATOR.join(reversed(parts))

    return {package_id: path_of(package_id) for package_id in names}


def _resolve_package(paths: Mapping[int, str], wanted: str) -> int:
    exact = [pid for pid, path in paths.items() if path == wanted]
    matches = exact or [
        pid for pid, path in paths.items() if path == wanted or path.endswith(f"/{wanted}")
    ]
    if not matches:
        raise QeaUsageError(f"no package {wanted}")
    if len(matches) > 1:
        listed = ", ".join(sorted(paths[pid] for pid in matches))
        raise QeaUsageError(f"package {wanted} is ambiguous: {listed}; name it by path")
    return matches[0]


def _of_types(rows: Iterable[sqlite3.Row], types: Iterable[str]) -> list[sqlite3.Row]:
    wanted = set(types)
    return [row for row in rows if row["Object_Type"] in wanted]


def _package_objects(
    packages: Iterable[sqlite3.Row], objects: Iterable[sqlite3.Row]
) -> dict[int, int]:
    """The object that draws each package, found by the ea_guid EA gives both: package id -> object id."""
    by_guid = {
        row["ea_guid"]: row["Object_ID"]
        for row in _of_types(objects, (PACKAGE_TYPE,))
        if row["ea_guid"]
    }
    return {
        row["Package_ID"]: by_guid[row["ea_guid"]] for row in packages if row["ea_guid"] in by_guid
    }


def _unexpected(rows: Iterable[sqlite3.Row]) -> list[sqlite3.Row]:
    """Rows whose object type is neither converted nor drawing furniture."""
    known = CONVERTED_TYPES | IGNORED_TYPES | STATE_TYPES | {OBJECT_TYPE}
    return [row for row in rows if row["Object_Type"] not in known]


def _run_values(run_state: object) -> list[UmlRunValue]:
    """The ``@VAR`` blocks of a ``RunState``, copied as written; judging them is the role rule's."""
    values = []
    for block in RUN_STATE_BLOCK.finditer(_text(run_state) or ""):
        parts = (part.partition(ASSIGNMENT) for part in block.group("body").split(";"))
        fields = {key: value for key, separator, value in parts if separator}
        values.append(
            UmlRunValue(
                variable=fields.get("Variable"),
                value=fields.get("Value"),
                operator=fields.get("Op"),
            )
        )
    return values


def _run_state_rest(run_state: object) -> str | None:
    """The text of a ``RunState`` outside its ``@VAR`` blocks, stripped; the role rule judges it (D-4)."""
    return _text(RUN_STATE_BLOCK.sub("", _text(run_state) or "").strip())


def _tag_text(value: str | None, notes: str | None) -> str | None:
    """A tagged value's text: its ``Value``, or, for a ``<memo>``, the text EA keeps in the notes."""
    return notes if value == MEMO else value


def _plain_boundaries(rows: Iterable[sqlite3.Row]) -> list[sqlite3.Row]:
    """The boundaries without a stereotype: a stereotyped one is a legend, not an aggregate."""
    return [row for row in _of_types(rows, {BOUNDARY_TYPE}) if _text(row["Stereotype"]) is None]


def _mark(value: object) -> int | str:
    """An end's ``IsAggregate`` as a number, ``NULL`` being unmarked; text that is no number as written."""
    text = _text(value)
    if text is None:
        return NOT_MARKED
    try:
        return int(text)
    except ValueError:
        return text


def _diamond_refusals(label: str, marks: tuple[int | str, int | str]) -> list[CheckProblem]:
    """The problems the two ``IsAggregate`` values of an Aggregation give, none for a composition (D-5)."""
    odd = [str(mark) for mark in marks if mark not in (NOT_MARKED, SHARED_MARK, COMPOSITE_MARK)]
    if odd:
        return [_no_rule(label, f"aggregate value {value}") for value in odd]
    if SHARED_MARK in marks:
        return [
            CheckProblem(
                rule=UmlRule.BOUNDARY_OWNED.value,
                element=label,
                message="a shared aggregation; draw a composition (strong) or a plain association",
            )
        ]
    if marks.count(COMPOSITE_MARK) != 1:
        return [_no_rule(label, "composition with no single diamond end")]
    return []


class _Reading:
    """One read of an open file: the subtree's rows, copied into records, problems collected."""

    def __init__(self, connection: sqlite3.Connection, package: str, excluded: tuple[str, ...]):
        self.connection = connection
        self.problems: list[CheckProblem] = []
        self.links: list[UmlLink] = []
        self.compositions: list[UmlComposition] = []
        self.realised: defaultdict[int, set[int]] = defaultdict(
            set
        )  # object id -> classes it realises
        package_rows = self._select("t_package")
        self.paths = _package_paths(package_rows)
        root_id = _resolve_package(self.paths, package)
        root = self.paths[root_id]
        self._check_excluded(excluded, root, package_rows)
        self.all_package_rows = {row["Package_ID"]: row for row in package_rows}
        self.package_rows = [
            row
            for row in package_rows
            if self._is_converted(self.paths[row["Package_ID"]], root, excluded)
        ]
        self.package_ids = {row["Package_ID"] for row in self.package_rows}
        self._load_objects(self._select("t_object"))

    def _check_excluded(
        self, excluded: tuple[str, ...], root: str, package_rows: Sequence[sqlite3.Row]
    ) -> None:
        """An excluded path that matches no package of the subtree is a usage error (D-17)."""
        subtree = [
            self.paths[row["Package_ID"]]
            for row in package_rows
            if self._is_converted(self.paths[row["Package_ID"]], root, ())
        ]
        root_name = root.rsplit(PATH_SEPARATOR, 1)[-1]
        for base in excluded:
            if not any(_is_within(path, base) for path in subtree):
                raise QeaUsageError(f"no package {base} under {root_name}")

    def _load_objects(self, objects: list[sqlite3.Row]) -> None:
        self.object_rows = {row["Object_ID"]: row for row in objects}
        self.object_types = {row["Object_ID"]: row["Object_Type"] for row in objects}
        self.object_names = {row["Object_ID"]: row["Name"] or "" for row in objects}
        in_subtree = [row for row in objects if row["Package_ID"] in self.package_ids]
        self.class_rows = _of_types(in_subtree, CONVERTED_TYPES)
        self.unexpected_rows = _unexpected(in_subtree)
        self.object_instance_rows = _of_types(in_subtree, (OBJECT_TYPE,))
        self.state_rows = _of_types(in_subtree, STATE_TYPES)
        self.state_ids = {row["Object_ID"] for row in self.state_rows}
        self.class_ids = {row["Object_ID"] for row in self.class_rows}
        self.boundary_rows = _plain_boundaries(in_subtree)
        self.package_objects = _package_objects(self.package_rows, objects)

    def _select(self, table: str) -> list[sqlite3.Row]:
        columns = ", ".join(TABLE_COLUMNS[table])
        return list(self.connection.execute(f"select {columns} from {table} order by rowid"))

    @staticmethod
    def _is_converted(path: str, root: str, excluded: tuple[str, ...]) -> bool:
        below_root = path == root or path.startswith(f"{root}{PATH_SEPARATOR}")
        return below_root and not any(_is_within(path, base) for base in excluded)

    def read(self) -> UmlModel | list[CheckProblem]:
        for row in self.unexpected_rows:
            self.problems.append(_no_rule(row["Name"] or "", f"{row['Object_Type']} object"))
        self._read_connectors()
        outside = self._outside_rows(self._connector_ends())
        nodes, flows, charts = _StateMachines(self).read()
        model = UmlModel(
            uml_packages=self._packages(),
            uml_outside_packages=self._outside_packages(outside),
            uml_classes=self._classes(),
            uml_outside_classes=[self._class_record(row) for row in outside],
            uml_links=self.links,
            uml_compositions=self.compositions,
            uml_tagged_values=self._tags(),
            uml_boundaries=self._boundaries(),
            uml_objects=self._objects(self.realised),
            uml_state_nodes=nodes,
            uml_state_flows=flows,
            uml_statecharts=charts,
        )
        if not self.problems:
            return model
        unique = {format_problem(problem): problem for problem in self.problems}
        return [unique[line] for line in sorted(unique)]

    def label(self, object_id: int | None) -> str:
        return self.object_names.get(object_id) or str(object_id)

    def _packages(self) -> list[UmlPackage]:
        return [self._package(row) for row in self._by_path(self.package_rows)]

    def _outside_rows(self, ends: Iterable[int]) -> list[sqlite3.Row]:
        """The classes and enumerations at the far end of a connector, not converted, once each."""
        rows = [
            self.object_rows[end] for end in set(ends) - self.class_ids if end in self.object_rows
        ]
        return sorted(_of_types(rows, CONVERTED_TYPES), key=lambda row: row["Object_ID"])

    def _outside_packages(self, outside: Iterable[sqlite3.Row]) -> list[UmlPackage]:
        """The packages of the outside classes and their ancestors that are not converted."""
        wanted: set[int] = set()
        for row in outside:
            current = row["Package_ID"]
            while current in self.all_package_rows and current not in wanted:
                wanted.add(current)
                current = self.all_package_rows[current]["Parent_ID"]
        rows = [self.all_package_rows[pid] for pid in wanted - self.package_ids]
        return [self._package(row) for row in self._by_path(rows)]

    def _by_path(self, rows: Iterable[sqlite3.Row]) -> list[sqlite3.Row]:
        return sorted(rows, key=lambda row: (self.paths[row["Package_ID"]], row["Package_ID"]))

    def _package(self, row: sqlite3.Row) -> UmlPackage:
        return UmlPackage(
            package_id=row["Package_ID"],
            name=row["Name"] or "",
            parent_id=row["Parent_ID"] or None,
            note=_text(row["Notes"]),
            object_id=self.package_objects.get(row["Package_ID"]),
        )

    def _objects(self, realised: Mapping[int, set[int]]) -> list[UmlObject]:
        rows = sorted(self.object_instance_rows, key=lambda r: (r["Name"] or "", r["Object_ID"]))
        return [
            UmlObject(
                object_id=row["Object_ID"],
                uml_name=row["Name"] or "",
                classifier_id=_integer(row["Classifier"]) or None,
                realised_ids=sorted(realised.get(row["Object_ID"], ())) or None,
                package_path=self.paths[row["Package_ID"]],
                run_values=_run_values(row["RunState"]),
                run_state_rest=_run_state_rest(row["RunState"]),
            )
            for row in rows
        ]

    def _second_stereotypes(self) -> dict[str, list[str]]:
        found: dict[str, list[str]] = {}
        for row in self._select("t_xref"):
            if row["Name"] != STEREOTYPES_XREF:
                continue
            names = XREF_STEREOTYPE_NAME.findall(row["Description"] or "")
            if len(names) >= MULTIPLE_STEREOTYPES:
                found[row["Client"]] = sorted(names)
        return found

    def _attributes(self) -> dict[int, list[UmlAttribute]]:
        rows = [row for row in self._select("t_attribute") if row["Object_ID"] in self.class_ids]
        rows.sort(key=lambda row: (row["Pos"] or 0, row["Name"] or "", row["ID"]))
        by_owner: dict[int, list[UmlAttribute]] = defaultdict(list)
        for row in rows:
            by_owner[row["Object_ID"]].append(
                UmlAttribute(
                    attribute_id=row["ID"],
                    owner_id=row["Object_ID"],
                    name=row["Name"] or "",
                    note=_text(row["Notes"]),
                    declared_type=_text(row["Type"]),
                    classifier_id=_integer(row["Classifier"]) or None,
                    lower_bound=_text(row["LowerBound"]),
                    upper_bound=_text(row["UpperBound"]),
                    position=row["Pos"],
                    uml_stereotype=_text(row["Stereotype"]),
                )
            )
        return by_owner

    def _classes(self) -> list[UmlClass]:
        attributes = self._attributes()
        second = self._second_stereotypes()
        classes = []
        for row in sorted(self.class_rows, key=lambda r: (r["Name"] or "", r["Object_ID"])):
            names = second.get(row["ea_guid"], [])
            if names:
                self.problems.append(
                    _no_rule(row["Name"] or "", f"two stereotypes ({', '.join(names)})")
                )
            classes.append(
                self._class_record(
                    row, attributes.get(row["Object_ID"], []), multiple_stereotypes=bool(names)
                )
            )
        return classes

    @staticmethod
    def _class_record(
        row: sqlite3.Row,
        attributes: list[UmlAttribute] | None = None,
        multiple_stereotypes: bool = False,
    ) -> UmlClass:
        """The record of a class row; for an outside class (D-17) no attributes."""
        return UmlClass(
            object_id=row["Object_ID"],
            name=row["Name"] or "",
            object_type=row["Object_Type"],
            uml_alias=_text(row["Alias"]),
            note=_text(row["Note"]),
            package_id=row["Package_ID"],
            uml_stereotype=_text(row["Stereotype"]),
            multiple_stereotypes=multiple_stereotypes,
            is_abstract=str(row["Abstract"]).strip() in ("1", "-1"),
            ea_guid=_text(row["ea_guid"]),
            uml_attributes=attributes or [],
        )

    def _connector_ends(self) -> set[int]:
        """The ends of every connector kept: a class away from the subtree is listed from these."""
        ends = {end for link in self.links for end in (link.source_id, link.target_id)}
        ends |= {each for c in self.compositions for each in (c.whole_id, c.part_id)}
        return ends | {target for targets in self.realised.values() for target in targets}

    def _read_connectors(self) -> None:
        """Read every connector that touches a converted class into ``links``, ``compositions`` or ``realised``."""
        for row in self._select("t_connector"):
            if row["Connector_Type"] in REALISATION_TYPES and self._realisation(row):
                continue
            if not self._is_skipped(row):
                self._read_connector(row)
        self.links.sort(key=lambda link: link.connector_id)
        self.compositions.sort(key=lambda composition: composition.composition_id)

    def _is_skipped(self, row: sqlite3.Row) -> bool:
        """Whether a connector is no business of the reader: away from the classes, a transition, furniture."""
        start, end = row["Start_Object_ID"], row["End_Object_ID"]
        if start not in self.class_ids and end not in self.class_ids:
            return True
        if row["Connector_Type"] == STATE_FLOW_TYPE and {start, end} & self.state_ids:
            return (
                True  # a transition of the converted states: `_StateMachines` reads or refuses it
            )
        # a note, text, boundary or package end: no link, no problem (D-25)
        return bool({self.object_types.get(start), self.object_types.get(end)} & IGNORED_TYPES)

    def _read_connector(self, row: sqlite3.Row) -> None:
        if row["Connector_Type"] == AGGREGATION_TYPE:
            composition = self._composition(row)
            if composition is not None:
                self.compositions.append(composition)
            return
        link = self._link(row)
        if link is not None:
            self.links.append(link)

    def _realisation(self, row: sqlite3.Row) -> bool:
        """Read a Realisation between an Object and a class (PD-11), whichever way it is drawn.

        Returns whether the connector is dealt with: the Object's realised class is recorded, or, for an
        Object that is not of the converted packages (excluded, or outside the subtree), it is skipped
        (A-20). A Realisation between anything else is left to the general rules (a class that
        realises stays a problem).
        """
        ends = (row["Start_Object_ID"], row["End_Object_ID"])
        objects = [end for end in ends if self.object_types.get(end) == OBJECT_TYPE]
        if len(objects) != 1:
            return False
        (obj,) = objects
        target = ends[0] if ends[1] == obj else ends[1]
        if self.object_types.get(target) not in CONVERTED_TYPES:
            return False
        if obj in {each["Object_ID"] for each in self.object_instance_rows}:
            self.realised[obj].add(target)
        return True

    def _composition(self, row: sqlite3.Row) -> UmlComposition | None:
        """The composition an Aggregation draws: the end column alone says the whole (PD-1, D-5)."""
        start, end = row["Start_Object_ID"], row["End_Object_ID"]
        marks = (_mark(row["SourceIsAggregate"]), _mark(row["DestIsAggregate"]))
        refusals = _diamond_refusals(f"{self.label(start)} -> {self.label(end)}", marks)
        if refusals:
            self.problems.extend(refusals)
            return None
        whole_is_start = marks[0] == COMPOSITE_MARK
        stereotype = _text(row["Stereotype"])
        return UmlComposition(
            composition_id=row["Connector_ID"],
            whole_id=start if whole_is_start else end,
            part_id=end if whole_is_start else start,
            own_graph=(stereotype or "").strip().lower() == OWN_GRAPH_STEREOTYPE,
            uml_stereotype=stereotype,
            role=_text(row["DestRole"] if whole_is_start else row["SourceRole"]),
        )

    def _link(self, row: sqlite3.Row) -> UmlLink | None:
        start, end = row["Start_Object_ID"], row["End_Object_ID"]
        label = self._link_label(row)
        kind = LINK_KINDS.get(row["Connector_Type"])
        if kind is None:
            self.problems.append(_no_rule(label, f"{row['Connector_Type']} connector"))
            return None
        association_class = None
        if kind is UmlLinkKind.ASSOCIATION:
            association_class = self._association_class(row)
            if association_class is not None:
                self.problems.append(_no_rule(label, "association class"))
        return UmlLink(
            connector_id=row["Connector_ID"],
            link_kind=kind,
            sub_type=_text(row["SubType"]),
            uml_stereotype=_text(row["Stereotype"]),
            note=_text(row["Notes"]),
            direction=_text(row["Direction"]),
            source_id=start,
            target_id=end,
            source_role=_text(row["SourceRole"]),
            source_card=_text(row["SourceCard"]),
            source_aggregate=row["SourceIsAggregate"],
            target_role=_text(row["DestRole"]),
            target_card=_text(row["DestCard"]),
            target_aggregate=row["DestIsAggregate"],
            association_class=association_class,
        )

    @staticmethod
    def _association_class(row: sqlite3.Row) -> str | None:
        sub_type = (_text(row["SubType"]) or "").strip().lower()
        named = _text(row["PDATA1"])
        if named is not None and named.strip() != NO_CLASS:
            return named
        return _text(row["SubType"]) if sub_type == ASSOCIATION_CLASS_SUB_TYPE else None

    def _link_label(self, row: sqlite3.Row) -> str:
        role = _text(row["DestRole"]) or _text(row["SourceRole"])
        source = self.label(row["Start_Object_ID"])
        target = self.label(row["End_Object_ID"])
        return f"{source}.{role} -> {target}" if role else f"{source} -> {target}"

    def _boundaries(self) -> list[UmlBoundary]:
        """The boundaries of the converted packages, by name and package only (PD-7, PD-18).

        A boundary is an annotation: no membership and no geometry is read. It is kept when a diagram
        shows it, with the first such diagram.
        """
        diagrams: dict[int, int] = {}
        for row in self._select("t_diagramobjects"):
            diagrams[row["Object_ID"]] = min(
                diagrams.get(row["Object_ID"], row["Diagram_ID"]), row["Diagram_ID"]
            )
        return [
            UmlBoundary(
                object_id=row["Object_ID"],
                name=row["Name"] or "",
                diagram_id=diagrams[row["Object_ID"]],
                package_id=row["Package_ID"],
            )
            for row in sorted(self.boundary_rows, key=lambda each: each["Object_ID"])
            if row["Object_ID"] in diagrams
        ]

    def _tags(self) -> list[UmlTaggedValue]:
        """The tagged values of the converted classes and of the converted packages' objects."""
        owners = self.class_ids | set(self.package_objects.values())
        tags = [
            UmlTaggedValue(
                owner_id=row["Object_ID"],
                name=row["Property"] or "",
                tag_value=_tag_text(row["Value"], row["Notes"]),
            )
            for row in self._select("t_objectproperties")
            if row["Object_ID"] in owners
        ]
        return sorted(tags, key=lambda tag: (tag.owner_id, tag.name))


class _StateMachines:
    """States, StateFlows and Statechart diagrams of the converted packages (PD-1, PD-2).

    The reader copies what the file holds and refuses, as ``no_rule``, every construct the probe did
    not see (DEC-6): a substate, a state with operations, a StateFlow with a name, PDATA, a
    stereotype or a trigger, and a StateFlow with one end outside the converted state nodes. It does
    not judge the kind of a state node: the workflow rule does (PD-5).
    """

    def __init__(self, reading: _Reading) -> None:
        self.reading = reading

    def read(self) -> tuple[list[UmlStateNode], list[UmlStateFlow], list[UmlStatechart]]:
        return self._nodes(), self._flows(), self._charts()

    def _nodes(self) -> list[UmlStateNode]:
        select = self.reading._select
        with_operations = {row["Object_ID"] for row in select("t_operation")}
        nodes = []
        for row in sorted(self.reading.state_rows, key=lambda r: (r["Name"] or "", r["Object_ID"])):
            name = row["Name"] or ""
            if _integer(row["ParentID"]):
                self.reading.problems.append(_no_rule(name, "substate"))
            if row["Object_ID"] in with_operations:
                self.reading.problems.append(
                    _no_rule(name, "State with entry, do or exit behaviour")
                )
            nodes.append(self._node(row))
        return nodes

    @staticmethod
    def _node(row: sqlite3.Row) -> UmlStateNode:
        is_node = row["Object_Type"] == STATE_NODE_TYPE
        node_type = _integer(row["NType"]) if is_node else None
        kind = None
        if not is_node:
            kind = UmlStateNodeKind.STATE
        elif node_type == INITIAL_NODE_TYPE:
            kind = UmlStateNodeKind.INITIAL
        return UmlStateNode(
            object_id=row["Object_ID"],
            uml_name=row["Name"] or "",
            node_kind=kind,
            node_type=node_type,
            note=_text(row["Note"]),
        )

    def _flows(self) -> list[UmlStateFlow]:
        reading = self.reading
        tags = self._tags()
        triggered = {row["Client"] for row in reading._select("t_xref")}
        flows = []
        for row in reading._select("t_connector"):
            start, end = row["Start_Object_ID"], row["End_Object_ID"]
            if row["Connector_Type"] != STATE_FLOW_TYPE or not {start, end} & reading.state_ids:
                continue
            label = f"{reading.label(start)} -> {reading.label(end)}"
            if not {start, end} <= reading.state_ids:
                reading.problems.append(
                    _no_rule(label, "StateFlow crossing the converted packages")
                )
                continue
            for what in self._unknown(row, triggered):
                reading.problems.append(_no_rule(label, f"StateFlow with {what}"))
            flows.append(
                UmlStateFlow(
                    connector_id=row["Connector_ID"],
                    source_id=start,
                    target_id=end,
                    uml_tagged_values=tags.get(row["Connector_ID"], []),
                )
            )
        return sorted(flows, key=lambda flow: flow.connector_id)

    @staticmethod
    def _unknown(row: sqlite3.Row, triggered: set[str]) -> list[str]:
        """What a StateFlow carries that the probe did not see, one phrase each."""
        found = []
        if _text(row["Name"]) is not None:
            found.append("a name")
        found += [column for column in PDATA_COLUMNS if _text(row[column]) is not None]
        if _text(row["Stereotype"]) is not None:
            found.append("a stereotype")
        if row["ea_guid"] in triggered:
            found.append("a trigger")
        return found

    def _tags(self) -> dict[int, list[UmlTaggedValue]]:
        by_connector: dict[int, list[UmlTaggedValue]] = defaultdict(list)
        for row in self.reading._select("t_connectortag"):
            by_connector[row["ElementID"]].append(
                UmlTaggedValue(
                    owner_id=row["ElementID"],
                    name=row["Property"] or "",
                    tag_value=_tag_text(row["VALUE"], row["NOTES"]),
                )
            )
        return {key: sorted(tags, key=lambda tag: tag.name) for key, tags in by_connector.items()}

    def _charts(self) -> list[UmlStatechart]:
        reading = self.reading
        placed: dict[int, set[int]] = defaultdict(set)
        for row in reading._select("t_diagramobjects"):
            if row["Object_ID"] in reading.state_ids:
                placed[row["Diagram_ID"]].add(row["Object_ID"])
        rows = [
            row
            for row in reading._select("t_diagram")
            if row["Diagram_Type"] == STATECHART_TYPE and placed[row["Diagram_ID"]]
        ]  # a workflow is a diagram that shows a converted state node, wherever it sits
        return [
            UmlStatechart(
                diagram_id=row["Diagram_ID"],
                uml_name=row["Name"] or "",
                package_path=reading.paths[row["Package_ID"]],
                node_ids=sorted(placed[row["Diagram_ID"]]),
            )
            for row in sorted(rows, key=lambda r: (r["Name"] or "", r["Diagram_ID"]))
        ]
