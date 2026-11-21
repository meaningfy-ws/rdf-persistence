"""PD-6: the one way the converter writes a library model as a YAML file.

The roles file and each workflow file are the library's own models dumped as JSON-compatible data,
with the defaults left out (``comment_required`` only when true), in the fields' own order, so a
field the library adds is written without an edit here.
"""

import yaml
from pydantic import BaseModel

DUMP_WIDTH = 100


def yaml_text(data: BaseModel | list[BaseModel]) -> str:
    """The model, or the list of models, as block-style YAML in the order of its fields."""
    items = [each.model_dump(mode="json", exclude_defaults=True) for each in _listed(data)]
    text: str = yaml.safe_dump(
        items if isinstance(data, list) else items[0],
        sort_keys=False,
        allow_unicode=True,
        width=DUMP_WIDTH,
    )
    return text


def _listed(data: BaseModel | list[BaseModel]) -> list[BaseModel]:
    return data if isinstance(data, list) else [data]
