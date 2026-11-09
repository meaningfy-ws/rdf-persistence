"""PreToolUse hook: deny Bash commands that poll with a sleep loop (agent-efficiency, PD-1).

It denies through JSON and never exits 2, so if it fails for any reason the command runs (DEC-3).
"""

import json
import re
import sys

POLLING = re.compile(r"\b(?:until|while|for)\b.*?\bdo\b.*?\bsleep\b.*?\bdone\b", re.DOTALL)

REASON = (
    "Polling loops are blocked in this repository (AGENTS.md, Habits). Run the command in the "
    "foreground with a timeout of up to 600000 ms (every make target finishes within it); or run it "
    "with run_in_background and wait for the completion notice; or, to wait on a condition, use the "
    "Monitor tool. Do not sleep in a loop in Bash."
)


def reason_to_deny(payload: dict[str, object]) -> str | None:
    """The reason to deny this tool call, or None to let it run."""
    tool_input = payload.get("tool_input")
    if payload.get("tool_name") != "Bash" or not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if isinstance(command, str) and POLLING.search(command):
        return REASON
    return None


def main() -> None:
    reason = reason_to_deny(json.load(sys.stdin))
    if reason:
        decision = {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
        print(json.dumps({"hookSpecificOutput": decision}))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # any failure lets the command run (DEC-3)
        sys.exit(1)
