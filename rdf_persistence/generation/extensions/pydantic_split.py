"""gen-pydantic in split mode: one module per schema module, metadata off, the toolkit's templates (PD-24).

The stock generator lacks three things the toolkit needs, and this module adds them:

* the metamodel's classes are imported from the toolkit's package, never regenerated: from
  ``rdf_persistence.domain.generated.<module>`` inside the toolkit's own runs and from the public
  top-level package (DEC-6) in an application's run;
* enum members are named after the permissible-value keys in UPPER_SNAKE case, not after the titles;
* a slot annotated ``internal: true`` carries ``json_schema_extra={"rp_internal": True}`` (the
  ``attribute.py.jinja`` template), which the API layer reads; the slot is still dumped, because the
  mapper must persist it.
"""

import copy
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from linkml.generators.pydanticgen import PydanticGenerator
from linkml.generators.pydanticgen.build import SlotResult
from linkml.generators.pydanticgen.pydanticgen import MetadataMode, SplitMode
from linkml.generators.pydanticgen.template import Imports, PydanticAttribute
from linkml_runtime.linkml_model.meta import (
    ClassDefinition,
    EnumDefinition,
    SchemaDefinition,
    SlotDefinition,
)
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.checks.scope import (
    TOOLKIT_DIR,
    TRUE,
    annotation,
    is_toolkit_schema,
    own_schemas,
)
from rdf_persistence.generation.outputs import GeneratedFile
from rdf_persistence.generation.transform import apply_defaults
from rdf_persistence.services.schema import load_schema, metamodel_importmap

TEMPLATE_DIR = Path(__file__).parents[1] / "templates" / "pydantic"
PUBLIC_PACKAGE = "rdf_persistence"
TOOLKIT_PACKAGE = "rdf_persistence.domain.generated"
METAMODEL_DIR = TOOLKIT_DIR / "model"
INIT = "__init__.py"


class InternalAttribute(PydanticAttribute):
    """A pydantic attribute that also knows whether its slot is ``internal`` (see the template)."""

    internal: bool = False


def metamodel_module(name: str, *, toolkit: bool) -> str:
    """The module a class of the metamodel module ``name`` is imported from."""
    return f"{TOOLKIT_PACKAGE}.{name}" if toolkit else PUBLIC_PACKAGE


@dataclass
class SplitPydanticGenerator(PydanticGenerator):
    """gen-pydantic that imports as the rule above says, names enum members by key, marks internals."""

    toolkit: bool = False
    folder: Path | None = None

    def generate_module_import(self, schema: SchemaDefinition, context: dict | None = None) -> str:
        module: str = super().generate_module_import(schema, context)
        source = Path(str(schema.source_file)).resolve()
        if source.parent == self.folder:
            return module
        if source.parent != METAMODEL_DIR:
            raise ValueError(
                f"{schema.name} is neither beside the root schema nor in the metamodel"
            )
        return metamodel_module(module.lstrip("."), toolkit=self.toolkit)

    def _get_imports(self, element: ClassDefinition | SlotDefinition | None = None) -> Imports:
        """The stock class imports, plus the enums of other modules that a slot ranges over."""
        imports = super()._get_imports(element)
        if not self.split or (self.split_mode == SplitMode.FULL and element is not None):
            return imports
        sv = self.schemaview
        if element is None:
            used = list(sv.all_enums())
        elif isinstance(element, SlotDefinition):
            used = [name for name in sv.slot_range_as_union(element) if name in sv.all_enums()]
        else:
            used = []
        local = sv.all_enums(imports=False)
        for name in used:
            if name not in local:
                imports += self._get_element_import(name)
        return imports

    def before_generate_enums(
        self, enum: Iterable[EnumDefinition], sv: SchemaView
    ) -> Iterable[EnumDefinition]:
        """Keep this module's enums (the stock generator repeats imported ones); label them by key."""
        local = sv.all_enums(imports=False)
        keyed = [copy.deepcopy(e) for e in enum if e.name in local]
        for definition in keyed:
            for value in definition.permissible_values.values():
                value.title = None
        return keyed

    def generate_enum_label(self, value: str) -> str:
        label: str = super().generate_enum_label(value)
        return label.upper()

    def after_generate_slot(self, slot: SlotResult, sv: SchemaView) -> SlotResult:
        fields = {name: getattr(slot.attribute, name) for name in PydanticAttribute.model_fields}
        internal = annotation(slot.source, "internal") == TRUE
        slot.attribute = InternalAttribute(**fields, internal=internal)
        return slot


def _generator(path: Path, folder: Path, mode: SplitMode) -> SplitPydanticGenerator:
    generator = SplitPydanticGenerator(
        str(path),
        importmap=metamodel_importmap(),
        template_dir=TEMPLATE_DIR,
        metadata_mode=MetadataMode.NONE,
        emit_metadata=False,
        split=True,
        split_mode=mode,
        toolkit=is_toolkit_schema(folder),
        folder=folder.resolve(),
    )
    apply_defaults(generator.schemaview, folder)
    return generator


def render_modules(schema_path: Path) -> list[GeneratedFile]:
    """Generate one module per schema module beside ``schema_path``, and an empty package marker.

    The root schema's module imports every class of the closure, so it is the one place a consumer
    can import any class from; every other module imports only what its classes use.
    """
    folder = schema_path.parent
    modules = [GeneratedFile(INIT, "")]
    for schema in own_schemas(load_schema(schema_path), folder):
        path = Path(str(schema.source_file))
        mode = SplitMode.FULL if path.resolve() == schema_path.resolve() else SplitMode.AUTO
        generator = _generator(path, folder, mode)
        name = generator.generate_module_import(generator.schema).lstrip(".")
        modules.append(GeneratedFile(f"{name}.py", generator.serialize()))
    return sorted(modules, key=lambda module: module.name)
