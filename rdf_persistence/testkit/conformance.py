"""Cross-artefact conformance (PD-27 item 3): generated classes and generated shapes must agree.

A consumer runs it on its own schema: ``assert testkit.conformance.run(schema, cases) == []``.
``schema`` is the root LinkML file of a ``[[tool.rp-generate]]`` entry; the generated package, the
shapes and the JSON-LD context are found from that entry. ``cases`` is a YAML list of
``ConstraintCase`` rows whose instance files sit beside it. A row whose class this schema does not
generate is left to the schema that does, so one cases file can serve several schemas.

An instance file is the YAML of one object, keyed by slot name, as the generated class takes it.
Dates and date-times are quoted, so that YAML keeps them as text. The shape side reads the same
object as RDF: the instance is made a JSON-LD node (``jsonld_node``) and expanded with the
generated context, which alone decides how values read (an IRI, an enum's meaning). Internal slots are
no public requirement: the shapes make them optional, so no constraint kind is counted from them.
"""

import importlib
import json
import pkgutil
from dataclasses import dataclass
from pathlib import Path

import yaml
from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel, ValidationError
from pyld import jsonld
from pyshacl import validate
from rdflib import Graph

from rdf_persistence.generation.config import python_folder, read_targets
from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import ConstraintCase, ConstraintKind
from rdf_persistence.generation.outputs import CONTEXT_FILE, SHAPES_FILE
from rdf_persistence.services.schema_structure import (
    generation_view,
    is_internal,
    is_owned,
    keyed_slots,
)


def load_cases(path: Path) -> list[ConstraintCase]:
    """The rows of the cases file at ``path``, their instance paths made absolute."""
    rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    cases = [ConstraintCase.model_validate(row) for row in rows]
    return [
        case.model_copy(
            update={
                "valid": [str(path.parent / p) for p in case.valid or []],
                "invalid": [str(path.parent / p) for p in case.invalid or []],
            }
        )
        for case in cases
    ]


def _generating_target(schema: Path) -> tuple[Path, str, Path]:
    """The folder of the pyproject, the package and the Python folder of the entry generating ``schema``."""
    wanted = schema.resolve()
    for folder in wanted.parents:
        try:
            targets = read_targets(folder / "pyproject.toml")
        except ConfigError:
            continue
        for target in targets:
            if (folder / target.schema_file).resolve() == wanted:
                return folder, target.package, folder / python_folder(target)
    raise LookupError(f"no [[tool.rp-generate]] entry of a pyproject.toml generates {schema}")


def _generated_models(package: str, folder: Path) -> dict[str, type[BaseModel]]:
    models: dict[str, type[BaseModel]] = {}
    for info in pkgutil.iter_modules([str(folder)]):
        module = importlib.import_module(f"{package}.{info.name}")
        models |= {
            name: member
            for name, member in vars(module).items()
            if isinstance(member, type)
            and issubclass(member, BaseModel)
            and member.__module__ == module.__name__
        }
    return models


@dataclass(frozen=True)
class Conformance:
    """A schema with its generated classes, JSON-LD context and shapes, ready to give verdicts.

    ``folder`` is the Python folder of the entry that generated them, where the frames are too.
    """

    view: SchemaView
    models: dict[str, type[BaseModel]]
    context: dict
    shapes: Graph
    folder: Path

    @staticmethod
    def of(schema: Path) -> "Conformance":
        """Open ``schema`` and the generated artefacts of the ``[[tool.rp-generate]]`` entry for it.

        Every call reads the files again, so a regeneration between two calls is seen.
        """
        _, package, folder = _generating_target(schema)
        context = json.loads((folder / CONTEXT_FILE).read_text(encoding="utf-8"))["@context"]
        return Conformance(
            view=generation_view(schema),
            models=_generated_models(package, folder),
            context=context,
            shapes=Graph().parse(folder / SHAPES_FILE),
            folder=folder,
        )

    def class_names(self) -> set[str]:
        """The schema classes this entry generates."""
        return {name for name in self.view.all_classes() if camelcase(name) in self.models}

    def class_accepts(self, class_name: str, data: dict) -> bool:
        """Whether the generated class builds an object from ``data``."""
        try:
            self.models[camelcase(class_name)].model_validate(data)
        except ValidationError:
            return False
        return True

    def shapes_accept(self, class_name: str, data: dict) -> bool:
        """Whether the generated shapes accept the RDF of ``data``, an instance of ``class_name``.

        An object the class builds is read back through its JSON (what the API would send); one it
        refuses is read from ``data`` as it is, since it cannot be built.
        """
        try:
            built = self.models[camelcase(class_name)].model_validate(data)
            data = built.model_dump(mode="json", by_alias=True, exclude_none=True)
        except ValidationError:
            pass
        nquads = jsonld.to_rdf(
            {"@context": self.context, **self.jsonld_node(class_name, data)},
            {"format": "application/n-quads"},
        )
        graph = Graph().parse(data=nquads, format="nt")
        conforms, _, _ = validate(graph, shacl_graph=self.shapes, inference="none")
        return bool(conforms)

    def jsonld_node(self, class_name: str, data: dict) -> dict:
        """``data`` as a JSON-LD node of ``class_name``, typed, owned parts too (a frame selects by type).

        Only the types are added: the values are read by the generated context as they are. Internal
        slots are left out, as the public context leaves them out: an API body never carries them.
        """
        slots = {underscore(s.name): s for s in self.view.class_induced_slots(class_name)}
        node: dict = {"@type": camelcase(class_name)}
        for key, value in data.items():
            slot = slots.get(key)
            if slot is None:
                node[key] = value
            elif not is_internal(slot):
                node[key] = self._typed_parts(slot, value)
        return node

    def _typed_parts(self, slot: SlotDefinition, value: object) -> object:
        if isinstance(value, list):
            return [self._typed_parts(slot, item) for item in value]
        if isinstance(value, dict) and is_owned(slot):
            return self.jsonld_node(slot.range, value)
        return value

    def used_kinds(self) -> set[ConstraintKind]:
        """The constraint kinds the generated classes of the schema use, read from ``SchemaView``."""
        kinds = {ConstraintKind.CLOSED} if self.models else set()
        for name in self.class_names():
            kinds |= self.class_kinds(name)
            for slot in self.view.class_induced_slots(name):
                if not is_internal(slot):  # the shapes make it optional (PD-24)
                    kinds |= self._slot_kinds(slot)
        return kinds

    def class_kinds(self, name: str) -> set[ConstraintKind]:
        """The kinds of the rules ``name`` declares or holds through a keyed slot."""
        cls = self.view.get_class(name)
        kinds = {kind for kind, found in _CLASS_KINDS if getattr(cls, found)}
        return kinds | ({ConstraintKind.UNIQUE_KEYS} if keyed_slots(self.view, cls) else set())

    def _slot_kinds(self, slot: SlotDefinition) -> set[ConstraintKind]:
        kinds = {kind for kind, found in _SLOT_KINDS if getattr(slot, found) is not None}
        if slot.range in self.view.all_types():
            kinds.add(ConstraintKind.RANGE_TYPE)
        if slot.range in self.view.all_enums():
            kinds.add(ConstraintKind.RANGE_ENUM)
        return kinds | ({ConstraintKind.IDENTIFIER} if slot.identifier else set())


