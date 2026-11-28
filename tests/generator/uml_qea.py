"""Build a small Enterprise Architect ``.qea`` file for tests (PD-24).

A helper, not a test module. No binary is checked in: a test builds the file in ``tmp_path``
with the stdlib ``sqlite3``. The eleven tables are the ones the reader reads (PD-3), with
exactly the columns it reads; ``EA_COLUMNS`` lists the real columns of each, so a unit test can
assert that the DDL here invents none.
"""

import sqlite3
from collections.abc import Iterable, Mapping
from pathlib import Path

# The column names of the eleven tables, taken from EA's own schema (``pragma table_info`` on an
# EA file) on 2026-11-20. They are EA's schema, not model data.
EA_COLUMNS: dict[str, tuple[str, ...]] = {
    "t_package": (
        "Package_ID",
        "Name",
        "Parent_ID",
        "CreatedDate",
        "ModifiedDate",
        "Notes",
        "ea_guid",
        "XMLPath",
        "IsControlled",
        "LastLoadDate",
        "LastSaveDate",
        "Version",
        "Protected",
        "PkgOwner",
        "UMLVersion",
        "UseDTD",
        "LogXML",
        "CodePath",
        "Namespace",
        "TPos",
        "PackageFlags",
        "BatchSave",
        "BatchLoad",
    ),
    "t_object": (
        "Object_ID",
        "Object_Type",
        "Diagram_ID",
        "Name",
        "Alias",
        "Author",
        "Version",
        "Note",
        "Package_ID",
        "Stereotype",
        "NType",
        "Complexity",
        "Effort",
        "Style",
        "Backcolor",
        "BorderStyle",
        "BorderWidth",
        "Fontcolor",
        "Bordercolor",
        "CreatedDate",
        "ModifiedDate",
        "Status",
        "Abstract",
        "Tagged",
        "PDATA1",
        "PDATA2",
        "PDATA3",
        "PDATA4",
        "PDATA5",
        "Concurrency",
        "Visibility",
        "Persistence",
        "Cardinality",
        "GenType",
        "GenFile",
        "Header1",
        "Header2",
        "Phase",
        "Scope",
        "GenOption",
        "GenLinks",
        "Classifier",
        "ea_guid",
        "ParentID",
        "RunState",
        "Classifier_guid",
        "TPos",
        "IsRoot",
        "IsLeaf",
        "IsSpec",
        "IsActive",
        "StateFlags",
        "PackageFlags",
        "Multiplicity",
        "StyleEx",
        "ActionFlags",
        "EventFlags",
    ),
    "t_attribute": (
        "Object_ID",
        "Name",
        "Scope",
        "Stereotype",
        "Containment",
        "IsStatic",
        "IsCollection",
        "IsOrdered",
        "AllowDuplicates",
        "LowerBound",
        "UpperBound",
        "Container",
        "Notes",
        "Derived",
        "ID",
        "Pos",
        "GenOption",
        "Length",
        "Precision",
        "Scale",
        "Const",
        "Style",
        "Classifier",
        "Default",
        "Type",
        "ea_guid",
        "StyleEx",
    ),
    "t_connector": (
        "Connector_ID",
        "Name",
        "Direction",
        "Notes",
        "Connector_Type",
        "SubType",
        "SourceCard",
        "SourceAccess",
        "SourceElement",
        "DestCard",
        "DestAccess",
        "DestElement",
        "SourceRole",
        "SourceRoleType",
        "SourceRoleNote",
        "SourceContainment",
        "SourceIsAggregate",
        "SourceIsOrdered",
        "SourceQualifier",
        "DestRole",
        "DestRoleType",
        "DestRoleNote",
        "DestContainment",
        "DestIsAggregate",
        "DestIsOrdered",
        "DestQualifier",
        "Start_Object_ID",
        "End_Object_ID",
        "Top_Start_Label",
        "Top_Mid_Label",
        "Top_End_Label",
        "Btm_Start_Label",
        "Btm_Mid_Label",
        "Btm_End_Label",
        "Start_Edge",
        "End_Edge",
        "PtStartX",
        "PtStartY",
        "PtEndX",
        "PtEndY",
        "SeqNo",
        "HeadStyle",
        "LineStyle",
        "RouteStyle",
        "IsBold",
        "LineColor",
        "Stereotype",
        "VirtualInheritance",
        "LinkAccess",
        "PDATA1",
        "PDATA2",
        "PDATA3",
        "PDATA4",
        "PDATA5",
        "DiagramID",
        "ea_guid",
        "SourceConstraint",
        "DestConstraint",
        "SourceIsNavigable",
        "DestIsNavigable",
        "IsRoot",
        "IsLeaf",
        "IsSpec",
        "SourceChangeable",
        "DestChangeable",
        "SourceTS",
        "DestTS",
        "StateFlags",
        "ActionFlags",
        "IsSignal",
        "IsStimulus",
        "DispatchAction",
        "Target2",
        "StyleEx",
        "SourceStereotype",
        "DestStereotype",
        "SourceStyle",
        "DestStyle",
        "EventFlags",
    ),
    "t_objectproperties": ("PropertyID", "Object_ID", "Property", "Value", "Notes", "ea_guid"),
    "t_xref": (
        "XrefID",
        "Name",
        "Type",
        "Visibility",
        "Namespace",
        "Requirement",
        "Constraint",
        "Behavior",
        "Partition",
        "Description",
        "Client",
        "Supplier",
        "Link",
    ),
    "t_diagramobjects": (
        "Diagram_ID",
        "Object_ID",
        "RectTop",
        "RectLeft",
        "RectRight",
        "RectBottom",
        "Sequence",
        "ObjectStyle",
        "Instance_ID",
    ),
    "t_diagramlinks": (
        "DiagramID",
        "ConnectorID",
        "Geometry",
        "Style",
        "Hidden",
        "Path",
        "Instance_ID",
    ),
    "t_diagram": (
        "Diagram_ID",
        "Package_ID",
        "ParentID",
        "Diagram_Type",
        "Name",
        "Version",
        "Author",
        "ShowDetails",
        "Notes",
        "Stereotype",
        "AttPub",
        "AttPri",
        "AttPro",
        "Orientation",
        "cx",
        "cy",
        "Scale",
        "CreatedDate",
        "ModifiedDate",
        "HTMLPath",
        "ShowForeign",
        "ShowBorder",
        "ShowPackageContents",
        "PDATA",
        "Locked",
        "ea_guid",
        "TPos",
        "Swimlanes",
        "StyleEx",
    ),
    "t_connectortag": ("PropertyID", "ElementID", "Property", "VALUE", "NOTES", "ea_guid"),
    "t_operation": (
        "OperationID",
        "Object_ID",
        "Name",
        "Scope",
        "Type",
        "ReturnArray",
        "Stereotype",
        "IsStatic",
        "IsAbstract",
        "IsConst",
        "IsSynchronized",
        "IsPure",
        "IsReturnArray",
        "IsQuery",
        "Pos",
        "Notes",
        "Behaviour",
        "Classifier",
        "Concurrency",
        "Style",
        "StyleEx",
        "ea_guid",
    ),
}

