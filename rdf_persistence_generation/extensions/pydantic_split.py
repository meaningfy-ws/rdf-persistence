"""gen-pydantic in split mode: one module per schema module, metadata off, the toolkit's templates (PD-24).

The stock generator lacks thirteen things the toolkit needs, and this module adds them:

* a class's ``is_a`` parent is its first base, in whatever module the parent is declared; the
  stock generator puts an imported parent last, which no MRO allows next to its mixins (#242);
* the module refers to the capitalised names it imports from ``pydantic``, ``typing``,
  ``decimal`` and ``enum`` under ``_`` aliases (``_Field``, ``_Optional``), so a schema class
  named ``Field`` shadows nothing (#243);

* the metamodel's classes are imported from the toolkit's package, never regenerated: from
  ``<python_package>.<module>`` inside the toolkit's own runs, the ``python_package`` annotation of
  the module saying where its classes live, and from the ``public_package`` of ``rp.yaml`` (DEC-6,
  DEC-7) in an application's run; the classes of a module of another target that names its
  ``python_package`` are imported from there too, never regenerated (PD-3);
* enum members are named after the permissible-value keys in UPPER_SNAKE case, not after the titles;
* ``exactly_one_of``, ``any_of`` and ``unique_keys`` become model validators (``pydantic_validators``);
* a slot annotated ``internal: true`` carries ``json_schema_extra={"rp_internal": True}`` (the
  ``attribute.py.jinja`` template), which the API layer reads; the slot is still dumped, because the
  mapper must persist it;
* a slot annotated ``secret: true`` (``GenerationAnnotation``) is declared ``repr=False``, so its value
  stays out of the repr of the class;
* a slot annotated ``strict: true`` is declared ``strict=True``: pydantic then takes no coerced value
  (``"123"`` or ``true`` for a number);
* a LinkML type annotated ``python_import: <module>`` whose ``repr`` names a class (``SparqlTerm``)
  generates ``from <module> import <repr>``, so a field ranging over the type has that class;
* a slot annotated ``default_instance: 'true'`` is declared ``Field(default_factory=<Range>)``, so a group
  of settings is never absent (the hard check refuses a slot whose range cannot be built with no argument);
* the ``ifabsent: string(a, b, ...)`` of a multivalued slot is the default list ``['a', 'b']``; the
  stock generator writes the one string ``"a, b"`` on a list field, and any other form is refused;
* a slot whose alias is no Python name (``rp.step``) is named after the slot, and keeps the alias;
* a slot annotated ``field_name: slot`` (``GenerationAnnotation``, D-52) with an identifier alias (``schema``) is
  named after the slot too, and keeps the alias; every other field keeps the stock name.
"""

import ast
import copy
import keyword
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import cache, cached_property
from pathlib import Path

from linkml.generators.common.build import ClassResult
from linkml.generators.pydanticgen import PydanticGenerator
from linkml.generators.pydanticgen.build import SlotResult
from linkml.generators.pydanticgen.pydanticgen import (
    MetadataMode,
    SplitMode,
    make_valid_python_identifier,
)
from linkml.generators.pydanticgen.template import (
    Import,
    Imports,
    ObjectImport,
    PydanticAttribute,
    PydanticBaseModel,
    PydanticModule,
)
from linkml_runtime.linkml_model.meta import (
    ClassDefinition,
    EnumDefinition,
    SchemaDefinition,
    SlotDefinition,
    TypeDefinition,
)
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.schema.services.schema import PACKAGE_DIR, load_schema, metamodel_importmap
from rdf_persistence.schema.services.schema_structure import (
    FIELD_NAME_SLOT,
    TRUE_TEXT,
    annotation_text,
    apply_defaults,
    generated_schemas,
    is_internal,
    is_switched_on,
    is_toolkit_schema,
    own_schemas,
)
from rdf_persistence_generation.config import TOOLKIT_ROOTS
from rdf_persistence_generation.exceptions import SchemaGenerationError
from rdf_persistence_generation.extensions.pydantic_validators import with_validators
from rdf_persistence_generation.generated.rp_generation import (
    GeneratedFile,
    GenerationAnnotation,
)
from rdf_persistence_generation.module_cycles import (
    analyse,
    deferred_by_module,
    modules_in_cycles,
)

