"""The errors of the generation toolchain. Imports nothing from the LinkML generators, so any module may raise or catch them."""

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path

from rdf_persistence.schema.services.schema_structure import UnsupportedRuleError
from rdf_persistence_generation.generated.rp_generation import CheckProblem


class ConfigError(Exception):
    """The configuration is unusable: a usage error, exit code 2."""


class StepError(Exception):
    """A step found problems."""

    def __init__(self, problems: Sequence[CheckProblem]) -> None:
        super().__init__("; ".join(problem.message for problem in problems))
        self.problems = list(problems)


class SchemaGenerationError(Exception):
    """The schema asks for something the generators cannot render; the message names the element.

    Extensions raise it for a schema fault. Any other exception from a generator is a bug in the
    toolchain and surfaces with its traceback.
    """


@contextmanager
def refusing_unsupported_rules() -> Iterator[None]:
    """Within it, a rule the schema declares in an unsupported form is a ``SchemaGenerationError``."""
    try:
        yield
    except UnsupportedRuleError as error:
        raise SchemaGenerationError(str(error)) from error


class UsageError(Exception):
    """The ``rp-uml2linkml`` setup cannot be used (exit 2); the message is the matrix text (PD-7)."""


class PrefixesFileError(UsageError):
    """The prefixes file cannot be used (exit 2); the message is the matrix text."""


class QeaUsageError(Exception):
    """The file or the ``--package`` cannot be used (exit 2); ``message`` is the matrix text."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class StagedFileRefused(RuntimeError):  # noqa: N818 (the name PD-4 decides)
    """The library's loader refuses a staged file (PD-4): a rule of the conversion missed it."""


class OutputError(Exception):
    """The output folder cannot be written (``path``); ``reason`` says why, in the matrix text."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason
