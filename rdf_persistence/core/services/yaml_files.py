"""Reading a YAML file into a mapping, and telling a validation error, for the loaders of files (PD-22).

The workflow and the migration loaders read one file each, into a generated model. What they share
is here: the refusals of a file that cannot be read as a mapping, a key given twice, and a bounded
text for a validation error. Each caller raises its own error type with its own noun.
"""

from collections.abc import Hashable
from pathlib import Path

import yaml
from pydantic import ValidationError

SHOWN = 200  # how much of a rejected input an error text echoes
MOST_PROBLEMS = 5  # how many validation errors one message lists


def shown(value: object) -> str:
    """The text of ``value`` for an error message, cut to ``SHOWN`` characters."""
    text = repr(value)
    return text if len(text) <= SHOWN else f"{text[:SHOWN]}..."


class _UniqueKeyLoader(yaml.SafeLoader):
    """A safe loader that refuses a mapping key given twice: a reviewer reads what runs (PD-21)."""

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict:
        seen: set[Hashable] = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, Hashable):
                continue  # the parent refuses it
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"found the key {key!r} twice", key_node.start_mark
                )
            seen.add(key)
        mapping: dict = super().construct_mapping(node, deep)
        return mapping


def read_mapping(path: Path, noun: str, error_type: type[Exception]) -> dict:
    """The mapping the YAML file ``path`` holds.

    Raises:
        error_type: The file cannot be read, is not UTF-8, is not YAML, is nested too deeply, is
            not a mapping, or gives a key twice; the message names the file and says ``noun``.
    """
    try:
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)
    except OSError as error:
        raise error_type(f"cannot read the {noun} {path}: {error}") from error
    except UnicodeDecodeError as error:
        raise error_type(f"{path} is not UTF-8 text: {str(error)[:SHOWN]}") from error
    except yaml.YAMLError as error:
        raise error_type(f"{path} is not valid YAML: {str(error)[:SHOWN]}") from error
    except RecursionError as error:
        raise error_type(f"{path} is nested too deeply to read") from error
    if not isinstance(data, dict):
        raise error_type(f"{path} must hold one {noun}, a mapping")
    return data


def problems_of(error: ValidationError, *, echo_input: bool = False) -> str:
    """The first ``MOST_PROBLEMS`` errors of a validation, each cut to ``SHOWN``, then ``+N more``.

    With ``echo_input`` each error also says what the file gave (``(got ...)``, cut to ``SHOWN``).
    """
    found = error.errors()
    lines = [
        f"{'.'.join(map(str, e['loc']))[:SHOWN]}: {str(e['msg'])[:SHOWN]}"
        + (f" (got {shown(e['input'])})" if echo_input else "")
        for e in found[:MOST_PROBLEMS]
    ]
    if len(found) > MOST_PROBLEMS:
        lines.append(f"+{len(found) - MOST_PROBLEMS} more")
    return "; ".join(lines)
