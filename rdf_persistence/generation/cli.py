"""The ``rp-generate`` command (PD-2, PD-18): regenerate everything a schema makes."""

import argparse
import sys
from pathlib import Path

from rdf_persistence.generation.config import FLAGS, ConfigError, read_targets
from rdf_persistence.generation.pipeline import generate

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2
EXTRA_HINT = "rp-generate needs LinkML's generators: install rdf-persistence[generate]"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rp-generate", description="Generate code from a LinkML schema."
    )
    parser.add_argument(
        "--project", type=Path, default=Path("pyproject.toml"), help="the pyproject.toml to read"
    )
    for flag in FLAGS:
        parser.add_argument(flag.option, dest=flag.field, help=f"overrides the `{flag.field}` key")
    parser.add_argument("--check", action="store_true", help="lint and check; write nothing")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run ``rp-generate``; return the exit code: 0 done, 1 problems found, 2 unusable setup."""
    args = build_parser().parse_args(argv)
    try:
        from rdf_persistence.generation import steps  # lazy: needs the `generate` extra
    except ModuleNotFoundError as error:
        if (error.name or "").split(".")[0] != "linkml":
            raise
        print(EXTRA_HINT, file=sys.stderr)
        return EXIT_USAGE
    try:
        targets = read_targets(args.project, args)
    except ConfigError as error:
        print(f"rp-generate: {error}", file=sys.stderr)
        return EXIT_USAGE
    problems = generate(targets, args.project.resolve().parent, steps.STEPS, check=args.check)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return EXIT_FAILED
    print(
        f"rp-generate: {'checked' if args.check else 'generated'} {len(targets)} target(s), no problems"
    )
    return EXIT_OK
