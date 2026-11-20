"""Command line interface for the Enterprise Experts engine.

  discover  <project> [--out REVIEW]         inventory the project (read-only)
  questions --review REVIEW [--mode MODE]    the intake questions for this project (JSON)
  intake    --review REVIEW                  validate intake.json and print the risk profile
  state     init|set|show --review REVIEW    track / resume a review
  evidence  run|note|list --review REVIEW    record evidence (run: ... -- <command> [args])
  approve   --review REVIEW --by NAME ...    record a user approval (paths a fix may touch, or one command)
  bench     run|compare --review REVIEW      measure before/after and judge the difference against noise
  graph     <project> --out DIR              dependency graph and database ERD (Mermaid) from the code
  package   --review REVIEW                  assemble the Final Engineering Delivery folder
  capabilities --review REVIEW               which areas, workflows and checks apply to this project
  scan      import --review REVIEW ...       scanner output (SARIF, npm audit, osv, pip-audit, trivy, gitleaks) -> candidates
  visual    compare|approve --review REVIEW  real screenshot vs approved baseline
  validate  --review REVIEW                  check findings.json + evidence (fail-closed)
  score     --review REVIEW                  scorecard + GO / CONDITIONAL GO / NO-GO
"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__, bench, capabilities, discovery, evidence, graphs, intake, package, report, scanners, scoring, state, visual
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
        matrix = capabilities.build(d)
        (out / "capability-matrix.json").write_text(json.dumps(matrix, indent=2), encoding="utf-8")
        (out / "capability-matrix.md").write_text(capabilities.to_markdown(matrix), encoding="utf-8")
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
    elif a.action == "phase":
        st = state.set_phase(a.review, a.phase)
    elif a.action == "close":
        st = state.close(a.review)
    else:
        st = state.load(a.review)
    plan = state.plan(st)
    _out({"mode": st["mode"], "phase": st.get("phase", "assessment"), "closed": bool(st.get("closed")),
          "approvals": len(st.get("approvals", [])), "areas": {f"{k} {AREAS[int(k)]}": v["status"] for k, v in st["areas"].items()},
          "plan": plan})
    return 0


def cmd_evidence(a):
    if a.action == "run":
        rec = evidence.run_command(a.review, a.area, a.title, a.command, cwd=a.cwd, timeout=a.timeout,
                                   approved=a.approved, also_areas=a.also)
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


def cmd_approve(a):
    st = state.approve(a.review, a.by, a.findings or [], a.paths or [], a.exact_command, a.note)
    _out({"approvals": st.get("approvals", []), "approved_commands": st.get("approved_commands", [])})
    return 0


def cmd_bench(a):
    if a.action == "run":
        if not a.label:
            raise ValueError("bench run needs --label baseline|candidate")
        res = bench.run(a.review, a.name, a.label, a.command, runs=a.runs, warmup=a.warmup, cwd=a.cwd,
                        metric_regex=a.metric_regex, unit=a.unit, area=a.area or 3, approved=a.approved)
        _out({k: res[k] for k in ("name", "label", "command", "metric", "failures", "stats", "evidence")})
        return 0
    res = bench.compare(a.review, a.name, a.min_improvement, a.max_regression, a.higher_is_better)
    print(bench.to_markdown(res))
    return {"improved": 0, "no_significant_change": 10, "regressed": 20, "not_comparable": 2}[res["verdict"]]


def cmd_graph(a):
    res = graphs.write(a.project, a.out, a.depth)
    _out({"written": res["written"], "skipped": res["skipped"], "modules_edges": len(res["dependency"]["edges"]),
          "cycles": res["dependency"]["cycles"], "tables": sorted(res["database"]["tables"])})
    return 0


def cmd_package(a):
    _out(package.build(a.review))
    return 0


def cmd_capabilities(a):
    disc = Path(a.review) / "discovery.json"
    if not disc.exists():
        raise ValueError("run `discover <project> --out <review>` first")
    matrix = capabilities.build(json.loads(disc.read_text(encoding="utf-8")))
    print(json.dumps(matrix, indent=2) if a.json else capabilities.to_markdown(matrix))
    return 0


def cmd_scan(a):
    res = scanners.import_scan(a.review, a.evidence, a.file)
    _out({k: res[k] for k in ("source", "format", "count", "by_severity", "note")})
    for c in res["candidates"][:a.show]:
        print(f"- [{c['severity']}] {c['title']} | {c['package'] or c['location'] or ''} | {c['rule'] or ''}")
    return 0


def cmd_visual(a):
    if a.action == "approve":
        _out(visual.approve(a.review, a.name, a.by, a.baselines, a.project))
        return 0
    if not a.image:
        raise ValueError("visual compare needs --image <png captured from the running app>")
    res = visual.compare(a.review, a.name, a.image, a.baselines, a.threshold)
    _out(res)
    return {"match": 0, "no_baseline": 10, "changed": 20}[res["verdict"]]


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
    s.add_argument("action", choices=["init", "set", "show", "phase", "close"])
    s.add_argument("--phase", choices=["assessment", "remediation"])
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
    s.add_argument("--also", type=int, nargs="*", default=[],
                   help="for 'run': other areas that may cite this same record")
    s.add_argument("--kind", choices=["observation", "inference"])
    s.add_argument("--detail", default="")
    s.add_argument("--location")
    s.add_argument("--project")
    s.set_defaults(fn=cmd_evidence)

    s = sub.add_parser("approve", help="record a decision the user made")
    s.add_argument("--review", required=True)
    s.add_argument("--by", required=True, help="who approved")
    s.add_argument("--findings", nargs="*")
    s.add_argument("--paths", nargs="*", help="files or globs the approved fix may change")
    s.add_argument("--exact-command", help="one exact risky command the user approved")
    s.add_argument("--note")
    s.set_defaults(fn=cmd_approve)

    s = sub.add_parser("bench")
    s.add_argument("action", choices=["run", "compare"])
    s.add_argument("--review", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--label", choices=bench.LABELS)
    s.add_argument("--runs", type=int, default=5)
    s.add_argument("--warmup", type=int, default=1)
    s.add_argument("--cwd", default=".")
    s.add_argument("--area", type=int)
    s.add_argument("--metric-regex", help="regex with one group capturing the number to compare")
    s.add_argument("--unit")
    s.add_argument("--approved", action="store_true")
    s.add_argument("--min-improvement", type=float, default=10.0)
    s.add_argument("--max-regression", type=float, default=5.0)
    s.add_argument("--higher-is-better", action="store_true")
    s.set_defaults(fn=cmd_bench)

    s = sub.add_parser("graph")
    s.add_argument("project")
    s.add_argument("--out", required=True)
    s.add_argument("--depth", type=int, default=2)
    s.set_defaults(fn=cmd_graph)

    s = sub.add_parser("package")
    s.add_argument("--review", required=True)
    s.set_defaults(fn=cmd_package)

    s = sub.add_parser("capabilities", help="which areas, workflows and checks apply to this project")
    s.add_argument("--review", required=True)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_capabilities)

    s = sub.add_parser("scan", help="turn recorded scanner output into candidate findings")
    s.add_argument("action", choices=["import"])
    s.add_argument("--review", required=True)
    s.add_argument("--evidence", help="id of the evidence record that captured the scanner's output")
    s.add_argument("--file", help="or: a results file inside the review folder (SARIF/JSON)")
    s.add_argument("--show", type=int, default=20)
    s.set_defaults(fn=cmd_scan)

    s = sub.add_parser("visual", help="compare a real screenshot with its approved baseline")
    s.add_argument("action", choices=["compare", "approve"])
    s.add_argument("--review", required=True)
    s.add_argument("--name", required=True)
    s.add_argument("--image")
    s.add_argument("--baselines", help="baseline folder (default: <review>/../visual-baselines)")
    s.add_argument("--threshold", type=float, default=0.1, help="allowed percent of changed pixels")
    s.add_argument("--by")
    s.add_argument("--project")
    s.set_defaults(fn=cmd_visual)

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
    if a.cmd == "state" and a.action == "phase" and not a.phase:
        print("state phase needs --phase", file=sys.stderr)
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
