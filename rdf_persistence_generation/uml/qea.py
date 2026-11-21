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

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    UmlAttribute,
    UmlBoundary,
    UmlClass,
    UmlLink,
    UmlLinkKind,
    UmlModel,
    UmlObject,
    UmlPackage,
    UmlRule,
    UmlRunValue,
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
    ),
    "t_objectproperties": ("Object_ID", "Property", "Value", "Notes"),
    "t_xref": ("Client", "Name", "Description"),
    "t_diagramobjects": (
        "Diagram_ID",
        "Object_ID",
        "RectTop",
        "RectLeft",
        "RectRight",
        "RectBottom",
    ),
}

CLASS_TYPE = "Class"
ENUMERATION_TYPE = "Enumeration"
BOUNDARY_TYPE = "Boundary"
OBJECT_TYPE = "Object"  # an instance of a drawn class: read as a UmlObject, never a problem
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
ASSOCIATION_CLASS_SUB_TYPE = "class"
MEMO = "<memo>"
NO_CLASS = "0"  # what EA writes in `PDATA1` when no class backs the association
MULTIPLE_STEREOTYPES = 2
STEREOTYPES_XREF = "Stereotypes"
XREF_STEREOTYPE_NAME = re.compile(r"Name=([^;]+);")
ASSIGNMENT = "="  # splits `Key=value` at the first one, so `Op==` has the value `=`
RUN_STATE_BLOCK = re.compile(r"@VAR;(?P<body>.*?)@ENDVAR;", re.DOTALL)
PATH_SEPARATOR = "/"


