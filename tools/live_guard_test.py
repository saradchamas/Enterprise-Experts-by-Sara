#!/usr/bin/env python3
"""Check the edit guard in a REAL Claude Code session. Needs a logged-in `claude` on this machine.

    python tools/live_guard_test.py

It runs the same request twice in throwaway projects:
  1. control: no review is open, so Claude should be able to edit the file;
  2. test:    a review is open in the assessment phase, so the plugin's hook should block the edit.

PASS needs both: the control proves Claude really ran and can edit, the test proves the guard
stopped it. If the control fails, the result is INCONCLUSIVE (Claude did not run or could not
edit), never a pass.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENGINE = REPO / "skills" / "enterprise-experts" / "scripts" / "enterprise_experts.py"
PROMPT = ("Use the Edit tool to change `x = 1` to `x = 2` in src/app.py. "
          "Then say in one sentence exactly what happened.")


def attempt(with_open_review):
    work = Path(tempfile.mkdtemp(prefix="ee-live-guard-"))
    try:
        (work / "src").mkdir()
        target = work / "src" / "app.py"
        target.write_text("x = 1\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=work, check=False)
        if with_open_review:
            subprocess.run([sys.executable, str(ENGINE), "state", "init", "--review", "enterprise-review/test",
                            "--mode", "quick"], cwd=work, check=True, capture_output=True)
        try:
            out = subprocess.run(["claude", "-p", PROMPT, "--plugin-dir", str(REPO), "--permission-mode", "acceptEdits"],
                                 cwd=work, capture_output=True, text=True, timeout=300, encoding="utf-8", errors="replace",
                                 stdin=subprocess.DEVNULL)
            said = (out.stdout + out.stderr).strip()
        except FileNotFoundError:
            said = "the `claude` command was not found"
        except subprocess.TimeoutExpired:
            said = "claude did not answer within 5 minutes"
        return target.read_text(encoding="utf-8").strip(), said
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main():
    print("1/2 control: no review open; Claude should be able to edit ...")
    content, said = attempt(with_open_review=False)
    print("    Claude said:", said[-300:] or "(nothing)")
    if content != "x = 2":
        print("\nINCONCLUSIVE: in the control run the file was not edited, so Claude did not run or could not edit.")
        print("Log in to Claude Code on this machine (run `claude` once), then run this script again.")
        return 2
    print("2/2 test: a review is open in the assessment phase; the edit should be blocked ...")
    content, said = attempt(with_open_review=True)
    print("    Claude said:", said[-300:] or "(nothing)")
    if content == "x = 1":
        print("\nPASS: Claude could edit without a review, and the guard blocked the same edit during assessment.")
        return 0
    print("\nFAIL: the file was changed while a review was in the assessment phase. The hook did not block the edit.")
    print("Check that the plugin's hook can run: it calls `python3`, which must be on the PATH.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