_CLASS_KINDS = (
    (ConstraintKind.EXACTLY_ONE_OF, "exactly_one_of"),
    (ConstraintKind.ANY_OF, "any_of"),
    (ConstraintKind.UNIQUE_KEYS, "unique_keys"),
)
_SLOT_KINDS = (
    (ConstraintKind.REQUIRED, "required"),
    (ConstraintKind.CARDINALITY, "minimum_cardinality"),
    (ConstraintKind.CARDINALITY, "maximum_cardinality"),
    (ConstraintKind.PATTERN, "pattern"),
    (ConstraintKind.VALUE_BOUNDS, "minimum_value"),
    (ConstraintKind.VALUE_BOUNDS, "maximum_value"),
)


def used_kinds(schema: Path) -> set[ConstraintKind]:
    """The constraint kinds the classes generated for ``schema`` use."""
    return Conformance.of(schema).used_kinds()


def generated_classes(schema: Path) -> set[str]:
    """The names of the schema classes generated for ``schema``'s entry."""
    return Conformance.of(schema).class_names()


def _word(accepted: bool) -> str:
    return "accept" if accepted else "refuse"


def _instance(path: str) -> dict:
    instance: dict = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return instance


def verdict_problems(conformance: Conformance, cases: list[ConstraintCase]) -> list[str]:
    """Every instance on which class and shape disagree, or both contradict the row; empty when none."""
    problems: list[str] = []
    for case in cases:
        if camelcase(case.class_name) not in conformance.models:
            continue
        for expected, files in ((True, case.valid), (False, case.invalid)):
            for file in files or []:
                data = _instance(file)
                by_class = conformance.class_accepts(case.class_name, data)
                by_shape = conformance.shapes_accept(case.class_name, data)
                label = f"{case.kind} {case.class_name} {Path(file).name}"
                if by_class != by_shape:
                    problems.append(
                        f"{label}: classes and shapes disagree "
                        f"(class {_word(by_class)}s, shapes {_word(by_shape)}s)"
                    )
                elif by_class != expected:
                    problems.append(
                        f"{label}: class and shapes both {_word(by_class)}, "
                        f"the row expects them to {_word(expected)}"
                    )
    return problems


def coverage_problems(conformance: Conformance, cases: list[ConstraintCase]) -> list[str]:
    """The kinds the schema uses that no row covers, as one problem naming them; empty when covered."""
    covered = {
        ConstraintKind(case.kind)
        for case in cases
        if camelcase(case.class_name) in conformance.models
    }
    missing = sorted(k.value for k in conformance.used_kinds() - covered)
    if not missing:
        return []
    return [f"no case for the constraint kinds the schema uses: {', '.join(missing)}"]


def run(schema: Path, cases: Path) -> list[str]:
    """All problems of the conformance suite for ``schema`` and the cases file; empty when it passes."""
    rows, conformance = load_cases(cases), Conformance.of(schema)
    return verdict_problems(conformance, rows) + coverage_problems(conformance, rows)