TEMPLATE_DIR = Path(__file__).parents[1] / "templates" / "pydantic"
METAMODEL_DIR = PACKAGE_DIR / "model"
INIT = "__init__.py"
TYPING = "typing"
INIT_DOC = "Completes the classes of the modules that import each other (rp-generate)."
BASE_MODEL = "RpModel"
BASE_MODULE = "base"
GENERATED_LEAF = "generated"
ANY_CLASS_URI = "linkml:Any"
_LIST_DEFAULT = re.compile(
    r"string\((.*)\)"
)  # the ifabsent of a multivalued slot: its names, comma-separated


# The library names a generated module refers to under `_` aliases, so no schema class shadows
# them (#243): a class named `Field` would rebind `Field`, and every later `x: str = Field(...)`
# would build that class. A generated class is named in camel case, which never starts with `_`;
# only a capitalised name needs an alias, since the lint refuses a lower-case class name
# (standard_naming), so `datetime`, `re` or `field_validator` are safe as they are.
LIBRARY_MODULES = frozenset({"decimal", "enum", "pydantic", "typing"})
SHADOWABLE = frozenset(
    {
        "Any",
        "BaseModel",
        "ClassVar",
        "ConfigDict",
        "Decimal",
        "Enum",
        "Field",
        "Literal",
        "Optional",
        "RootModel",
        "SerializationInfo",
        "SerializerFunctionWrapHandler",
        "Union",
    }
)


def alias_imports(imports: Imports) -> None:
    """Import every shadowable library name as its alias (``from pydantic import Field as _Field``)."""
    for each in imports.imports:
        if each.module in LIBRARY_MODULES:
            for name in each.objects or []:
                if name.name in SHADOWABLE:
                    name.alias = f"_{name.name}"


def drop_imports(imports: Imports, names: set[str]) -> None:
    """Import none of ``names`` from a schema's module; a module left with no name is not imported."""
    for each in imports.imports:
        if each.module not in LIBRARY_MODULES and each.objects:
            each.objects = [name for name in each.objects if name.name not in names]
    imports.imports = [each for each in imports.imports if each.objects != []]


def alias_leaf(pyrange: str) -> str:
    """A type's Python range (``Decimal``, ``Any``) as its alias; the caller knows it names no class."""
    return f"_{pyrange}" if pyrange in SHADOWABLE else pyrange


def alias_heads(expression: str) -> str:
    """Alias the library names an annotation subscripts (``Optional[...]``); its leaves are left as they are.

    A subscripted name is always the library's: a schema class is never subscripted. Offsets are
    in UTF-8 bytes, so the splice is done on the encoded text.
    """
    heads = [
        node.value.col_offset
        for node in ast.walk(ast.parse(expression, mode="eval"))
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id in SHADOWABLE
    ]
    text = expression.encode()
    for offset in sorted(heads, reverse=True):
        text = text[:offset] + b"_" + text[offset:]
    return text.decode()


class InternalAttribute(PydanticAttribute):
    """A pydantic attribute that also knows whether its slot is ``internal`` or ``loosens`` its base class's (see the template)."""

    internal: bool = False
    loosens: bool = False
    secret: bool = False
    strict: bool = False
    default_factory: str | None = None


@cache
def public_package() -> str:
    """The package an application imports the metamodel's classes from: the ``public_package`` of ``rp.yaml`` (DEC-7)."""
    root = load_schema(METAMODEL_DIR / "rp.yaml").schema
    return _required_annotation(root, GenerationAnnotation.PUBLIC_PACKAGE)


def _required_annotation(schema: SchemaDefinition, tag: GenerationAnnotation) -> str:
    text = annotation_text(schema, tag)
    if text is None:
        raise SchemaGenerationError(f"{schema.name} has no {tag.value} annotation")
    return text


def metamodel_module(schema: SchemaDefinition, *, toolkit: bool) -> str:
    """The module a class of the metamodel's ``schema`` module is imported from.

    A toolkit run imports it from the package the module says it lives in (``python_package``),
    an application's run from the public package, which ``rp.yaml`` names (DEC-7, PD-6).
    """
    if not toolkit:
        return public_package()
    return target_module(schema)


@cache
def toolkit_base_module() -> str:
    """The module that holds ``RpModel``, for the toolkit's own run (PD-8).

    It sits beside the metamodel's generated package: ``python_package`` of ``rp.yaml`` with its
    ``generated`` leaf replaced by ``base`` (``rdf_persistence.core.domain.generated`` gives
    ``rdf_persistence.core.domain.base``).
    """
    root = load_schema(METAMODEL_DIR / "rp.yaml").schema
    package = _dotted_package(root)
    parent, _, leaf = package.rpartition(".")
    if leaf != GENERATED_LEAF or not parent:
        raise SchemaGenerationError(
            f"the python_package of rp.yaml ({package}) must end in .{GENERATED_LEAF}, "
            f"so the module of {BASE_MODEL} can be found beside it"
        )
    return f"{parent}.{BASE_MODULE}"


