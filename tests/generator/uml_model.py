"""Builders for the converter's tests: a ``UmlModel`` written down directly, the reader left out.

The generic library model: packages ``model`` (the subtree root), ``library``, ``catalogue`` and
``shelves``; ids of classes are the constants below, so a row reads the same as the diagram it stands for.
"""

from dataclasses import dataclass

from linkml_runtime.linkml_model import (
    ClassDefinition,
    EnumDefinition,
    SchemaDefinition,
    SlotDefinition,
)

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    ReportLine,
    UmlAttribute,
    UmlBoundary,
    UmlClass,
    UmlLink,
    UmlLinkKind,
    UmlModel,
    UmlPackage,
    UmlPrefix,
    UmlSettings,
    UmlTaggedValue,
)
from rdf_persistence_generation.uml.convert import convert

NS = "https://example.org/ns/library#"
BASE = "https://example.org/ns/library/"
PREFIXES = {"lib": NS, "dct": "http://purl.org/dc/terms/", "bibo": "http://purl.org/ontology/bibo/"}
METAMODEL_PREFIXES = {
    "dcterms": "http://purl.org/dc/terms/",
    "rp": "https://meaningfy.ws/ns/rdf-persistence#",
}

DIRECTED = "Source -> Destination"
BIDIRECTIONAL = "Bi-Directional"

MODEL_PKG, LIBRARY_PKG, CATALOGUE_PKG, SHELVES_PKG = 1, 2, 3, 4
EXTERNAL_PKG = 8  # a package outside the subtree, as the reader reports it in uml_outside_packages
BOOK, CHAPTER, SHELF, GENRE, SERIES = 10, 11, 12, 13, 14

PACKAGES = (
    UmlPackage(package_id=MODEL_PKG, name="model"),
    UmlPackage(package_id=LIBRARY_PKG, name="library", parent_id=MODEL_PKG),
    UmlPackage(package_id=CATALOGUE_PKG, name="catalogue", parent_id=MODEL_PKG),
    UmlPackage(package_id=SHELVES_PKG, name="shelves", parent_id=MODEL_PKG),
)


def attribute(
    attribute_id: int,
    owner: int,
    name: str,
    declared_type: str = "xsd:string",
    *,
    lower: str | None = "1",
    upper: str | None = "1",
    note: str | None = "An attribute.",
    position: int = 0,
    stereotype: str | None = None,
    classifier: int | None = None,
) -> UmlAttribute:
    return UmlAttribute(
        attribute_id=attribute_id,
        owner_id=owner,
        name=name,
        note=note,
        declared_type=declared_type,
        classifier_id=classifier,
        lower_bound=lower,
        upper_bound=upper,
        position=position,
        uml_stereotype=stereotype,
    )


def klass(
    object_id: int,
    name: str,
    package: int = LIBRARY_PKG,
    *,
    note: str | None = "A class.",
    stereotype: str | None = None,
    abstract: bool = False,
    attributes: tuple[UmlAttribute, ...] = (),
    object_type: str = "Class",
    alias: str | None = None,
) -> UmlClass:
    return UmlClass(
        object_id=object_id,
        name=name,
        object_type=object_type,
        uml_alias=alias,
        note=note,
        package_id=package,
        uml_stereotype=stereotype,
        is_abstract=abstract,
        uml_attributes=list(attributes),
    )


def enumeration(
    object_id: int, name: str, literals: tuple[str, ...], package: int = LIBRARY_PKG
) -> UmlClass:
    return klass(
        object_id,
        name,
        package,
        object_type="Enumeration",
        attributes=tuple(
            attribute(
                object_id * 100 + n, object_id, literal, "", note=f"The {literal}.", position=n
            )
            for n, literal in enumerate(literals)
        ),
    )


def link(
    connector_id: int,
    source: int,
    target: int,
    *,
    kind: UmlLinkKind = UmlLinkKind.ASSOCIATION,
    source_role: str | None = None,
    source_card: str | None = None,
    target_role: str | None = None,
    target_card: str | None = None,
    source_aggregate: int = 0,
    target_aggregate: int = 0,
    note: str | None = "A connector.",
    stereotype: str | None = None,
    direction: str | None = None,
) -> UmlLink:
    """A connector; with no ``direction`` given, a source role makes it bi-directional, else directed."""
    if direction is None:
        direction = BIDIRECTIONAL if source_role else DIRECTED
    return UmlLink(
        connector_id=connector_id,
        link_kind=kind,
        uml_stereotype=stereotype,
        note=note,
        direction=direction,
        source_id=source,
        target_id=target,
        source_role=source_role,
        source_card=source_card,
        source_aggregate=source_aggregate,
        target_role=target_role,
        target_card=target_card,
        target_aggregate=target_aggregate,
    )


def generalisation(connector_id: int, child: int, parent: int) -> UmlLink:
    return link(connector_id, child, parent, kind=UmlLinkKind.GENERALISATION, note=None)


def tag(owner: int, name: str, value: str) -> UmlTaggedValue:
    return UmlTaggedValue(owner_id=owner, name=name, tag_value=value)


def boundary(object_id: int, *members: int) -> UmlBoundary:
    return UmlBoundary(
        object_id=object_id, name="Aggregate", diagram_id=1, member_ids=list(members)
    )


def model(
    *classes: UmlClass,
    links: tuple[UmlLink, ...] = (),
    tags: tuple[UmlTaggedValue, ...] = (),
    boundaries: tuple[UmlBoundary, ...] = (),
    packages: tuple[UmlPackage, ...] = PACKAGES,
    outside: tuple[UmlClass, ...] = (),
    outside_packages: tuple[UmlPackage, ...] = (),
) -> UmlModel:
    """A model; ``outside`` are the classes at a link's far end the reader did not convert (D-17)."""
    return UmlModel(
        uml_packages=list(packages),
        uml_outside_packages=list(outside_packages),
        uml_outside_classes=list(outside),
        uml_classes=list(classes),
        uml_links=list(links),
        uml_tagged_values=list(tags),
        uml_boundaries=list(boundaries),
    )


def settings(**overrides: object) -> UmlSettings:
    values: dict[str, object] = {
        "schema_base": BASE,
        "default_prefix": "lib",
        "schema_version": "1",
        "prefixes": [UmlPrefix(prefix_name=p, namespace=ns) for p, ns in PREFIXES.items()],
        "subtree_package": "model",
        "root_name": "app",
        "not_generated_stereotypes": ["loaded graph"],
    }
    values.update(overrides)
    return UmlSettings(**values)


@dataclass(frozen=True)
class Converted:
    """What one conversion returned, with the accessors the rows read."""

    schemas: dict[str, SchemaDefinition]
    report: list[ReportLine]
    problems: list[CheckProblem]

    def klass(self, module: str, name: str) -> ClassDefinition:
        return self.schemas[module].classes[name]

    def slot(self, module: str, name: str) -> SlotDefinition:
        return self.schemas[module].slots[name]

    def enum(self, module: str, name: str) -> EnumDefinition:
        return self.schemas[module].enums[name]

    def report_lines(self, kind: str) -> list[str]:
        return [
            f"{line.element}: {line.message}" for line in self.report if line.report_kind == kind
        ]

    def problem_texts(self) -> list[str]:
        return [f"[{p.rule}] {p.element}: {p.message}" for p in self.problems]


def run(uml: UmlModel, **overrides: object) -> Converted:
    schemas, report, problems = convert(uml, settings(**overrides), METAMODEL_PREFIXES)
    return Converted({schema.name: schema for schema in schemas}, report, problems)
