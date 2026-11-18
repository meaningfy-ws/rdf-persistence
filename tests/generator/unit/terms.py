"""The terms of a generated artefact read as data, so a test never searches its text."""

import json
from collections.abc import Iterator
from pathlib import Path

from rdflib import Graph

PARSED = {
    ".ttl",
    ".jsonld",
    ".json",
}  # Turtle and JSON(-LD) are data; Python and TypeScript are text


def _json_strings(value: object) -> Iterator[str]:
    """Every key and every string value of a parsed JSON document."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _json_strings(item)
    elif isinstance(value, str):
        yield value


def terms_of(path: Path) -> list[str]:
    """The RDF terms of a Turtle file, the keys and strings of a JSON(-LD) one, else the whole text."""
    if path.suffix == ".ttl":
        return [str(term) for triple in Graph().parse(path, format="turtle") for term in triple]
    if path.suffix in PARSED:
        return list(_json_strings(json.loads(path.read_text())))
    return [path.read_text()]