# The columns the reader reads (PD-3), no more.
DDL: dict[str, str] = {
    "t_package": (
        "CREATE TABLE t_package (Package_ID INTEGER PRIMARY KEY, Name TEXT, Parent_ID INTEGER,"
        " Notes TEXT, ea_guid TEXT)"
    ),
    "t_object": (
        "CREATE TABLE t_object (Object_ID INTEGER PRIMARY KEY, Object_Type TEXT, Name TEXT,"
        " Alias TEXT, Note TEXT, Package_ID INTEGER, Stereotype TEXT, Abstract TEXT,"
        " ea_guid TEXT, Classifier INTEGER, RunState TEXT, NType INTEGER, ParentID INTEGER)"
    ),
    "t_attribute": (
        "CREATE TABLE t_attribute (ID INTEGER PRIMARY KEY, Object_ID INTEGER, Name TEXT,"
        " Notes TEXT, Type TEXT, Classifier TEXT, LowerBound TEXT, UpperBound TEXT,"
        " Pos INTEGER, Stereotype TEXT)"
    ),
    "t_connector": (
        "CREATE TABLE t_connector (Connector_ID INTEGER PRIMARY KEY, Connector_Type TEXT,"
        " SubType TEXT, Stereotype TEXT, Notes TEXT, Direction TEXT, Start_Object_ID INTEGER,"
        " End_Object_ID INTEGER, SourceRole TEXT, SourceCard TEXT, SourceIsAggregate INTEGER,"
        " DestRole TEXT, DestCard TEXT, DestIsAggregate INTEGER, PDATA1 TEXT, Name TEXT,"
        " PDATA2 TEXT, PDATA3 TEXT, PDATA4 TEXT, PDATA5 TEXT, ea_guid TEXT)"
    ),
    "t_objectproperties": (
        "CREATE TABLE t_objectproperties (Object_ID INTEGER, Property TEXT, Value TEXT, Notes TEXT)"
    ),
    "t_xref": "CREATE TABLE t_xref (Client TEXT, Name TEXT, Description TEXT)",
    "t_diagramobjects": (
        "CREATE TABLE t_diagramobjects (Diagram_ID INTEGER, Object_ID INTEGER, RectTop INTEGER,"
        " RectLeft INTEGER, RectRight INTEGER, RectBottom INTEGER)"
    ),
    "t_diagramlinks": (
        "CREATE TABLE t_diagramlinks (DiagramID INTEGER, ConnectorID INTEGER, Hidden INTEGER)"
    ),
    "t_diagram": (
        "CREATE TABLE t_diagram (Diagram_ID INTEGER PRIMARY KEY, Name TEXT, Package_ID INTEGER,"
        " Diagram_Type TEXT)"
    ),
    "t_connectortag": (
        "CREATE TABLE t_connectortag (ElementID INTEGER, Property TEXT, VALUE TEXT, NOTES TEXT)"
    ),
    "t_operation": "CREATE TABLE t_operation (Object_ID INTEGER, Name TEXT)",
}