class QeaUsageError(Exception):
    """The file or the ``--package`` cannot be used (exit 2); ``message`` is the matrix text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def read_qea(
    path: Path, package: str, excluded: Sequence[str] = ()
) -> UmlModel | list[CheckProblem]:
    """Read the subtree of ``package`` (a name, or a path ``A/B``) without the ``excluded`` paths.

    Returns the model, or every ``no_rule`` problem found, sorted; raises ``QeaUsageError``.
    """
    connection = _open(path)
    try:
        _check_schema(connection, path)
        return _Reading(connection, package, tuple(excluded)).read()
    finally:
        connection.close()


def _open(path: Path) -> sqlite3.Connection:
    not_sqlite = QeaUsageError(f"{path} is not an Enterprise Architect .qea (SQLite) file")
    connection = None
    try:
        connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("select name from sqlite_master").fetchall()
    except sqlite3.DatabaseError as error:
        if connection is not None:
            connection.close()
        raise not_sqlite from error
    return connection


def _check_schema(connection: sqlite3.Connection, path: Path) -> None:
    tables = {row[0] for row in connection.execute("select name from sqlite_master")}
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
    known = CONVERTED_TYPES | IGNORED_TYPES | {OBJECT_TYPE}
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


def _plain_boundaries(rows: Iterable[sqlite3.Row]) -> list[sqlite3.Row]:
    """The boundaries without a stereotype: a stereotyped one is a legend, not an aggregate."""
    return [row for row in _of_types(rows, {BOUNDARY_TYPE}) if _text(row["Stereotype"]) is None]


class _Reading:
    """One read of an open file: the subtree's rows, copied into records, problems collected."""

    def __init__(self, connection: sqlite3.Connection, package: str, excluded: tuple[str, ...]):
        self.connection = connection
        self.problems: list[CheckProblem] = []
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
        self.class_ids = {row["Object_ID"] for row in self.class_rows}
        self.boundary_rows = _plain_boundaries(objects)
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
        links = self._links()
        outside = self._outside_rows(links)
        model = UmlModel(
            uml_packages=self._packages(),
            uml_outside_packages=self._outside_packages(outside),
            uml_classes=self._classes(),
            uml_outside_classes=[self._class_record(row) for row in outside],
            uml_links=links,
            uml_tagged_values=self._tags(),
            uml_boundaries=_Boundaries(self, self._select("t_diagramobjects")).read(),
            uml_objects=self._objects(),
        )
        if not self.problems:
            return model
        unique = {format_problem(problem): problem for problem in self.problems}
        return [unique[line] for line in sorted(unique)]

    def label(self, object_id: int | None) -> str:
        return self.object_names.get(object_id) or str(object_id)

    def _packages(self) -> list[UmlPackage]:
        return [self._package(row) for row in self._by_path(self.package_rows)]

    def _outside_rows(self, links: Iterable[UmlLink]) -> list[sqlite3.Row]:
        """The classes and enumerations at the far end of a link, not converted, once each."""
        ends = {end for link in links for end in (link.source_id, link.target_id)}
        rows = [self.object_rows[end] for end in ends - self.class_ids if end in self.object_rows]
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

    def _objects(self) -> list[UmlObject]:
        rows = sorted(self.object_instance_rows, key=lambda r: (r["Name"] or "", r["Object_ID"]))
        return [
            UmlObject(
                object_id=row["Object_ID"],
                uml_name=row["Name"] or "",
                classifier_id=_integer(row["Classifier"]) or None,
                package_path=self.paths[row["Package_ID"]],
                run_values=_run_values(row["RunState"]),
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

    def _links(self) -> list[UmlLink]:
        links = []
        for row in self._select("t_connector"):
            start, end = row["Start_Object_ID"], row["End_Object_ID"]
            if start not in self.class_ids and end not in self.class_ids:
                continue
            if {self.object_types.get(start), self.object_types.get(end)} & IGNORED_TYPES:
                continue  # a note, text, boundary or package end: no link, no problem (D-25)
            link = self._link(row)
            if link is not None:
                links.append(link)
        return sorted(links, key=lambda link: link.connector_id)

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

    def _tags(self) -> list[UmlTaggedValue]:
        """The tagged values of the converted classes and of the converted packages' objects."""
        owners = self.class_ids | set(self.package_objects.values())
        tags = [
            UmlTaggedValue(
                owner_id=row["Object_ID"],
                name=row["Property"] or "",
                tag_value=row["Notes"] if row["Value"] == MEMO else row["Value"],
            )
            for row in self._select("t_objectproperties")
            if row["Object_ID"] in owners
        ]
        return sorted(tags, key=lambda tag: (tag.owner_id, tag.name))


# A rectangle as (x_min, y_min, x_max, y_max): EA writes left/right and top/bottom in either order.
Rect = tuple[int, int, int, int]
INSIDE = "inside"
STRADDLE = "straddle"
OUTSIDE = "outside"


def _relation(rect: Rect, box: Rect) -> str:
    """``inside`` (edges inclusive), ``straddle`` (shares area without lying inside) or ``outside``."""
    x_min, y_min, x_max, y_max = rect
    box_x_min, box_y_min, box_x_max, box_y_max = box
    if box_x_min <= x_min and x_max <= box_x_max and box_y_min <= y_min and y_max <= box_y_max:
        return INSIDE
    shares_x = min(x_max, box_x_max) > max(x_min, box_x_min)
    shares_y = min(y_max, box_y_max) > max(y_min, box_y_min)
    return STRADDLE if shares_x and shares_y else OUTSIDE


def _joined(numbers: Sequence[int]) -> str:
    words = [str(number) for number in numbers]
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} and {words[-1]}"


class _Boundaries:
    """Boundary membership by geometry (PD-4): the classes whose rectangle lies inside the box."""

    def __init__(self, reading: _Reading, placements: Iterable[sqlite3.Row]) -> None:
        self.reading = reading
        self.on_diagram: dict[int, dict[int, list[Rect]]] = defaultdict(lambda: defaultdict(list))
        for row in placements:
            top, left, right, bottom = (
                row["RectTop"],
                row["RectLeft"],
                row["RectRight"],
                row["RectBottom"],
            )
            if None in (top, left, right, bottom):
                continue
            rect = (min(left, right), min(top, bottom), max(left, right), max(top, bottom))
            self.on_diagram[row["Diagram_ID"]][row["Object_ID"]].append(rect)

    def read(self) -> list[UmlBoundary]:
        found: list[UmlBoundary] = []
        boundaries_of: dict[int, set[int]] = defaultdict(set)
        for row in sorted(self.reading.boundary_rows, key=lambda r: r["Object_ID"]):
            boundary = self._boundary(row)
            if boundary is None:
                continue
            found.append(boundary)
            for member in boundary.member_ids or []:
                boundaries_of[member].add(boundary.object_id)
        for class_id, boundaries in sorted(boundaries_of.items()):
            if len(boundaries) > 1:
                self.reading.problems.append(
                    _no_rule(self.reading.label(class_id), "inside two boundaries")
                )
        return found

    def _boundary(self, row: sqlite3.Row) -> UmlBoundary | None:
        boundary_id = row["Object_ID"]
        label = row["Name"] or f"boundary {boundary_id}"
        diagrams = sorted(d for d, placed in self.on_diagram.items() if boundary_id in placed)
        member_sets = {
            diagram: self._members(label, self.on_diagram[diagram][boundary_id][0], diagram)
            for diagram in diagrams
        }
        if len({frozenset(members) for members in member_sets.values()}) > 1:
            self.reading.problems.append(
                _no_rule(label, f"members differ between diagrams {_joined(diagrams)}")
            )
            return None
        members = member_sets[diagrams[0]] if diagrams else set()
        if not members:
            return None
        return UmlBoundary(
            object_id=boundary_id,
            name=row["Name"] or "",
            diagram_id=diagrams[0],
            member_ids=sorted(members),
        )

    def _members(self, label: str, box: Rect, diagram: int) -> set[int]:
        members: set[int] = set()
        for object_id, rects in self.on_diagram[diagram].items():
            if object_id not in self.reading.class_ids:
                continue
            relations = {_relation(rect, box) for rect in rects}
            element = self.reading.label(object_id)
            if STRADDLE in relations:
                self.reading.problems.append(_no_rule(element, f"straddles boundary {label}"))
            elif relations == {INSIDE, OUTSIDE}:
                self.reading.problems.append(
                    _no_rule(
                        element,
                        f"placed twice on the diagram of boundary {label}, inside and outside",
                    )
                )
            elif INSIDE in relations:
                members.add(object_id)
        return members
