"""The Jinja environment of the toolkit's own templates (PD-25). Needs the ``generate`` extra's Jinja2."""

from jinja2 import Environment, FileSystemLoader

from rdf_persistence.generation.manifest import TEMPLATES_DIR


def environment(folder: str) -> Environment:
    """An environment over ``templates/<folder>``: every line the template writes is one it shows."""
    return Environment(
        loader=FileSystemLoader(TEMPLATES_DIR / folder),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
