"""The errors of the generation toolchain. Imports nothing from LinkML, so any module may raise or catch them."""

from collections.abc import Sequence


class ConfigError(Exception):
    """The configuration is unusable: a usage error, exit code 2."""


class StepError(Exception):
    """A step found problems; each is one line to show the developer."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class SchemaGenerationError(Exception):
    """The schema asks for something the generators cannot render; the message names the element.

    Extensions raise it for a schema fault. Any other exception from a generator is a bug in the
    toolchain and surfaces with its traceback.
    """
