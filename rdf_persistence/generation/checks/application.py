"""The application-class rows of the hard check (app-level-data PD-5): what a class annotated ``database: application`` must be."""

from collections.abc import Iterator

from linkml_runtime.linkml_model.meta import ClassDefinition
from linkml_runtime.utils.schemaview import SchemaView

from rdf_persistence.domain.generated.rp_core import DatabaseKind, RpAnnotation
from rdf_persistence.generation.generated.rp_generation import CheckProblem, HardRule
from rdf_persistence.generation.problems import rule_problem
from rdf_persistence.services.schema_structure import (
    STORED_FILE,
    annotation,
    database_of,
    database_roots,
    is_tenant_root,
    owned_classes,
)

TENANT_ROOT_ROW = "an application class cannot be the tenant root"
OWNED_ROW = "an application class cannot be owned; its owner decides the database"
NOT_ROOT_ROW = "only an aggregate root can be application-level"
STORED_FILE_ROW = (
    "an application class cannot be a stored file: the application space has no bucket"
)
SHARED_IRI_ROW = "an application class cannot share its class IRI with"  # then the other class
MIXIN_ROW = "the database annotation is not inherited through a mixin"
ROWS = (TENANT_ROOT_ROW, OWNED_ROW, NOT_ROOT_ROW, STORED_FILE_ROW, SHARED_IRI_ROW, MIXIN_ROW)


def _application_row(
    view: SchemaView,
    cls: ClassDefinition,
    roots: list[ClassDefinition],
    owned: set[str],
    others: dict[str, str],
) -> str | None:
    """The message of the first PD-5 row that ``cls``, an application class, breaks; None when it breaks none."""
    clash = others.get(view.get_uri(cls, expand=True))
    rows = (
        (is_tenant_root(cls), TENANT_ROOT_ROW),
        (cls.name in owned, OWNED_ROW),
        (cls not in roots, NOT_ROOT_ROW),
        (STORED_FILE in view.class_ancestors(cls.name), STORED_FILE_ROW),
        (bool(clash), f"{SHARED_IRI_ROW} {clash}"),
    )
    return next((message for broken, message in rows if broken), None)


def _is_application(view: SchemaView, cls: ClassDefinition) -> bool:
    """True for a concrete class that lives in the application database; abstract classes are skipped."""
    return not cls.abstract and database_of(view, cls) == DatabaseKind.APPLICATION


def _row_of(
    view: SchemaView,
    cls: ClassDefinition,
    roots: list[ClassDefinition],
    owned: set[str],
    others: dict[str, str],
) -> str | None:
    """The PD-5 message for ``cls``, or None: the mixin row for a mixin, the first broken row for an application class."""
    if cls.mixin:
        carries = annotation(cls, RpAnnotation.DATABASE) == DatabaseKind.APPLICATION.value
        return MIXIN_ROW if carries else None
    return _application_row(view, cls, roots, owned, others) if _is_application(view, cls) else None


def application_problems(
    view: SchemaView, classes: list[ClassDefinition], roots: list[ClassDefinition]
) -> Iterator[CheckProblem]:
    """PD-5: what an application class must be. A mixin's annotation is not inherited, so it is refused."""
    others = {
        view.get_uri(root, expand=True): root.name
        for database in (DatabaseKind.TENANT, DatabaseKind.SYSTEM)
        for root in database_roots(view, database)
    }
    owned = owned_classes(view, classes)
    for cls in classes:
        row = _row_of(view, cls, roots, owned, others)
        if row:
            yield rule_problem(HardRule.ANNOTATION, cls.name, row)