def base_model_module(*, toolkit: bool) -> str:
    """The module a generated module imports ``RpModel`` from: the public package for an
    application, its own module for the toolkit, whose top package imports the generated code (PD-8)."""
    return toolkit_base_module() if toolkit else public_package()


class RpBaseModel(PydanticBaseModel):
    """The base-model template's data, plus the module ``RpModel`` is imported from."""

    module: str = ""


class RpModule(PydanticModule):
    """The module template's data, plus the imports a module of a cycle makes for the type checker only (PD-5)."""

    deferred: Imports | None = None
    in_cycle: bool = False


def target_module(schema: SchemaDefinition) -> str:
    """The module a class of ``schema`` is imported from: its ``python_package``, then its name (PD-3)."""
    return f"{_dotted_package(schema)}.{schema.name}"


def _dotted_package(schema: SchemaDefinition) -> str:
    """The ``python_package`` of ``schema``: a dotted name of identifiers, or a refusal naming it."""
    tag = GenerationAnnotation.PYTHON_PACKAGE
    package = _required_annotation(schema, tag)
    if not all(part.isidentifier() for part in package.split(".")):
        raise SchemaGenerationError(
            f"{schema.name}: the {tag.value} annotation ({package!r}) is not a dotted Python name"
        )
    return package


@dataclass
class SplitPydanticGenerator(PydanticGenerator):
    """gen-pydantic that imports as the rule above says, names enum members by key, marks internals."""

    toolkit: bool = False
    folder: Path | None = None
    root_package: str | None = None
    # PD-5: per source module (its name, no dot), the names this module imports for the type checker only
    deferred: dict[str, tuple[str, ...]] = field(default_factory=dict)
    in_cycle: bool = False
    class_names: list[str] = field(
        default_factory=list, init=False
    )  # the classes the module defines, in order

    def generate_module_import(self, schema: SchemaDefinition, context: dict | None = None) -> str:
        module: str = super().generate_module_import(schema, context)
        source = Path(str(schema.source_file)).resolve()
        if source.parent == self.folder:
            return module if self._generated_here(schema) else target_module(schema)  # PD-2
        if source.parent == METAMODEL_DIR:
            return metamodel_module(schema, toolkit=self.toolkit)
        if annotation_text(schema, GenerationAnnotation.PYTHON_PACKAGE) is not None:
            return target_module(schema)  # a module of another target (PD-3)
        raise SchemaGenerationError(
            f"{schema.name} is neither beside the root schema, nor in the metamodel, "
            f"nor says where its classes live ({GenerationAnnotation.PYTHON_PACKAGE.value})"
        )

    def _generated_here(self, schema: SchemaDefinition) -> bool:
        """Whether a module beside the root is written into the root's package: it names that package, or the root names none."""
        package = annotation_text(schema, GenerationAnnotation.PYTHON_PACKAGE)
        return self.root_package is None or package in (None, self.root_package)

    @property
    def class_bases(self) -> dict[str, list[str]]:
        """The stock bases with the ``is_a`` parent first, wherever it is declared (#242).

        The stock generator orders the bases by the parents' places in this module and puts an
        imported one last, after the mixins it already has, which no MRO allows.
        """
        reordered: dict[str, list[str]] | None = self._class_bases
        if reordered is not None:  # reordered on the first access
            return reordered
        bases: dict[str, list[str]] = super().class_bases
        for cls in self.schemaview.all_classes().values():
            name = self._get_class_python_name(cls.name)
            if cls.is_a and name in bases:
                parent = self._get_class_python_name(cls.is_a)
                bases[name] = [parent, *(base for base in bases[name] if base != parent)]
        return bases

    def before_render_template(self, module: PydanticModule, sv: SchemaView) -> PydanticModule:
        """Name the module ``RpModel`` is imported from (PD-8); import the library names as aliases (#243).

        A module of a cycle imports its deferred names under ``if _TYPE_CHECKING:`` (PD-5).
        """
        module.base_model = RpBaseModel(
            **module.base_model.model_dump(), module=base_model_module(toolkit=self.toolkit)
        )
        alias_imports(module.python_imports)
        drop_imports(module.python_imports, self._any_classes)
        self.class_names = list(module.class_names)
        if not self.in_cycle:
            return module
        # the field values themselves, not model_dump(): the classes keep their InternalAttribute
        fields = {name: getattr(module, name) for name in PydanticModule.model_fields}
        imports = module.python_imports.model_copy(
            deep=True
        )  # its objects are shared between modules
        fields["python_imports"] = imports
        return RpModule(**fields, deferred=self._defer(imports), in_cycle=True)

    def _defer(self, imports: Imports) -> Imports | None:
        """Move the deferred names out of ``imports``; the moved ones, or None when nothing moves."""
        moved = [
            leaving
            for each in imports.imports
            if (leaving := self._take_deferred(each)) is not None
        ]
        if not moved:
            return None
        imports.imports = [each for each in imports.imports if each.objects != []]
        _import_type_checking(imports)
        return Imports(imports=sorted(moved, key=lambda each: str(each.module)))

    def _take_deferred(self, each: Import) -> Import | None:
        """Remove the deferred names from a relative import and return them as an import of their own."""
        module = str(each.module)
        if not module.startswith(".") or not each.objects:
            return None
        names = self.deferred.get(module.lstrip("."), ())
        leaving = sorted((o for o in each.objects if o.name in names), key=lambda o: o.name)
        if not leaving:
            return None
        each.objects = [o for o in each.objects if o.name not in names]
        return Import(module=module, objects=leaving)

    @cached_property
    def _any_classes(self) -> set[str]:
        """The classes that stand for ``typing.Any`` (``class_uri: linkml:Any``): never generated, so never imported."""
        sv = self.schemaview
        return {
            self._get_class_python_name(cls.name)
            for cls in sv.all_classes().values()
            if cls.class_uri == ANY_CLASS_URI
        }

    def _inline_as_simple_dict_with_value(self, slot_def: SlotDefinition) -> str | None:
        """The stock value type of a simple-dict slot, as its alias: the stock generator reads it
        from the type directly, not through ``generate_python_range`` (#243)."""
        value: str | None = super()._inline_as_simple_dict_with_value(slot_def)
        return alias_leaf(value) if value else value

    def _clean_injected_classes(self, injected_classes: list[str | type]) -> list[str] | None:
        """None: the only injected class, ``LinkMLMeta``, holds the metadata, which is off (#243)."""
        return None

    def generate_python_range(
        self, slot_range: str, slot_def: SlotDefinition, class_def: ClassDefinition
    ) -> str:
        """The stock range, with a type's library name (``Decimal``, ``Any``) as its alias (#243).

        A class or an enum keeps its name, even one that is also a library name: only this method
        knows which of the two ``Decimal`` is.
        """
        pyrange: str = super().generate_python_range(slot_range, slot_def, class_def)
        sv = self.schemaview
        names_a_class = (
            slot_range in sv.all_classes()
            and pyrange == self._get_class_python_name(slot_range)
            and pyrange not in self._any_classes
        )
        if slot_range in sv.all_enums() or names_a_class:
            return pyrange
        return alias_leaf(pyrange)

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
        if cls.cls.type_alias_value:  # a union_of class
            cls.cls.type_alias_value = alias_heads(cls.cls.type_alias_value)
        return with_validators(cls, sv)

    def after_generate_slot(self, slot: SlotResult, sv: SchemaView) -> SlotResult:
        fields = {name: getattr(slot.attribute, name) for name in PydanticAttribute.model_fields}
        fields["description"] = slot.source.description  # the raw text, as for classes
        fields["range"] = alias_heads(str(slot.attribute.range))  # #243
        if _named_after_slot(slot):
            fields["name"] = make_valid_python_identifier(underscore(slot.source.name))
            fields["alias"] = (
                slot.source.alias
            )  # the stock generator names the field by it and drops it
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


