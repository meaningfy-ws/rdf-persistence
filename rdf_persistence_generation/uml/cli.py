"""The ``rp-uml2linkml`` command (PD-1, PD-5, PD-22, PD-23): an Enterprise Architect model in, LinkML out.

The flow: parse, read the prefixes file into ``UmlSettings``, read the ``.qea``, convert, write.
Exit 0 written; 1 the model has problems (all printed, sorted, nothing written); 2 the setup is
unusable (arguments, prefixes file, ``.qea`` file or package) or ``--out`` cannot be written, one ``rp-uml2linkml: <message>`` line.
"""

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml
from linkml_runtime.utils.metamodelcore import NCName
from linkml_runtime.utils.uri_validator import validate_uri

from rdf_persistence_generation.exceptions import (
    OutputError,
    PrefixesFileError,
    QeaUsageError,
    StagedFileRefused,
    UsageError,
)
from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    UmlModel,
    UmlPrefix,
    UmlSettings,
)
from rdf_persistence_generation.problems import format_problems
from rdf_persistence_generation.uml.convert import convert
from rdf_persistence_generation.uml.qea import read_qea
from rdf_persistence_generation.uml.toolkit import load_toolkit
from rdf_persistence_generation.uml.write import write

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
PROG = "rp-uml2linkml"
DEFAULT_ROOT_NAME = "app"
DEFAULT_MIXINS = "Described,Tracked"
DEFAULT_NOT_GENERATED = ("loaded graph",)
LIST_SEPARATOR = ","
REQUIRED_KEYS = ("schema_base", "default_prefix", "version", "prefixes")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG, description="Convert an Enterprise Architect .qea model to LinkML schemas."
    )
    parser.add_argument("qea", type=Path, help="the Enterprise Architect .qea (SQLite) file")
    parser.add_argument("--package", required=True, help="the package to convert: a name or a path")
    parser.add_argument("--prefixes", required=True, type=Path, help="the prefixes YAML file")
    parser.add_argument("--out", required=True, type=Path, help="the folder to write into")
    parser.add_argument(
        "--root-name", default=DEFAULT_ROOT_NAME, help="the root schema's name (default: app)"
    )
    parser.add_argument(
        "--exclude-package",
        action="append",
        default=[],
        metavar="PATH",
        help="a package path to leave out with its subtree; repeatable",
    )
    parser.add_argument(
        "--default-mixins",
        default=DEFAULT_MIXINS,
        help="the mixins of a root class and its labelled parts, comma separated",
    )
    parser.add_argument(
        "--not-generated",
        action="append",
        metavar="STEREOTYPE",
        help="a stereotype whose classes are not generated; repeatable (default: loaded graph)",
    )
    return parser


def _read_mapping(path: Path) -> Mapping[str, object]:
    try:
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PrefixesFileError(f"{path}: cannot be read: {error}") from error
    if not isinstance(content, Mapping):
        raise PrefixesFileError(f"{path}: not a mapping")
    return content


def _is_ncname(text: str) -> bool:
    return bool(text) and NCName.is_valid(text)


def _is_absolute_iri(text: str) -> bool:
    return bool(validate_uri(text))


def _check_values(
    path: Path, content: Mapping[str, object], prefixes: Mapping[str, object]
) -> None:
    """Each value the file gives must be usable in the output (D-29 C-2), else a usage error."""
    schema_base = str(content["schema_base"])
    if not _is_absolute_iri(schema_base):
        raise PrefixesFileError(f"{path}: schema_base {schema_base} is not an absolute IRI")
    for name, namespace in prefixes.items():
        if not _is_ncname(str(name)):
            raise PrefixesFileError(f"{path}: prefix {name} is not an NCName")
        if not _is_absolute_iri(str(namespace)):
            raise PrefixesFileError(
                f"{path}: namespace {namespace} of prefix {name} is not an absolute IRI"
            )
    default_prefix = str(content["default_prefix"])
    if default_prefix not in {str(name) for name in prefixes}:
        raise PrefixesFileError(f"{path}: default_prefix {default_prefix} is not a key of prefixes")


def _check_root_name(root_name: str) -> None:
    if not _is_ncname(root_name):
        raise UsageError(f"--root-name {root_name} is not an NCName")


def load_settings(path: Path, args: argparse.Namespace) -> UmlSettings:
    """The prefixes file (PD-5) and the command line as ``UmlSettings``.

    Raises:
        PrefixesFileError: The file is unreadable, not a mapping, or lacks a key.
    """
    content = _read_mapping(path)
    for key in REQUIRED_KEYS:
        if key not in content:
            raise PrefixesFileError(f"{path}: missing {key}")
    prefixes = content["prefixes"]
    if not isinstance(prefixes, Mapping):
        raise PrefixesFileError(f"{path}: prefixes is not a mapping")
    _check_values(path, content, prefixes)
    return UmlSettings(
        schema_base=str(content["schema_base"]),
        default_prefix=str(content["default_prefix"]),
        schema_version=str(content["version"]),
        prefixes=[
            UmlPrefix(prefix_name=str(name), namespace=str(namespace))
            for name, namespace in prefixes.items()
        ],
        subtree_package=args.package,
        root_name=args.root_name,
        exclude_packages=list(args.exclude_package),
        default_mixins=[item for item in args.default_mixins.split(LIST_SEPARATOR) if item],
        not_generated_stereotypes=list(args.not_generated or DEFAULT_NOT_GENERATED),
    )


def _usage_error(message: str) -> int:
    print(f"{PROG}: {message}", file=sys.stderr)
    return EXIT_USAGE


def _problems_found(problems: Sequence[CheckProblem]) -> int:
    print(format_problems(problems), file=sys.stderr)
    return EXIT_FAILED


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``rp-uml2linkml``; return the exit code: 0 written, 1 model problems, 2 unusable setup."""
    args = build_parser().parse_args(argv)
    try:
        _check_root_name(args.root_name)
        settings = load_settings(args.prefixes, args)
        model = read_qea(args.qea, args.package, args.exclude_package)
    except UsageError as error:
        return _usage_error(str(error))
    except QeaUsageError as error:
        return _usage_error(error.message)
    if not isinstance(model, UmlModel):
        return _problems_found(model)
    schemas, report, problems, files = convert(model, settings, load_toolkit())
    if problems:
        return _problems_found(problems)
    try:
        write(schemas, report, args.out, args.root_name, files)
    except StagedFileRefused as error:
        print(f"{PROG}: {error}", file=sys.stderr)
        return EXIT_FAILED
    except OutputError as error:
        return _usage_error(f"cannot write {error.path}: {error.reason}")
    return EXIT_OK
