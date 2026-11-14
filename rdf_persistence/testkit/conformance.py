"""Cross-artefact conformance (PD-27 item 3): generated classes and generated shapes must agree.

A consumer runs it on its own schema: ``assert testkit.conformance.run(schema, cases) == []``.
``schema`` is the root LinkML file of a ``[[tool.rp-generate]]`` entry; the generated package, the
shapes and the JSON-LD context are found from that entry. ``cases`` is a YAML list of
``ConstraintCase`` rows whose instance files sit beside it. A row whose class this schema does not
generate is left to the schema that does, so one cases file can serve several schemas.

An instance file is the YAML of one object, keyed by slot name, as the generated class takes it.
Dates and date-times are quoted, so that YAML keeps them as text. The shape side reads the same
object as RDF the way the router reads a JSON body: ``Documents.expand`` types it by the schema and
reads it with the generated context, which alone decides how values read (an IRI, an enum's
meaning). Internal slots are no public requirement: the shapes make them optional, no body carries
them, and no constraint kind is counted from them.
"""

import importlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml
from linkml_runtime.linkml_model.meta import SlotDefinition
from linkml_runtime.utils.formatutils import camelcase, underscore
from linkml_runtime.utils.schemaview import SchemaView
from pydantic import BaseModel, ValidationError
from pyshacl import validate
from rdflib import Graph

from rdf_persistence.domain.exceptions import InvalidBody
from rdf_persistence.generation.config import python_folder, read_targets
from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import ConstraintCase, ConstraintKind
from rdf_persistence.services.documents import Documents
from rdf_persistence.services.mapper import generated_models_of
from rdf_persistence.services.schema_structure import (
    generation_view,
    holds_owned_part,
    is_internal,
    is_scoped,
    json_name,
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


@dataclass(frozen=True)
class Conformance:
    """A schema with its generated classes, JSON-LD context and shapes, ready to give verdicts.

    ``documents`` read the same folder: it expands a body into RDF and frames RDF back into JSON as
    the router does, so what this suite and the round trip check is the router's own code.
    """

    view: SchemaView
    models: Mapping[str, type[BaseModel]]
    shapes: Graph
    documents: Documents

    @staticmethod
    def of(schema: Path) -> "Conformance":
        """Open ``schema`` and the generated artefacts of the ``[[tool.rp-generate]]`` entry for it.

        Every call reads the files again, so a regeneration between two calls is seen.
        """
        _, package, folder = _generating_target(schema)
        view = generation_view(schema)
        documents = Documents(view, folder)
        models = generated_models_of(importlib.import_module(package)).classes()
        return Conformance(view=view, models=models, shapes=documents.shapes, documents=documents)

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
        refuses is read from ``data`` as it is, since it cannot be built. A body the router would
        refuse before the shapes see it (a key the class has no slot for) is refused here too.
        """
        try:
            built = self.models[camelcase(class_name)].model_validate(data)
            data = built.model_dump(mode="json", by_alias=True, exclude_none=True)
        except ValidationError:
            pass
        try:
            graph = self.documents.expand(
                self.public(class_name, data), self.view.get_class(class_name)
            )
        except InvalidBody:
            return False
        conforms, _, _ = validate(graph, shacl_graph=self.shapes, inference="none")
        return bool(conforms)

    def graph_of(self, model: BaseModel, class_name: str) -> Graph:
        """The RDF of ``model``, its public JSON read the way the router reads a request body."""
        body = model.model_dump(mode="json", by_alias=True, exclude_none=True)
        return self.documents.expand(self.public(class_name, body), self.view.get_class(class_name))

    def slots_of(self, class_name: str) -> dict[str, SlotDefinition]:
        """The slots of ``class_name`` by the keys an object of it is written with: slot name and JSON name."""
        slots = self.view.class_induced_slots(class_name)
        return {**{underscore(s.name): s for s in slots}, **{json_name(s): s for s in slots}}

    def public(self, class_name: str, data: dict) -> dict:
        """``data``, an object of ``class_name`` as JSON, without its internal slots, owned parts too.

        No API body carries them, as the public context leaves them out.
        """
        slots = self.slots_of(class_name)
        return {
            key: self._public_value(slots.get(key), value)
            for key, value in data.items()
            if not (key in slots and is_internal(slots[key]))
        }

    def _public_value(self, slot: SlotDefinition | None, value: object) -> object:
        if isinstance(value, list):
            return [self._public_value(slot, item) for item in value]
        if slot is not None and holds_owned_part(self.view, slot) and isinstance(value, dict):
            return self.public(str(slot.range), value)
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
        keyed = keyed_slots(self.view, cls) or any(
            not is_scoped(key) for key in cls.unique_keys.values()
        )
        return kinds | ({ConstraintKind.UNIQUE_KEYS} if keyed else set())

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
