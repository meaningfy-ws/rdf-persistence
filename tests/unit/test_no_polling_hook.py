"""The PreToolUse hook that denies sleep loops in Bash (agent-efficiency, PD-1 to PD-3)."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK = REPO_ROOT / ".claude" / "hooks" / "no_polling.py"

_spec = importlib.util.spec_from_file_location("no_polling", HOOK)
assert _spec is not None and _spec.loader is not None
no_polling = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(no_polling)

DENIED = [
    'until grep -q "^real" temp/checkall.log; do sleep 5; done; tail -12 temp/checkall.log',
    'for i in $(seq 1 23); do grep -q "^real" temp/checkall.log && break; sleep 5; done; '
    "tail -1 temp/checkall.log",
    "cd /tmp/tasks/; for i in $(seq 34); do kill -0 582896 2>/dev/null || break; sleep 5; done",
    'while pgrep -f "make test" >/dev/null; do sleep 5; done; tail -30 /tmp/buiqvrb6f.output',
    "timeout 178 bash -c 'until grep -q \"^real\" temp/dt-make-test.log; do sleep 5; done'; "
    "tail -c 200 temp/dt-make-test.log",
    'while ! grep -q "^real" temp/par5.log 2>/dev/null; do sleep 5; done; '
    'grep -E " passed" temp/par5.log',
    "until gh pr checks 154 >/dev/null 2>&1; do sleep 5; done; gh pr checks 154 --watch --interval 15",
    "for i in $(seq 1 40); do\n  s=$(docker inspect fuseki)\n"
    '  [ "$s" = healthy ] && break\n  sleep 6\ndone',
    "for i in $(seq 30); do test -f temp/done.flag && break; sleep 2; done",
    "while true; do grep -q done log && break; sleep 5; done",
    "for a in 1 2; do for b in 3; do :; done; sleep 1; done",
]

ALLOWED = [
    "sleep 5; gh pr merge 41 --merge 2>&1 | tail -1",
    "gh pr checks 161 --watch --interval 30 2>&1 | tail -8",
    "for s in wait_until fuseki; do timeout 60 gitnexus impact $s --direction upstream; done",
    "( time make check-all ) 2>&1 | tail -30",
    "python3 - <<'E'\nwhile True:\n    time.sleep(1)\nE",
    'git commit -m "fix: do not sleep in tests"',
    "make test-changed",
    "for f in *.py; do ruff format $f; done",
    "for f in a b; do echo $f; done; sleep 3",
]


def bash(command: object) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


@pytest.mark.parametrize("command", DENIED)
def test_a_sleep_loop_is_denied_with_the_alternatives(command: str) -> None:
    assert no_polling.reason_to_deny(bash(command)) == no_polling.REASON


@pytest.mark.parametrize(
    "alternative", ["foreground", "600000", "run_in_background", "completion notice", "Monitor"]
)
def test_the_reason_names_every_alternative(alternative: str) -> None:
    assert alternative in no_polling.REASON


@pytest.mark.parametrize("command", ALLOWED)
def test_any_other_command_runs(command: str) -> None:
    assert no_polling.reason_to_deny(bash(command)) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"tool_name": "Read", "tool_input": {"command": DENIED[0]}},
        {"tool_name": "Bash"},
        bash(None),
        bash([DENIED[0]]),
    ],
)
def test_a_payload_that_is_not_a_bash_command_runs(payload: dict[str, object]) -> None:
    assert no_polling.reason_to_deny(payload) is None


def run(
    args: list[str], stdin: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, input=stdin, capture_output=True, text=True, env=env, check=False)


def test_the_hook_prints_a_json_deny_and_exits_0() -> None:
    denied = run([sys.executable, str(HOOK)], json.dumps(bash(DENIED[0])))
    allowed = run([sys.executable, str(HOOK)], json.dumps(bash(ALLOWED[0])))

    decision = json.loads(denied.stdout)["hookSpecificOutput"]
    assert denied.returncode == 0
    assert decision["permissionDecision"] == "deny"
    assert "run_in_background" in decision["permissionDecisionReason"]
    assert (allowed.returncode, allowed.stdout) == (0, "")


def test_unreadable_input_never_exits_2() -> None:
    result = run([sys.executable, str(HOOK)], "not json")

    assert result.returncode != 2
    assert result.returncode != 0 or result.stdout == ""


def test_the_settings_wrapper_lets_the_command_run_when_the_hook_is_missing(tmp_path: Path) -> None:
    settings = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text())
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    payload = json.dumps(bash(DENIED[0]))

    missing = run(
        ["bash", "-c", command], payload, {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    )
    present = run(
        ["bash", "-c", command], payload, {**os.environ, "CLAUDE_PROJECT_DIR": str(REPO_ROOT)}
    )

    assert (missing.returncode, missing.stdout) == (0, "")
    assert json.loads(present.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
