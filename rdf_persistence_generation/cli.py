"""The ``rp-generate`` command (PD-2, PD-18): regenerate everything a schema makes."""

import argparse
import os
import sys
from pathlib import Path

from rdf_persistence_generation.checks.importable import import_problems, type_problems
from rdf_persistence_generation.config import cli_flags, python_folder, read_targets, toml_key
from rdf_persistence_generation.exceptions import ConfigError
from rdf_persistence_generation.generated.rp_generation import CheckProblem, GenerationTarget
from rdf_persistence_generation.manifest import fix_hint, freshness_report, stale_targets
from rdf_persistence_generation.pipeline import Step, generate
from rdf_persistence_generation.problems import format_problem

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
LINKML_PACKAGE = "linkml"  # the top-level package the `generate` extra installs
EXTRA_HINT = "rp-generate needs LinkML's generators: install rdf-persistence[generate]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rp-generate", description="Generate code from a LinkML schema."
    )
    parser.add_argument(
        "--project", type=Path, default=Path("pyproject.toml"), help="the pyproject.toml to read"
    )
    for flag in cli_flags():
        parser.add_argument(
            flag.option, dest=flag.field, help=f"overrides the `{toml_key(flag.field)}` key"
        )
    parser.add_argument("--check", action="store_true", help="lint and check; write nothing")
    parser.add_argument(
        "--list-python-folders",
        action="store_true",
        help="print the Python output folder of each target, relative to the working folder, and exit",
    )
    return parser


def _pipeline_steps() -> tuple[Step, ...] | None:
    """The pipeline, or ``None`` without the ``generate`` extra (a check then only compares the manifest)."""
    try:
        from rdf_persistence_generation import steps  # lazy: needs the `generate` extra
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] != LINKML_PACKAGE:
            raise
        return None
    return steps.STEPS


def _freshness(targets: list[GenerationTarget], base: Path) -> list[CheckProblem]:
    """The manifest comparison of a check (PD-26), with the command that fixes what it finds."""
    stale = stale_targets(targets, base)
    if not stale:
        return []
    return [
        *freshness_report(stale),
        CheckProblem(message=fix_hint(target for target, _ in stale)),
    ]


def _list_python_folders(targets: list[GenerationTarget], base: Path) -> int:
    """Print each target's Python folder, relative to the working folder; a make target reads them."""
    for target in targets:
        print(os.path.relpath(base / python_folder(target)))
    return EXIT_OK


def _run(
    args: argparse.Namespace,
    targets: list[GenerationTarget],
    base: Path,
    pipeline_steps: tuple[Step, ...] | None,
) -> int:
    """Generate (or check) the targets and report; the exit code is 0 or 1."""
    problems = generate(targets, base, pipeline_steps or (), check=args.check)
    if not problems:  # what was written imports, and in a check type-checks (#242)
        problems += import_problems(targets, base)
        problems += type_problems(targets, base) if args.check else []
    if args.check:
        problems += _freshness(targets, base)
    for problem in problems:
        print(format_problem(problem), file=sys.stderr)
    if problems:
        return EXIT_FAILED
    print(
        f"rp-generate: {'checked' if args.check else 'generated'} {len(targets)} target(s), no problems"
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Run ``rp-generate``; return the exit code: 0 done, 1 problems found, 2 unusable setup."""
    args = build_parser().parse_args(argv)
    # the listing writes nothing, so it is decided before the pipeline needs the `generate` extra
    pipeline_steps = None if args.list_python_folders else _pipeline_steps()
    if pipeline_steps is None and not (args.check or args.list_python_folders):
        print(EXTRA_HINT, file=sys.stderr)
        return EXIT_USAGE
    try:
        targets = read_targets(args.project, args)
    except ConfigError as error:
        print(f"rp-generate: {error}", file=sys.stderr)
        return EXIT_USAGE
    base = args.project.resolve().parent
    if args.list_python_folders:
        return _list_python_folders(targets, base)
    return _run(args, targets, base, pipeline_steps)
