"""What the hard-check and boundary-check tests share: reading a schema's problems, two planted schemas."""

from pathlib import Path

from rdf_persistence.schema.services.schema import load_schema
from rdf_persistence_generation.checks import boundary
from rdf_persistence_generation.checks.hard import hard_problems
from rdf_persistence_generation.problems import format_problem

from .conftest import ROOT_SCHEMA


def hard_check_problems(root: Path) -> list[str]:
    """The hard check's problems of the schema at ``root``, one formatted line each."""
    return [format_problem(p) for p in hard_problems(load_schema(root), root.parent)]


def boundary_problems(root: Path) -> list[str]:
    """The boundary check's problems of the schema at ``root``, one formatted line each."""
    return [format_problem(p) for p in boundary.boundary_problems(load_schema(root), root.parent)]


DEFAULT_INSTANCE_SCHEMA = """
id: https://example.org/ns/groups
name: groups
title: Groups
description: A settings class that holds a group of its own.
prefixes: {{g: "https://example.org/ns/g#", linkml: "https://w3id.org/linkml/"}}
default_prefix: g
default_range: string
imports: [linkml:types]
classes:
  Group:
    title: Group
    description: A group of values.
    slots: [size, name]
    slot_usage:
      size: {{ifabsent: "int(3)"}}
      name: {{required: {name_required}{name_default}}}
  Holder:
    title: Holder
    description: Holds a group.
    slots: [group, label]
slots:
  size:
    title: Size
    description: A count.
    range: integer
  name:
    title: Name
    description: A name.
  group:
    title: Group slot
    description: The group.
    range: Group
    annotations:
      default_instance: 'true'
  label:
    title: Label
    description: A label.
    annotations:
      default_instance: 'true'
"""

API_MODULE = """id: https://example.org/ns/library/api
name: api
title: API module
description: The request and response shapes of the library's own routes.
prefixes:
  lib: https://example.org/ns/library#
  linkml: https://w3id.org/linkml/
default_prefix: lib
default_range: string
imports:
  - linkml:types
annotations:
  module_kind: {kind}

classes:
  Account:
    title: Account
    description: What a route answers about an account; never stored.
    class_uri: lib:Account
    attributes:
      account_id:
        title: Account id
        description: The identifier of the account.
        identifier: true
      active:
        title: Active
        description: Whether the account may sign in.
        range: boolean
"""


def add_api_module(toy: Path, kind: str) -> Path:
    """Write ``api.yaml`` of the given kind into the toy and import it from the root schema."""
    (toy / "api.yaml").write_text(API_MODULE.format(kind=kind), encoding="utf-8")
    root = toy / ROOT_SCHEMA
    text = root.read_text(encoding="utf-8")
    root.write_text(
        text.replace("  - library_access\n", "  - library_access\n  - api\n", 1), encoding="utf-8"
    )
    return root
