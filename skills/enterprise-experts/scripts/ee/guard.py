"""Edit and command guard, used by the plugin's PreToolUse hook.

While a review is active in a project, this decides whether a tool call may
proceed. It is deterministic and holds no opinion: the rules are

  assessment phase   project files are read-only; only the review folder is writable
  remediation phase  a project file may be edited only if a recorded approval covers
                     it and the checked-out branch is not the default branch
  any phase          commands that delete, publish, deploy, migrate or rewrite history
                     are blocked unless that exact command was approved

Limits, stated plainly: it sees only the tool calls the host sends to the hook. A
shell command can still write files through redirection or a script; pattern
matching is not a sandbox. The approval record proves an approval was recorded,
not who typed it. Use it together with the host's own permission prompts.
"""
import fnmatch
import json
import re
from pathlib import Path

from .policy import check_shell

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
PROTECTED_BRANCHES = {"main", "master", "production", "prod", "release"}
REVIEW_DIR = "enterprise-review"
ENGINE_OWNED = {"review-state.json", "evidence-log.json"}
SAFE_IN_REMEDIATION = re.compile(r"^\s*git\s+(add|commit|switch|checkout\s+-b|worktree\s+add|stash|restore\s+--staged)\b")


def find_active_review(cwd):
    """(project_root, review_dir, state) for the open review that governs cwd, else None."""
    here = Path(cwd).resolve()
    for base in [here, *here.parents][:8]:
        root = base / REVIEW_DIR
        if not root.is_dir():
            continue
        candidates = sorted(root.glob("*/review-state.json"), reverse=True) + list(root.glob("review-state.json"))
        for state_file in candidates:
            try:
                state = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return base, state_file.parent, None      # unreadable state: caller fails closed
            if not state.get("closed"):
                return base, state_file.parent, state
        return None
    return None


def current_branch(project_root):
    try:
        head = (Path(project_root) / ".git" / "HEAD").read_text().strip()
    except OSError:
        return None
    return head.split("refs/heads/", 1)[1] if "refs/heads/" in head else "(detached)"


def _covered(rel, approvals):
    for ap in approvals:
        for pattern in ap.get("paths", []):
            if fnmatch.fnmatch(rel, pattern.replace("**/", "*").replace("**", "*")) or rel == pattern:
                return True
    return False


def decide(event):
    """Return (allowed: bool, message: str) for a PreToolUse event."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    cwd = event.get("cwd") or "."
    found = find_active_review(cwd)
    if not found:
        return True, ""
    project, review_dir, state = found
    if state is None:
        return False, ("Enterprise Experts: the review state file is unreadable, so changes are blocked. "
                       "Repair or remove " + str(review_dir / "review-state.json"))
    phase = state.get("phase", "assessment")
    approvals = state.get("approvals", [])

    if tool in EDIT_TOOLS:
        target = tool_input.get("file_path") or tool_input.get("notebook_path")
        if not target:
            return True, ""
        path = (Path(cwd) / target).resolve()
        if (project / REVIEW_DIR).resolve() in [path, *path.parents]:
            # The engine's own records are written by the engine, not by hand: a hand-written
            # evidence log or state file would defeat the checks that rely on them.
            if path.name in ENGINE_OWNED or path.name.startswith("scorecard") or "evidence" in path.relative_to(
                    (project / REVIEW_DIR).resolve()).parts[:-1]:
                return False, (f"Enterprise Experts: '{path.name}' is written by the engine only. Use the "
                               "`evidence`, `state`, `approve` and `score` commands instead of editing it.")
            return True, ""
        if project.resolve() not in path.parents:
            return True, ""
        rel = path.relative_to(project.resolve()).as_posix()
        if phase != "remediation":
            return False, (f"Enterprise Experts: the review is in the assessment phase, which is read-only. "
                           f"'{rel}' was not changed. Record the finding and propose the fix in the remediation plan; "
                           "edit only after the user approves it.")
        if not _covered(rel, approvals):
            return False, (f"Enterprise Experts: no recorded approval covers '{rel}'. Ask the user to approve this "
                           "change, then record it with `approve --paths`.")
        branch = current_branch(project)
        if branch in PROTECTED_BRANCHES:
            return False, (f"Enterprise Experts: fixes are not made on '{branch}'. Create a remediation branch first.")
        return True, ""

    if tool == "Bash":
        command = str(tool_input.get("command", ""))
        reason = check_shell(command)
        if not reason:
            return True, ""
        if command.strip() in {c.get("command", "").strip() for c in state.get("approved_commands", [])}:
            return True, ""
        if phase == "remediation" and approvals and SAFE_IN_REMEDIATION.match(command) \
                and current_branch(project) not in PROTECTED_BRANCHES:
            return True, ""
        return False, (f"Enterprise Experts: this command {reason} and a review is active. It was not run. "
                       "Ask the user; if they approve this exact command, record it with `approve --exact-command`.")
    return True, ""
