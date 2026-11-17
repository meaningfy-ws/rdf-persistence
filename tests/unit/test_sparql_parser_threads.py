"""rdflib's SPARQL parser, called by several threads at once, never fails (it did: ``Param.postParse2() missing
1 required positional argument``, from pyparsing's shared arity counter, for the rest of the process).

The race is in the first parse of a process, so each round starts a new one. The worker is ``tests.unit.sparql_threads``.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROUNDS = 5
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.slow
@pytest.mark.parametrize("round_number", range(ROUNDS))
def test_threads_that_parse_sparql_at_once_all_succeed(round_number: int):
    done = subprocess.run(
        [sys.executable, "-m", "tests.unit.sparql_threads"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    assert done.returncode == 0, done.stderr
