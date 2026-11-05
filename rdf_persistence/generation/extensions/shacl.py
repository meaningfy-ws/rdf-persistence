"""gen-shacl with the toolkit's bookkeeping, its reference rule and the declared rules (PD-24, PD-7).

The stock generator lacks six things:

* the predicates the session writes (``rp:version``, ``dcterms:created``, ``dcterms:modified``,
  ``dcterms:creator``, ``dcterms:contributor``) are added to the ignored properties of closed shapes,
  so a graph that carries them still validates;
* each class gets a shape of its own, named by its native IRI, because classes may share a
  ``class_uri`` (a narrowed ``Grant``);
* a slot that refers to another aggregate (not ``owned``) is checked as an IRI only, so an
  aggregate's graph validates on its own, without the referenced aggregate in it;
* a class whose instances have an identifier is a node that must be an IRI, which no property shape can
  say, since the IRI is the subject; a class without one (a grant) may be a blank node;
* an ``internal`` slot is optional: the toolkit writes it, never the client, so a body without it must
  validate, while the generated class keeps the slot as declared (PD-24);
* ``exactly_one_of``, ``any_of`` and ``unique_keys`` are translated (``shacl_constraints``).
"""

from dataclasses import dataclass
from pathlib import Path

from linkml.generators.shaclgen import ShaclGenerator
from linkml_runtime.linkml_model.meta import ClassDefinition
from rdflib import BNode, Graph, URIRef
from rdflib.collection import Collection
from rdflib.namespace import SH

from rdf_persistence.generation.checks.scope import TRUE, annotation
from rdf_persistence.generation.extensions.shacl_constraints import constraints_graph, shape_uri
from rdf_persistence.generation.outputs import GeneratedFile
from rdf_persistence.generation.transform import apply_defaults
from rdf_persistence.services.schema import metamodel_importmap

SHAPES_FILE = "shapes.ttl"
BOOKKEEPING_SLOTS = ("version", "created", "modified", "creator", "contributor")


@dataclass
class RpShaclGenerator(ShaclGenerator):
    """gen-shacl as the module docstring describes."""

    use_class_uri_names: bool = False

    def _bookkeeping(self) -> set[URIRef]:
        sv = self.schemaview
        slots = sv.all_slots()
        return {
            URIRef(sv.get_uri(slots[name], expand=True))
            for name in BOOKKEEPING_SLOTS
            if name in slots
        }

    def _build_ignored_properties(self, g: Graph, c: ClassDefinition) -> BNode:
        node: BNode = super()._build_ignored_properties(g, c)
        if not (self.closed and not (c.mixin or c.abstract)):
            return node
        items = Collection(g, node)
        merged = sorted({*items, *self._bookkeeping()}, key=str)
        items.clear()
        Collection(g, node, merged)
        return node

    def _refer_by_iri(self, g: Graph) -> None:
        """Drop the class or shape check from every slot that refers to another aggregate."""
        sv = self.schemaview
        classes = sv.all_classes()
        for cls in classes.values():
            shape = shape_uri(sv, cls)
            for slot in sv.class_induced_slots(cls.name):
                if slot.range not in classes or annotation(slot, "owned") == TRUE:
                    continue
                path = URIRef(sv.get_uri(slot, expand=True))
                for prop in g.objects(shape, SH.property):
                    if (prop, SH.path, path) in g:
                        g.remove((prop, SH.node, None))
                        g.remove((prop, SH["class"], None))

    def _require_iri_nodes(self, g: Graph) -> None:
        """Add ``sh:nodeKind sh:IRI`` to the shape of every class with an identifier slot."""
        sv = self.schemaview
        for cls in sv.all_classes().values():
            if sv.get_identifier_slot(cls.name) is not None:
                g.add((shape_uri(sv, cls), SH.nodeKind, SH.IRI))

    def _relax_internal_slots(self, g: Graph) -> None:
        """Drop ``sh:minCount`` from the properties of ``internal`` slots."""
        sv = self.schemaview
        for cls in sv.all_classes().values():
            shape = shape_uri(sv, cls)
            for slot in sv.class_induced_slots(cls.name):
                if annotation(slot, "internal") != TRUE:
                    continue
                path = URIRef(sv.get_uri(slot, expand=True))
                for prop in g.objects(shape, SH.property):
                    if (prop, SH.path, path) in g:
                        g.remove((prop, SH.minCount, None))

    def as_graph(self) -> Graph:
        g: Graph = super().as_graph()
        self._refer_by_iri(g)
        self._require_iri_nodes(g)
        self._relax_internal_slots(g)
        g += constraints_graph(self.schemaview)
        return g


def render_shapes(schema_path: Path) -> GeneratedFile:
    """The closed shapes of the schema and its closure, as Turtle in a canonical form."""
    generator = RpShaclGenerator(str(schema_path), importmap=metamodel_importmap())
    apply_defaults(generator.schemaview, schema_path.parent)
    return GeneratedFile(SHAPES_FILE, generator.serialize())
