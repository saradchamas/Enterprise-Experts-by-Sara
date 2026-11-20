"""Command line interface for the Enterprise Experts engine.

  discover  <project> [--out REVIEW]         inventory the project (read-only)
  questions --review REVIEW [--mode MODE]    the intake questions for this project (JSON)
  intake    --review REVIEW                  validate intake.json and print the risk profile
  state     init|set|show --review REVIEW    track / resume a review
  evidence  run|note|list --review REVIEW    record evidence (run: ... -- <command> [args])
  validate  --review REVIEW                  check findings.json + evidence (fail-closed)
  score     --review REVIEW                  scorecard + GO / CONDITIONAL GO / NO-GO
"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__, discovery, evidence, intake, report, scoring, state
from .areas import AREAS


def _out(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_discover(a):
    if not Path(a.project).is_dir():
        print(f"Not a directory: {a.project}", file=sys.stderr)
        return 2
    d = discovery.discover(a.project)
    md = discovery.to_markdown(d)
    if a.out:
        out = Path(a.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "discovery.json").write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        (out / "discovery.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def cmd_questions(a):
    flags = {}
    disc = Path(a.review) / "discovery.json"
    if disc.exists():
        flags = json.loads(disc.read_text(encoding="utf-8")).get("flags", {})
    _out({"note": "Ask the user these before reviewing. Record answers in intake.json under 'answers'. "
                  "Never guess an answer: use 'unknown' when the user does not know.",
          "discovery_used": disc.exists(), "questions": intake.questions_for(flags, a.mode)})
    return 0


def cmd_intake(a):
    data = intake.load_intake(a.review)
    if data is None:
        print("intake.json not found", file=sys.stderr)
        return 2
    errors = intake.validate_intake(data)
    _out({"valid": not errors, "errors": errors,
          "risk_profile": None if errors else intake.effective_risk_profile(data)})
    return 2 if errors else 0


def cmd_state(a):
    if a.action == "init":
        st = state.init(a.review, a.mode, a.scope)
    elif a.action == "set":
        st = state.set_status(a.review, a.area, a.status, a.note)
    else:
        st = state.load(a.review)
    plan = state.plan(st)
    _out({"mode": st["mode"], "areas": {f"{k} {AREAS[int(k)]}": v["status"] for k, v in st["areas"].items()},
          "plan": plan})
    return 0


def cmd_evidence(a):
    if a.action == "run":
        rec = evidence.run_command(a.review, a.area, a.title, a.command, cwd=a.cwd, timeout=a.timeout,
                                   approved=a.approved)
    elif a.action == "note":
        rec = evidence.add_note(a.review, a.area, a.title, a.kind, a.detail, a.location, a.project)
    else:
        log = evidence.load_log(a.review)
        for r in log["records"]:
            level, problem = evidence.record_level(r, a.review)
            print(f"{r['id']} | area {r.get('area')} | {level or 'BROKEN: ' + problem} | {r.get('title')} | "
                  f"{r.get('command') or r.get('location') or ''}")
        return 0
    _out(rec)
    return 0


def cmd_validate(a):
    _d, _i, _c, errors = scoring.validate(a.review)
    _out({"valid": not errors, "errors": errors})
    return 2 if errors else 0


def cmd_score(a):
    res = scoring.evaluate(a.review)
    if not a.no_write:
        report.write_all(res, a.review)
    print(json.dumps(res, indent=2, ensure_ascii=False) if a.json else report.to_markdown(res))
    return res["exit_code"]


def build_parser():
    p = argparse.ArgumentParser(prog="enterprise-experts", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("discover")
    s.add_argument("project")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_discover)

    s = sub.add_parser("questions")
    s.add_argument("--review", required=True)
    s.add_argument("--mode", choices=["full", "quick", "focused"])
    s.set_defaults(fn=cmd_questions)

    s = sub.add_parser("intake")
    s.add_argument("--review", required=True)
    s.set_defaults(fn=cmd_intake)

    s = sub.add_parser("state")
    s.add_argument("action", choices=["init", "set", "show"])
    s.add_argument("--review", required=True)
    s.add_argument("--mode", choices=["full", "quick", "focused"])
    s.add_argument("--scope", type=int, nargs="+")
    s.add_argument("--area", type=int)
    s.add_argument("--status", choices=state.STATUSES)
    s.add_argument("--note")
    s.set_defaults(fn=cmd_state)

    s = sub.add_parser("evidence")
    s.add_argument("action", choices=["run", "note", "list"])
    s.add_argument("--review", required=True)
    s.add_argument("--area", type=int)
    s.add_argument("--title")
    s.add_argument("--cwd", default=".")
    s.add_argument("--timeout", type=int, default=900)
    s.add_argument("--approved", action="store_true",
                   help="the user explicitly approved this risky command")
    s.add_argument("--kind", choices=["observation", "inference"])
    s.add_argument("--detail", default="")
    s.add_argument("--location")
    s.add_argument("--project")
    s.set_defaults(fn=cmd_evidence)

    s = sub.add_parser("validate")
    s.add_argument("--review", required=True)
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("score")
    s.add_argument("--review", required=True)
    s.add_argument("--json", action="store_true")
    s.add_argument("--no-write", action="store_true")
    s.set_defaults(fn=cmd_score)
    return p


def main(argv=None):
    # Reports contain characters (★, —, …, Arabic) that legacy Windows consoles cannot
    # encode; without this the CLI would crash while printing a valid scorecard.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    command = []
    if "--" in argv:  # everything after "--" is the command for `evidence run`
        i = argv.index("--")
        argv, command = argv[:i], argv[i + 1:]
    a = build_parser().parse_args(argv)
    a.command = command
    if a.cmd == "evidence" and a.action in ("run", "note") and (a.area is None or not a.title):
        print("evidence run/note need --area and --title", file=sys.stderr)
        return 2
    if a.cmd == "state" and a.action == "set" and (a.area is None or not a.status):
        print("state set needs --area and --status", file=sys.stderr)
        return 2
    try:
        return a.fn(a)
    except PermissionError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except (ValueError, FileExistsError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