def _import_type_checking(imports: Imports) -> None:
    """Add ``TYPE_CHECKING as _TYPE_CHECKING`` (the alias rule of #243) to the ``typing`` import."""
    guard = ObjectImport(name="TYPE_CHECKING", alias="_TYPE_CHECKING")
    for each in imports.imports:
        if each.module == TYPING and each.objects is not None:
            each.objects = sorted([*each.objects, guard], key=lambda o: o.name)
            return
    imports.imports.append(Import(module=TYPING, objects=[guard]))


def _named_after_slot(slot: SlotResult) -> bool:
    """Whether the field is the slot's own name: the alias is no Python name, or the slot opts in (``field_name: slot``)."""
    opted_in = annotation_text(slot.source, GenerationAnnotation.FIELD_NAME) == FIELD_NAME_SLOT
    return opted_in or not _is_python_name(slot.attribute.alias)


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
    flagged = is_switched_on(slot, GenerationAnnotation.DEFAULT_INSTANCE)
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


def _generator(
    path: Path,
    folder: Path,
    mode: SplitMode,
    root_package: str | None,
    deferred: dict[str, tuple[str, ...]] | None = None,
) -> SplitPydanticGenerator:
    """The generator of one module; ``deferred`` is None outside a cycle, else the names it defers per source module (PD-5)."""
    generator = SplitPydanticGenerator(
        str(path),
        importmap=metamodel_importmap(),
        template_dir=TEMPLATE_DIR,
        metadata_mode=MetadataMode.NONE,
        emit_metadata=False,
        split=True,
        split_mode=mode,
        toolkit=is_toolkit_schema(folder, roots=TOOLKIT_ROOTS),
        folder=folder.resolve(),
        root_package=root_package,
        deferred=deferred or {},
        in_cycle=deferred is not None,
    )
    apply_defaults(generator.schemaview, folder, roots=TOOLKIT_ROOTS)
    return generator


