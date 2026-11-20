# Installation

## Requirements

- Claude Code, or Claude with skills enabled, to run reviews.
- Python 3.10 or newer for the engine. It uses only the standard library; there is nothing to `pip install`.
- Optional: Docker with Compose v2, for the isolated runner.
- The project's own tools (node, go, pytest, ...) are needed only to run that project's checks. A missing tool means those checks are reported as Not assessed.

## Option 1: Claude Code plugin

```
/plugin marketplace add saradchamas/Enterprise-Experts-by-Sara
/plugin install enterprise-experts@enterprise-experts-by-sara
```

Or from a terminal, using a local clone:

```bash
git clone https://github.com/saradchamas/Enterprise-Experts-by-Sara.git
claude plugin marketplace add ./Enterprise-Experts-by-Sara
claude plugin install enterprise-experts@enterprise-experts-by-sara
claude plugin details enterprise-experts@enterprise-experts-by-sara
```

`details` should list one skill (`enterprise-experts`), two agents (`expert-reviewer`, `independent-reviewer`) and one hook (`PreToolUse`). The hook runs `python3`; on Windows make sure `python3` is on the PATH, or the guard will not run.

Uninstall:

```bash
claude plugin uninstall enterprise-experts@enterprise-experts-by-sara
claude plugin marketplace remove enterprise-experts-by-sara
```

Tested: install, details and uninstall from a local clone (Linux, Claude Code CLI). Installing straight from GitHub has not been tested yet.

## Option 2: standalone skill

Copy the folder `skills/enterprise-experts/` into `~/.claude/skills/` (personal) or `<project>/.claude/skills/` (one project). In the Claude apps, upload the packaged `enterprise-experts.skill` file instead.

To remove it, delete that folder (or remove the skill in Claude's settings).

## Verify the engine

From the repository root:

```bash
python skills/enterprise-experts/scripts/enterprise_experts.py --version
python -m unittest discover -s tests -t .
```

The first prints the version; the second should end with `OK`.

## Platforms

| Platform | Engine and tests | Docker runner |
|---|---|---|
| Linux | Tested locally and in CI (Python 3.10, 3.13) | Tested locally and in CI |
| macOS | Passing in CI (Python 3.10, 3.13) | Not tested |
| Windows | Passing in CI (Python 3.10, 3.13) since the console fix in 0.3.0 | Not tested; use Docker Desktop with WSL2 and run the commands from the WSL shell |
