"""gen-pydantic in split mode: one module per schema module, metadata off, the toolkit's templates (PD-24).

The stock generator lacks five things the toolkit needs, and this module adds them:

* the metamodel's classes are imported from the toolkit's package, never regenerated: from
  ``rdf_persistence.domain.generated.<module>`` inside the toolkit's own runs and from the public
  top-level package (DEC-6) in an application's run;
* enum members are named after the permissible-value keys in UPPER_SNAKE case, not after the titles;
* ``exactly_one_of``, ``any_of`` and ``unique_keys`` become model validators (``pydantic_validators``);
* a slot annotated ``internal: true`` carries ``json_schema_extra={"rp_internal": True}`` (the
  ``attribute.py.jinja`` template), which the API layer reads; the slot is still dumped, because the
  mapper must persist it;
* a slot annotated ``secret: true`` (``GenerationAnnotation``) is declared ``repr=False``, so its value
  stays out of the repr of the class;
* a slot annotated ``strict: true`` is declared ``strict=True``: pydantic then takes no coerced value
  (``"123"`` or ``true`` for a number).
"""

import copy
import keyword
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from linkml.generators.common.build import ClassResult
from linkml.generators.pydanticgen import PydanticGenerator
from linkml.generators.pydanticgen.build import SlotResult
from linkml.generators.pydanticgen.pydanticgen import (
    MetadataMode,
    SplitMode,
    make_valid_python_identifier,
)
from linkml.generators.pydanticgen.template import Import, Imports, ObjectImport, PydanticAttribute
from linkml_runtime.linkml_model.meta import (
    ClassDefinition,
    EnumDefinition,
    SchemaDefinition,
    SlotDefinition,
    TypeDefinition,
)
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.generation.exceptions import SchemaGenerationError
from rdf_persistence.generation.extensions.pydantic_validators import with_validators
from rdf_persistence.generation.generated.rp_generation import (
    GeneratedFile,
    GenerationAnnotation,
)
from rdf_persistence.services.schema import PACKAGE_DIR, load_schema, metamodel_importmap
from rdf_persistence.services.schema_structure import (
    TRUE_TEXT,
    annotation_text,
    apply_defaults,
    is_internal,
    is_toolkit_schema,
    own_schemas,
)

TEMPLATE_DIR = Path(__file__).parents[1] / "templates" / "pydantic"
PUBLIC_PACKAGE = "rdf_persistence"
TOOLKIT_PACKAGE = "rdf_persistence.domain.generated"
METAMODEL_DIR = PACKAGE_DIR / "model"
INIT = "__init__.py"
_LIST_DEFAULT = re.compile(
    r"string\((.*)\)"
)  # the ifabsent of a multivalued slot: its names, comma-separated


class InternalAttribute(PydanticAttribute):
    """A pydantic attribute that also knows whether its slot is ``internal`` or ``loosens`` its base class's (see the template)."""

    internal: bool = False
    loosens: bool = False
    secret: bool = False
    strict: bool = False
    default_factory: str | None = None


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
            raise SchemaGenerationError(
                f"{schema.name} is neither beside the root schema nor in the metamodel"
            )
        return metamodel_module(module.lstrip("."), toolkit=self.toolkit)

    def _get_imports(self, element: ClassDefinition | SlotDefinition | None = None) -> Imports:
        """The stock class imports, plus the enums of other modules that a slot ranges over, plus
        the Python import of a type whose ``repr`` names a class (the ``python_import`` annotation)."""
        imports = super()._get_imports(element) + self._python_imports(element)
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

    def _python_imports(self, element: ClassDefinition | SlotDefinition | None) -> Imports:
        """``from <python_import> import <repr>`` for each type a slot ranges over that declares both."""
        if not isinstance(element, SlotDefinition):
            return Imports()
        sv = self.schemaview
        types = [
            sv.get_type(name) for name in sv.slot_range_as_union(element) if name in sv.all_types()
        ]
        return Imports(imports=[_python_import(t) for t in types if t.repr and _python_module(t)])

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

    def after_generate_class(self, cls: ClassResult, sv: SchemaView) -> ClassResult:
        # the stock generator escapes quotes for its triple-quoted template; ours quotes the text itself
        cls.cls.description = cls.source.description
        return with_validators(cls, sv)

    def after_generate_slot(self, slot: SlotResult, sv: SchemaView) -> SlotResult:
        fields = {name: getattr(slot.attribute, name) for name in PydanticAttribute.model_fields}
        fields["description"] = slot.source.description  # the raw text, as for classes
        if not _is_python_name(slot.attribute.alias):
            fields["name"] = make_valid_python_identifier(underscore(slot.source.name))
        if slot.source.multivalued and slot.source.ifabsent is not None:
            fields["predefined"] = _list_default(slot.source)
        factory = _default_factory(slot.source)
        if factory is not None:
            fields["range"] = factory  # never absent, so never ``Optional``
        internal = is_internal(slot.source)
        secret = annotation_text(slot.source, GenerationAnnotation.SECRET) == TRUE_TEXT
        slot.attribute = InternalAttribute(
            **fields,
            internal=internal,
            loosens=_loosens_a_base_slot(slot.source, sv),
            secret=secret,
            strict=annotation_text(slot.source, GenerationAnnotation.STRICT) == TRUE_TEXT,
            default_factory=factory,
        )
        return slot


