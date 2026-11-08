"""The ``rp-generate`` command (PD-2, PD-18): regenerate everything a schema makes."""

import argparse
import os
import sys
from pathlib import Path

from rdf_persistence.generation.config import cli_flags, python_folder, read_targets
from rdf_persistence.generation.exceptions import ConfigError
from rdf_persistence.generation.generated.rp_generation import CheckProblem, GenerationTarget
from rdf_persistence.generation.manifest import fix_hint, stale_targets
from rdf_persistence.generation.pipeline import Step, generate
from rdf_persistence.generation.problems import format_problem

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
EXTRA_HINT = "rp-generate needs LinkML's generators: install rdf-persistence[generate]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rp-generate", description="Generate code from a LinkML schema."
    )
    parser.add_argument(
        "--project", type=Path, default=Path("pyproject.toml"), help="the pyproject.toml to read"
    )
    for flag in cli_flags():
        parser.add_argument(flag.option, dest=flag.field, help=f"overrides the `{flag.field}` key")
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
        from rdf_persistence.generation import steps  # lazy: needs the `generate` extra
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] != "linkml":
            raise
        return None
    return steps.STEPS


def _freshness(targets: list[GenerationTarget], base: Path) -> list[CheckProblem]:
    """The manifest comparison of a check (PD-26), with the command that fixes what it finds."""
    stale = stale_targets(targets, base)
    if not stale:
        return []
    found = [problem for _, problems in stale for problem in problems]
    return [*found, CheckProblem(message=fix_hint(target for target, _ in stale))]


def _list_python_folders(targets: list[GenerationTarget], base: Path) -> int:
    """Print each target's Python folder, relative to the working folder; a make target reads them."""
    for target in targets:
        print(os.path.relpath(base / python_folder(target)))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    """Run ``rp-generate``; return the exit code: 0 done, 1 problems found, 2 unusable setup."""
    args = build_parser().parse_args(argv)
    pipeline_steps = _pipeline_steps()
    if pipeline_steps is None and not args.check:
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
    problems = generate(targets, base, pipeline_steps or (), check=args.check)
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
