"""The ``rp-uml2linkml`` command (PD-1, PD-5, PD-22, PD-23): an Enterprise Architect model in, LinkML out.

The flow: parse, read the prefixes file into ``UmlSettings``, read the ``.qea``, convert, write.
Exit 0 written; 1 the model has problems (all printed, sorted, nothing written); 2 the setup is
unusable (arguments, prefixes file, ``.qea`` file or package), one ``rp-uml2linkml: <message>`` line.
"""

import argparse
import functools
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import yaml

from rdf_persistence_generation.generated.rp_generation import (
    CheckProblem,
    UmlModel,
    UmlPrefix,
    UmlSettings,
)
from rdf_persistence_generation.problems import format_problems
from rdf_persistence_generation.uml.convert import convert
from rdf_persistence_generation.uml.qea import QeaUsageError, read_qea
from rdf_persistence_generation.uml.write import write

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
PROG = "rp-uml2linkml"
DEFAULT_ROOT_NAME = "app"
DEFAULT_MIXINS = "Described,Tracked"
DEFAULT_NOT_GENERATED = ("loaded graph",)
LIST_SEPARATOR = ","
REQUIRED_KEYS = ("schema_base", "default_prefix", "version", "prefixes")


class PrefixesFileError(Exception):
    """The prefixes file cannot be used (exit 2); the message is the matrix text."""


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


@functools.cache
def metamodel_prefixes() -> Mapping[str, str]:
    """The prefix name and namespace of every prefix the toolkit's metamodel declares (PD-6).

    Read once with ``linkml_runtime`` (the contract ``works-without-the-generate-extra`` allows it).
    """
    from rdf_persistence.schema.services.schema import PACKAGE_DIR, load_schema
    from rdf_persistence_generation.config import METAMODEL_ROOT

    view = load_schema(PACKAGE_DIR / "model" / METAMODEL_ROOT)
    return {
        prefix.prefix_prefix: prefix.prefix_reference
        for schema in view.all_schema()
        for prefix in schema.prefixes.values()
    }


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
        settings = load_settings(args.prefixes, args)
        model = read_qea(args.qea, args.package, args.exclude_package)
    except PrefixesFileError as error:
        return _usage_error(str(error))
    except QeaUsageError as error:
        return _usage_error(error.message)
    if not isinstance(model, UmlModel):
        return _problems_found(model)
    schemas, report, problems = convert(model, settings, metamodel_prefixes())
    if problems:
        return _problems_found(problems)
    write(schemas, report, args.out, args.root_name)
    return EXIT_OK