def _is_python_name(alias: str | None) -> bool:
    """Whether the stock field name, which is the slot's alias when it has one, can stand as it is.

    The stock generator names a field after the alias and sets ``alias=`` only when the two differ;
    a dotted alias (``rp.step``) would become ``rp_step``. Such a slot is named after itself instead.
    """
    return alias is None or (alias.isidentifier() and not keyword.iskeyword(alias))


def _list_default(slot: SlotDefinition) -> str:
    """The Python list a multivalued slot's ``ifabsent: string(a, b)`` stands for.

    The stock generator writes the one string ``"a, b"`` as the default of a list field, which is no list.
    """
    found = _LIST_DEFAULT.fullmatch(str(slot.ifabsent))
    if found is None:
        raise SchemaGenerationError(
            f"{slot.name} is multivalued: its ifabsent must be string(a, b, ...), got {slot.ifabsent}"
        )
    return repr([name.strip() for name in found.group(1).split(",")])


def _default_factory(slot: SlotDefinition) -> str | None:
    """The class name a ``default_instance`` slot builds its default from; None for any other slot.

    The hard check (``checks/default_instance.py``) has already refused a slot whose range is no class.
    """
    flagged = annotation_text(slot, GenerationAnnotation.DEFAULT_INSTANCE) == TRUE_TEXT
    return camelcase(str(slot.range)) if flagged else None


def _python_module(definition: TypeDefinition) -> str | None:
    return annotation_text(definition, GenerationAnnotation.PYTHON_IMPORT)


def _python_import(definition: TypeDefinition) -> Import:
    return Import(
        module=str(_python_module(definition)), objects=[ObjectImport(name=str(definition.repr))]
    )


def _loosens_a_base_slot(slot: SlotDefinition, sv: SchemaView) -> bool:
    """Whether the slot, as its class declares it, is optional where an ancestor's is required (PD-11).

    The generated subclass then redeclares the field with a wider type, which mypy reports as an
    incompatible override; the template marks that line.
    """
    if slot.required or slot.identifier or slot.key or slot.owner is None:
        return False
    return any(
        sv.induced_slot(slot.name, ancestor).required
        for ancestor in sv.class_ancestors(slot.owner, reflexive=False)
        if slot.name in sv.class_slots(ancestor)
    )


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


def render(schema_path: Path) -> list[GeneratedFile]:
    """Generate one module per schema module beside ``schema_path``, and an empty package marker.

    The root schema's module imports every class of the closure, so it is the one place a consumer
    can import any class from; every other module imports only what its classes use.
    """
    folder = schema_path.parent
    modules = [GeneratedFile(name=INIT, text="")]
    for schema in own_schemas(load_schema(schema_path), folder):
        path = Path(str(schema.source_file))
        mode = SplitMode.FULL if path.resolve() == schema_path.resolve() else SplitMode.AUTO
        generator = _generator(path, folder, mode)
        name = generator.generate_module_import(generator.schema).lstrip(".")
        modules.append(GeneratedFile(name=f"{name}.py", text=generator.serialize()))
    return sorted(modules, key=lambda module: module.name)
