"""Step 7: one Mermaid class diagram per module (D-8, PD-25).

The stock ``gen-mermaid-class-diagram`` writes one Markdown file per class from a template that knows
nothing of aggregates, and it opens the schema without the metamodel import map (PD-22). This subclass
keeps its naming and cardinality helpers, opens the schema through the map, and renders one ``.mmd``
file per module from the toolkit's template: aggregate roots carry ``<<root>>``, owned parts
``<<owned>>``, ownership is a composition and any other reference an arrow, and a class of another
module is drawn as its name only. Mixins are not drawn: the stereotype says what they would.
"""

from pathlib import Path

from linkml.generators.mermaidclassdiagramgen import MermaidClassDiagramGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition, SchemaDefinition, SlotDefinition

from rdf_persistence.generation.generated.rp_generation import (
    GeneratedFile,
    MmdAttribute,
    MmdClass,
    MmdModule,
)
from rdf_persistence.generation.templating import environment
from rdf_persistence.services.schema import metamodel_importmap
from rdf_persistence.services.schema_structure import (
    declared_slot_names,
    is_internal,
    is_owned,
    own_schemas,
    owned_class_names,
    root_classes,
)

TEMPLATES = "mermaid"
TEMPLATE = "module.mmd.jinja"
ROOT = "root"
OWNED = "owned"


class ToolkitMermaidGenerator(MermaidClassDiagramGenerator):
    """``gen-mermaid-class-diagram`` with the toolkit's template, one diagram per module."""

    def __post_init__(self) -> None:
        super().__post_init__()
        # the stock generator rebuilt its view without the import map; nothing has read an import yet
        self.schemaview.importmap = metamodel_importmap()
        source = Path(self.schema.source_file)
        self.roots = {cls.name for cls in root_classes(self.schemaview, source.parent)}
        self.owned = owned_class_names(self.schemaview, source.parent)

    def _stereotype(self, cls: ClassDefinition) -> str | None:
        if cls.name in self.roots:
            return ROOT
        return OWNED if cls.name in self.owned else None

    def _induced(self, cls: ClassDefinition) -> list[SlotDefinition]:
        """The slots the class declares or narrows, without the ``internal`` ones."""
        slots = (self.schemaview.induced_slot(name, cls.name) for name in declared_slot_names(cls))
        return [slot for slot in slots if not is_internal(slot)]

    def _attribute(self, slot: SlotDefinition) -> MmdAttribute:
        type_name = f"List~{slot.range}~" if slot.multivalued else str(slot.range)
        return MmdAttribute(type=type_name, name=self.name(slot))

    def _link(self, cls: ClassDefinition, slot: SlotDefinition) -> str:
        arrow = "*--" if is_owned(slot) else "-->"
        target = self.name(self.schemaview.get_class(slot.range))
        return (
            f'{self.name(cls)} "1" {arrow} "{self.cardinality(slot)}" {target} : {self.name(slot)}'
        )

    def _class_parts(self, cls: ClassDefinition) -> tuple[MmdClass, list[str], set[str]]:
        """The box of a class, its links, and the names of the classes the links reach."""
        slots = self._induced(cls)
        references = [slot for slot in slots if slot.range in self.schemaview.all_classes()]
        attributes = [self._attribute(slot) for slot in slots if slot not in references]
        links = [self._link(cls, slot) for slot in references]
        named = {slot.range for slot in references}
        if cls.is_a:
            parent = self.name(self.schemaview.get_class(cls.is_a))
            links.append(f"{parent} <|-- {self.name(cls)}")
            named.add(cls.is_a)
        box = MmdClass(name=self.name(cls), stereotype=self._stereotype(cls), attributes=attributes)
        return box, links, named

    def module(self, schema: SchemaDefinition) -> MmdModule:
        """The diagram of the classes ``schema`` defines."""
        classes = [cls for cls in schema.classes.values() if not cls.mixin]
        diagram = MmdModule(classes=[], links=[], externals=[])
        named: set[str] = set()
        for cls in classes:
            box, links, reached = self._class_parts(cls)
            diagram.classes.append(box)
            diagram.links.extend(links)
            named |= reached
        outside = named - {cls.name for cls in classes}
        diagram.externals = sorted(self.name(self.schemaview.get_class(n)) for n in outside)
        return diagram

    def files(self, schemas: list[SchemaDefinition]) -> list[GeneratedFile]:
        template = environment(TEMPLATES).get_template(TEMPLATE)
        return [
            GeneratedFile(
                name=f"{schema.name}.mmd", text=template.render(module=self.module(schema))
            )
            for schema in schemas
            if any(not cls.mixin for cls in schema.classes.values())
        ]


def render(schema_path: Path) -> list[GeneratedFile]:
    """One ``<module>.mmd`` per module, kept beside the schema, that defines classes."""
    generator = ToolkitMermaidGenerator(
        str(schema_path), directory="", importmap=metamodel_importmap(), mergeimports=False
    )
    schemas = own_schemas(generator.schemaview, schema_path.parent)
    return generator.files(sorted(schemas, key=lambda schema: schema.name))