def render(schema_path: Path) -> list[GeneratedFile]:
    """Generate one module per schema module beside ``schema_path`` that its package holds, and an empty package marker.

    A consumer's root module imports every class of the closure, so it is the one place a consumer
    can import any class from; every other module imports only what its classes use. A module
    naming another package than the root's is left to the target that generates it (PD-1). On the
    toolkit's run, a root that shares its folder with such modules (a theme target's) re-exports no
    class of another theme: without classes of its own it writes no module, with some it imports
    only what it uses (PD-5).
    """
    folder = schema_path.parent
    view = load_schema(schema_path)
    root_package = annotation_text(view.schema, GenerationAnnotation.PYTHON_PACKAGE)
    generated = generated_schemas(view, folder)
    shared = is_toolkit_schema(folder, roots=TOOLKIT_ROOTS) and len(generated) < len(
        own_schemas(view, folder)
    )
    wanted = [
        (Path(str(schema.source_file)), schema)
        for schema in generated
        if not (
            shared
            and Path(str(schema.source_file)).resolve() == schema_path.resolve()
            and not schema.classes
        )
    ]
    first: dict[str, tuple[Path, SplitMode, str]] = {}  # pass 1: name -> (schema, mode, text)
    for path, _ in wanted:
        is_root = path.resolve() == schema_path.resolve()
        mode = SplitMode.FULL if is_root and not shared else SplitMode.AUTO
        generator = _generator(path, folder, mode, root_package)
        name = generator.generate_module_import(generator.schema).lstrip(".")
        first[name] = (path, mode, generator.serialize())
    analysis = analyse({name: text for name, (_, _, text) in first.items()})  # PD-1 to PD-3
    deferred = deferred_by_module(analysis)
    modules, classes = _second_pass(
        first, modules_in_cycles(analysis), deferred, folder, root_package
    )
    modules.append(GeneratedFile(name=INIT, text=_package_init(deferred, classes)))
    return sorted(modules, key=lambda module: module.name)


def _second_pass(
    first: dict[str, tuple[Path, SplitMode, str]],
    in_cycles: frozenset[str],
    deferred: dict[str, dict[str, tuple[str, ...]]],
    folder: Path,
    root_package: str | None,
) -> tuple[list[GeneratedFile], dict[str, list[str]]]:
    """The files of pass 1, the modules of a cycle re-rendered with their deferred names (PD-7), and their classes."""
    modules: list[GeneratedFile] = []
    classes: dict[str, list[str]] = {}
    for name, (path, mode, text) in first.items():
        if name in in_cycles:
            generator = _generator(path, folder, mode, root_package, deferred.get(name, {}))
            text = generator.serialize()
            classes[name] = generator.class_names
        modules.append(GeneratedFile(name=f"{name}.py", text=text))
    return modules, classes


def _package_init(
    deferred: dict[str, dict[str, tuple[str, ...]]], classes: dict[str, list[str]]
) -> str:
    """The ``__init__.py`` of a target: empty, or with a cycle the text that binds the deferred names and rebuilds (PD-6)."""
    if not classes:
        return ""
    names = sorted(classes)
    lines = [f'"""{INIT_DOC}"""', ""]
    lines += [f"from . import {name} as _{name}" for name in names]
    lines.append("")
    for name in names:
        bound = sorted(
            (n, source) for source, found in deferred.get(name, {}).items() for n in found
        )
        lines += [f'setattr(_{name}, "{n}", _{source}.{n})' for n, source in bound]
    lines.append("")
    lines += [f"_{name}.{each}.model_rebuild()" for name in names for each in classes[name]]
    return "\n".join(lines) + "\n"