BOUNDARY_TYPE = "Boundary"
GENERALISATION_TYPE = "Generalization"
ASSOCIATION_TYPE = "Association"
DEPENDENCY_TYPE = "Dependency"
AGGREGATION_TYPE = "Aggregation"
REALISATION_TYPE = "Realisation"
STATE_FLOW_TYPE = "StateFlow"
STATECHART_TYPE = "Statechart"
DIRECTED = "Source -> Destination"


class QeaBuilder:
    """Write a ``.qea`` file; every method returns the id of the row it wrote."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._db = sqlite3.connect(path)
        for statement in DDL.values():
            self._db.execute(statement)

    def _insert(self, table: str, **values: object) -> int:
        names = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        cursor = self._db.execute(
            f"INSERT INTO {table} ({names}) VALUES ({marks})", tuple(values.values())
        )
        return cursor.lastrowid or 0

    def package(self, name: str, parent: int = 0, note: str | None = None) -> int:
        return self._insert(
            "t_package", Name=name, Parent_ID=parent, Notes=note, ea_guid=f"{{PKG-{name}}}"
        )

    def package_element(self, package: int) -> int:
        """The object EA draws a package as: in its parent package, with the package's ea_guid."""
        name, parent, guid = self._db.execute(
            "SELECT Name, Parent_ID, ea_guid FROM t_package WHERE Package_ID = ?", (package,)
        ).fetchone()
        return self._insert(
            "t_object", Object_Type="Package", Name=name, Package_ID=parent, ea_guid=guid
        )

    def cls(
        self,
        package: int,
        name: str,
        stereotype: str | None = None,
        object_type: str = "Class",
        abstract: bool = False,
        note: str | None = None,
    ) -> int:
        object_id = self._insert(
            "t_object",
            Object_Type=object_type,
            Name=name,
            Note=note,
            Package_ID=package,
            Stereotype=stereotype,
            Abstract="1" if abstract else "0",
        )
        self._db.execute(
            "UPDATE t_object SET ea_guid = ? WHERE Object_ID = ?",
            (f"{{GUID-{object_id}}}", object_id),
        )
        return object_id

    def object_(
        self, package: int, name: str, classifier: int | None, run_state: str | None = None
    ) -> int:
        """An ``Object`` (an instance of a drawn class): its classifier's id and its ``RunState``."""
        object_id = self._insert(
            "t_object",
            Object_Type="Object",
            Name=name,
            Package_ID=package,
            Classifier=classifier,
            RunState=run_state,
        )
        self._db.execute(
            "UPDATE t_object SET ea_guid = ? WHERE Object_ID = ?",
            (f"{{GUID-{object_id}}}", object_id),
        )
        return object_id

    def state(
        self,
        package: int,
        name: str,
        ntype: int | None = None,
        parent: int = 0,
        note: str | None = None,
    ) -> int:
        """A ``State`` row, or with an ``ntype`` a ``StateNode`` (3 is the Initial node)."""
        object_id = self._insert(
            "t_object",
            Object_Type="State" if ntype is None else "StateNode",
            Name=name,
            Note=note,
            Package_ID=package,
            NType=ntype or 0,
            ParentID=parent,
        )
        self._db.execute(
            "UPDATE t_object SET ea_guid = ? WHERE Object_ID = ?",
            (f"{{GUID-{object_id}}}", object_id),
        )
        return object_id

    def operation(self, owner: int, name: str) -> int:
        """An operation row of ``owner``, where EA keeps a state's entry, do and exit behaviour."""
        return self._insert("t_operation", Object_ID=owner, Name=name)

    def state_flow(
        self,
        source: int,
        destination: int,
        tags: Mapping[str, str] | None = None,
        memo_tags: Mapping[str, str] | None = None,
        name: str | None = None,
        stereotype: str | None = None,
        pdata: Mapping[int, str] | None = None,
        trigger: bool = False,
    ) -> int:
        """A ``StateFlow`` with its tags in ``t_connectortag``; a ``memo_tags`` text goes to NOTES.

        ``pdata`` maps 1 to 5 to a ``PDATA`` text; ``trigger`` adds the ``t_xref`` row EA keeps one in.
        """
        connector = self._insert(
            "t_connector",
            Connector_Type=STATE_FLOW_TYPE,
            Direction=DIRECTED,
            Name=name,
            Stereotype=stereotype,
            Start_Object_ID=source,
            End_Object_ID=destination,
            **{f"PDATA{number}": text for number, text in (pdata or {}).items()},
        )
        guid = f"{{CON-{connector}}}"
        self._db.execute(
            "UPDATE t_connector SET ea_guid = ? WHERE Connector_ID = ?", (guid, connector)
        )
        for tag, value in (tags or {}).items():
            self._insert("t_connectortag", ElementID=connector, Property=tag, VALUE=value)
        for tag, text in (memo_tags or {}).items():
            self._insert(
                "t_connectortag", ElementID=connector, Property=tag, VALUE="<memo>", NOTES=text
            )
        if trigger:
            self._insert("t_xref", Client=guid, Name="CustomProperties", Description="trigger")
        return connector

    def diagram(self, name: str, package: int, diagram_type: str, members: Iterable[int]) -> int:
        """A diagram of ``diagram_type`` in ``package``, the ``members`` placed on it."""
        diagram = self._insert(
            "t_diagram", Name=name, Package_ID=package, Diagram_Type=diagram_type
        )
        for member in members:
            self.place(diagram, member)
        return diagram

    def diagram_link(self, diagram: int, connector: int, *, hidden: bool = False) -> None:
        """The row EA keeps for a connector on a diagram: ``Hidden`` is 1 when the modeller hid it (PD-12).

        EA writes a row for a connector it has drawn on a diagram; a connector with no row is shown.
        """
        self._insert(
            "t_diagramlinks", DiagramID=diagram, ConnectorID=connector, Hidden=1 if hidden else 0
        )

    def statechart(self, name: str, package: int, nodes: Iterable[int]) -> int:
        """A ``Statechart`` diagram: the one thing that groups states into a workflow (probe)."""
        return self.diagram(name, package, STATECHART_TYPE, nodes)

    def extra_stereotypes(self, owner: int, *names: str) -> int:
        """Record the stereotypes of ``owner`` in ``t_xref`` the way EA does, one entry per name."""
        guid = self._db.execute(
            "SELECT ea_guid FROM t_object WHERE Object_ID = ?", (owner,)
        ).fetchone()[0]
        entries = "".join(f"@STEREO;Name={name};GUID={{S-{name}}};@ENDSTEREO;" for name in names)
        return self._insert("t_xref", Client=guid, Name="Stereotypes", Description=entries)

    def attribute(
        self,
        owner: int,
        name: str,
        type_: str = "",
        lower: str = "0",
        upper: str = "1",
        stereotype: str | None = None,
        note: str | None = None,
        pos: int = 0,
    ) -> int:
        return self._insert(
            "t_attribute",
            Object_ID=owner,
            Name=name,
            Notes=note,
            Type=type_,
            LowerBound=lower,
            UpperBound=upper,
            Pos=pos,
            Stereotype=stereotype,
        )

    def association(
        self,
        source: int,
        destination: int,
        role: str,
        card: str | None,
        note: str | None = None,
        direction: str = DIRECTED,
        sub_type: str | None = None,
        pdata1: str | None = None,
    ) -> int:
        """A directed association with its role and cardinality at the destination.

        ``sub_type="Class"`` or a ``pdata1`` naming a class makes it an association class.
        """
        return self._insert(
            "t_connector",
            Connector_Type=ASSOCIATION_TYPE,
            SubType=sub_type,
            PDATA1=pdata1,
            Direction=direction,
            Notes=note,
            Start_Object_ID=source,
            End_Object_ID=destination,
            SourceIsAggregate=0,
            DestRole=role,
            DestCard=card,
            DestIsAggregate=0,
        )

    def dependency(self, source: int, destination: int, role: str, note: str | None = None) -> int:
        """A class-to-enumeration dependency, named by its destination role."""
        return self._insert(
            "t_connector",
            Connector_Type=DEPENDENCY_TYPE,
            Notes=note,
            Start_Object_ID=source,
            End_Object_ID=destination,
            DestRole=role,
        )

    def connector(self, connector_type: str, source: int, destination: int) -> int:
        """A bare connector of any type, as EA writes the ones no rule maps (Realisation, NoteLink)."""
        return self._insert(
            "t_connector",
            Connector_Type=connector_type,
            Start_Object_ID=source,
            End_Object_ID=destination,
        )

    def aggregation(
        self,
        whole: int,
        part: int,
        part_to_whole: bool = False,
        shared: bool = False,
        sub_type: str | None = None,
        stereotype: str | None = None,
        role: str | None = None,
        note: str | None = None,
        ends: tuple[int | None, int | None] | None = None,
    ) -> int:
        """An Aggregation connector, in the columns PD-1 states (D-5: the end column alone decides).

        Drawn whole to part: ``Start=whole``, ``SourceIsAggregate=2``; drawn part to whole:
        ``Start=part``, ``DestIsAggregate=2``; ``shared`` writes ``1`` in place of ``2``. ``role`` is
        written at the part's end. ``ends`` overrides the two columns, for the rows the drawing
        never makes (``(source, dest)``).
        """
        mark = 1 if shared else 2
        source_mark, dest_mark = (0, mark) if part_to_whole else (mark, 0)
        start, end = (part, whole) if part_to_whole else (whole, part)
        if ends is not None:
            source_mark, dest_mark = ends
        role_column = "SourceRole" if part_to_whole else "DestRole"
        return self._insert(
            "t_connector",
            Connector_Type=AGGREGATION_TYPE,
            SubType=sub_type,
            Stereotype=stereotype,
            Notes=note,
            Start_Object_ID=start,
            End_Object_ID=end,
            SourceIsAggregate=source_mark,
            DestIsAggregate=dest_mark,
            **{role_column: role},
        )

    def realisation(
        self,
        obj: int,
        target: int,
        from_target: bool = False,
        spelling: str = REALISATION_TYPE,
    ) -> int:
        """A Realisation between an Object and a class, drawn from the Object unless ``from_target``."""
        start, end = (target, obj) if from_target else (obj, target)
        return self.connector(spelling, start, end)

    def generalisation(self, child: int, parent: int) -> int:
        return self._insert(
            "t_connector",
            Connector_Type=GENERALISATION_TYPE,
            Start_Object_ID=child,
            End_Object_ID=parent,
        )

    def tag(self, owner: int, name: str, value: str, memo: str | None = None) -> int:
        """A tagged value; a ``memo`` keeps its text in ``Notes`` and ``<memo>`` in ``Value``."""
        if memo is not None:
            return self._insert(
                "t_objectproperties", Object_ID=owner, Property=name, Value="<memo>", Notes=memo
            )
        return self._insert("t_objectproperties", Object_ID=owner, Property=name, Value=value)

    def boundary(
        self,
        diagram: int,
        package: int | None = None,
        name: str = "Boundary",
        stereotype: str | None = None,
    ) -> int:
        """Place a boundary object on a diagram; it sits in ``package`` (none: in no package), by name only (PD-7)."""
        boundary = self._insert(
            "t_object",
            Object_Type=BOUNDARY_TYPE,
            Name=name,
            Package_ID=package,
            Stereotype=stereotype,
        )
        self.place(diagram, boundary)
        return boundary

    def place(self, diagram: int, obj: int, rect: tuple[int, int, int, int] | None = None) -> None:
        """Place an object on a diagram; ``rect`` is ``(left, top, right, bottom)``, as given, when a row wants one.

        The reader reads no geometry (PD-18), so most rows give none.
        """
        geometry: dict[str, object] = {}
        if rect is not None:
            left, top, right, bottom = rect
            geometry = {
                "RectTop": top,
                "RectLeft": left,
                "RectRight": right,
                "RectBottom": bottom,
            }
        self._insert("t_diagramobjects", Diagram_ID=diagram, Object_ID=obj, **geometry)

    def finish(self) -> Path:
        """Commit, close and return the path of the file."""
        self._db.commit()
        self._db.close()
        return self.path
