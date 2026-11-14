"""Which database a class lives in (PD-4): ``database_of``, ``served_roots``, ``root_class_iris``, ``Listings``."""

from pathlib import Path

import pytest
from linkml_runtime.utils.schemaview import SchemaView
from rdflib import URIRef

from rdf_persistence.domain.generated.rp_core import DatabaseKind
from rdf_persistence.services.listing import Listings
from rdf_persistence.services.schema import load_schema
from rdf_persistence.services.schema_structure import (
    database_of,
    root_class_iris,
    served_roots,
)

APPLICATION = DatabaseKind.APPLICATION
TENANT = DatabaseKind.TENANT
SYSTEM = DatabaseKind.SYSTEM
NS = "https://example.org/ns/dbs#"

HEAD = """
id: https://example.org/ns/dbs
name: dbs
title: Databases
description: Roots in the three databases.
prefixes: {d: "https://example.org/ns/dbs#", linkml: "https://w3id.org/linkml/"}
default_prefix: d
default_range: string
imports: [linkml:types]
classes:
  AggregateRoot:
    abstract: true
  Mixin:
    mixin: true
    annotations: {database: application}
"""


def _root(name: str, path: str, database: str | None, parent: str = "AggregateRoot") -> str:
    tag = f"      database: {database}\n" if database else ""
    return f"  {name}:\n    is_a: {parent}\n    annotations:\n      rp_path: {path}\n{tag}"


SCHEMA = (
    HEAD
    + _root("Book", "books", None)
    + _root("Shelf", "shelves", "tenant")
    + _root("Tpl", "templates", "application")
    + _root("Access", "accesses", "system")
    + _root("ReportTpl", "reports", None, parent="Tpl")
    + _root("LostAccess", "lost", None, parent="Access")
    + "  Mixed:\n    is_a: Book\n    mixins: [Mixin]\n    annotations: {rp_path: mixed}\n"
)


@pytest.fixture
def view(tmp_path: Path) -> SchemaView:
    path = tmp_path / "dbs.yaml"
    path.write_text(SCHEMA, encoding="utf-8")
    return load_schema(path)


def _names(view: SchemaView, database: DatabaseKind | None = None) -> set[str]:
    roots = served_roots(view) if database is None else served_roots(view, database)
    return {root.name for root in roots}


def test_the_default_database_serves_the_tenant_roots_only(view: SchemaView) -> None:
    served = _names(view)
    assert {"Book", "Shelf"} <= served, "unannotated and tenant roots are served by default"
    assert not served & {"Tpl", "Access"}, "application and system roots are not tenant roots"


def test_the_application_database_serves_the_application_roots(view: SchemaView) -> None:
    assert {"Tpl", "ReportTpl"} == _names(view, APPLICATION), "exactly the application roots"


def test_the_system_database_serves_the_system_roots(view: SchemaView) -> None:
    assert {"Access", "LostAccess"} == _names(view, SYSTEM), "exactly the system roots"


def test_a_root_is_served_by_one_database_only(view: SchemaView) -> None:
    served = [_names(view, kind) for kind in DatabaseKind]
    assert sum(map(len, served)) == len(set().union(*served)), "no root in two databases"


def test_root_class_iris_of_the_application(view: SchemaView) -> None:
    assert root_class_iris(view, APPLICATION) == frozenset(
        {URIRef(NS + "Tpl"), URIRef(NS + "ReportTpl")}
    ), "the class IRIs of the application roots"


def test_root_class_iris_of_the_tenant_leave_the_application_out(view: SchemaView) -> None:
    iris = root_class_iris(view, TENANT)
    assert URIRef(NS + "Book") in iris and URIRef(NS + "Shelf") in iris, "tenant roots are in"
    assert not iris & {URIRef(NS + "Tpl"), URIRef(NS + "Access")}, "other databases' roots are out"


def test_root_class_iris_are_a_frozenset(view: SchemaView) -> None:
    assert isinstance(root_class_iris(view, TENANT), frozenset), (
        "hashable, so a session can keep it"
    )


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Book", TENANT),
        ("Shelf", TENANT),
        ("Tpl", APPLICATION),
        ("Access", SYSTEM),
        ("ReportTpl", APPLICATION),
        ("LostAccess", SYSTEM),
        ("Mixed", TENANT),
    ],
    ids=lambda v: str(getattr(v, "value", v)),
)
def test_database_of_follows_is_a_and_never_a_mixin(
    view: SchemaView, name: str, expected: DatabaseKind
) -> None:
    assert database_of(view, view.get_class(name)) == expected, name


def test_a_subclass_of_an_application_class_is_listed_for_the_application(view: SchemaView) -> None:
    assert Listings(view, APPLICATION).served_root("ReportTpl").name == "ReportTpl"


@pytest.mark.parametrize(
    ("database", "name"),
    [(None, "Tpl"), (APPLICATION, "Book")],
    ids=["tenant-refuses-application", "application-refuses-tenant"],
)
def test_listings_refuse_a_class_of_the_other_database(
    view: SchemaView, database: DatabaseKind | None, name: str
) -> None:
    listings = Listings(view) if database is None else Listings(view, database)
    with pytest.raises(ValueError, match=name):
        listings.served_root(name)


def test_listings_serve_a_tenant_class_by_default(view: SchemaView) -> None:
    assert Listings(view).served_root("Book").name == "Book", "today's behaviour"
