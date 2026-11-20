"""Build a small Enterprise Architect ``.qea`` file for tests (PD-24).

A helper, not a test module. No binary is checked in: a test builds the file in ``tmp_path``
with the stdlib ``sqlite3``. The seven tables are the ones the reader reads (PD-3), with
exactly the columns it reads; ``EA_COLUMNS`` lists the real columns of each, so a unit test can
assert that the DDL here invents none.
"""

import sqlite3
from collections.abc import Iterable
from pathlib import Path

# The column names of the seven tables, taken from EA's own schema (``pragma table_info`` on an
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
}

# The columns the reader reads (PD-3), no more.
DDL: dict[str, str] = {
    "t_package": (
        "CREATE TABLE t_package (Package_ID INTEGER PRIMARY KEY, Name TEXT, Parent_ID INTEGER,"
        " Notes TEXT)"
    ),
    "t_object": (
        "CREATE TABLE t_object (Object_ID INTEGER PRIMARY KEY, Object_Type TEXT, Name TEXT,"
        " Alias TEXT, Note TEXT, Package_ID INTEGER, Stereotype TEXT, Abstract TEXT,"
        " ea_guid TEXT)"
    ),
    "t_attribute": (
        "CREATE TABLE t_attribute (ID INTEGER PRIMARY KEY, Object_ID INTEGER, Name TEXT,"
        " Notes TEXT, Type TEXT, Classifier TEXT, LowerBound TEXT, UpperBound TEXT,"
        " Pos INTEGER, Stereotype TEXT)"
    ),
    "t_connector": (
        "CREATE TABLE t_connector (Connector_ID INTEGER PRIMARY KEY, Connector_Type TEXT,"
        " SubType TEXT, Stereotype TEXT, Notes TEXT, Start_Object_ID INTEGER,"
        " End_Object_ID INTEGER, SourceRole TEXT, SourceCard TEXT, SourceIsAggregate INTEGER,"
        " DestRole TEXT, DestCard TEXT, DestIsAggregate INTEGER, PDATA1 TEXT)"
    ),
    "t_objectproperties": (
        "CREATE TABLE t_objectproperties (Object_ID INTEGER, Property TEXT, Value TEXT, Notes TEXT)"
    ),
    "t_xref": "CREATE TABLE t_xref (Client TEXT, Name TEXT, Description TEXT)",
    "t_diagramobjects": (
        "CREATE TABLE t_diagramobjects (Diagram_ID INTEGER, Object_ID INTEGER, RectTop INTEGER,"
        " RectLeft INTEGER, RectRight INTEGER, RectBottom INTEGER)"
    ),
}

BOUNDARY_TYPE = "Boundary"
GENERALISATION_TYPE = "Generalization"
ASSOCIATION_TYPE = "Association"
DEPENDENCY_TYPE = "Dependency"


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
        return self._insert("t_package", Name=name, Parent_ID=parent, Notes=note)

    def cls(
        self,
        package: int,
        name: str,
        stereotype: str | None = None,
        object_type: str = "Class",
        abstract: bool = False,
        note: str | None = None,
    ) -> int:
        return self._insert(
            "t_object",
            Object_Type=object_type,
            Name=name,
            Note=note,
            Package_ID=package,
            Stereotype=stereotype,
            Abstract="1" if abstract else "0",
        )

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
        self, source: int, destination: int, role: str, card: str, note: str | None = None
    ) -> int:
        """A directed association with its role and cardinality at the destination."""
        return self._insert(
            "t_connector",
            Connector_Type=ASSOCIATION_TYPE,
            Notes=note,
            Start_Object_ID=source,
            End_Object_ID=destination,
            SourceIsAggregate=0,
            DestRole=role,
            DestCard=card,
            DestIsAggregate=0,
        )

    def dependency(self, source: int, destination: int, role: str) -> int:
        """A class-to-enumeration dependency, named by its destination role."""
        return self._insert(
            "t_connector",
            Connector_Type=DEPENDENCY_TYPE,
            Start_Object_ID=source,
            End_Object_ID=destination,
            DestRole=role,
        )

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
        self, diagram: int, rect: tuple[int, int, int, int], members: Iterable[int]
    ) -> int:
        """Place a boundary on a diagram, each member as a small rectangle at its centre.

        ``rect`` is ``(left, top, right, bottom)``; the boundary stays out of every package.
        """
        left, top, right, bottom = rect
        boundary = self._insert("t_object", Object_Type=BOUNDARY_TYPE, Name="Boundary")
        self._place(diagram, boundary, rect)
        centre_x, centre_y = (left + right) // 2, (top + bottom) // 2
        for member in members:
            self._place(diagram, member, (centre_x - 1, centre_y + 1, centre_x + 1, centre_y - 1))
        return boundary

    def _place(self, diagram: int, obj: int, rect: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = rect
        self._insert(
            "t_diagramobjects",
            Diagram_ID=diagram,
            Object_ID=obj,
            RectTop=top,
            RectLeft=left,
            RectRight=right,
            RectBottom=bottom,
        )

    def finish(self) -> Path:
        """Commit, close and return the path of the file."""
        self._db.commit()
        self._db.close()
        return self.path
