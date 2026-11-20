#!/usr/bin/env python3
"""Build the engine-free "lite" edition of the skill for plugin directories that accept
only Markdown, JSON, YAML and images from unverified publishers.

The lite edition has no scripts and no hooks. Its hand-written files (SKILL.md, the scoring
rules, the research guide, the agents, the manifest) live in the output folder. This tool
generates the rest from the full skill, so the expert guidance cannot drift:

    python tools/build_lite.py            # rewrite the generated files
    python tools/build_lite.py --check    # exit 1 if a generated file is out of date

A replacement whose source text is no longer in the full skill fails the build: that is the
signal to look at what changed and update the wording here.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FULL = ROOT / "skills" / "enterprise-experts"
LITE = ROOT / "directory" / "enterprise-experts-lite"
SKILL = LITE / "skills" / "enterprise-experts-lite"
sys.path.insert(0, str(FULL / "scripts"))

LOG = "and record the command, its exit code and its output in the evidence log"
NOTE = "write the URL, the date you read it and what the page said into the evidence log"

# (file, [(exact text in the full skill, text in the lite edition), ...])
REPLACEMENTS = {
    "references/ai-engineering.md": [
        ('record each as evidence: `EE evidence note --kind observation --location <url> --title ... --detail '
         '"<what the page said>"` stores the URL and the date.', f"record each as evidence: {NOTE}."),
    ],
    "references/deployment-advisor.md": [
        ("`discovery.json` has a `deployment_profile`. Confirm and complete it",
         "Work out the deployment profile from your discovery notes, then confirm and complete it"),
        ("record it as evidence (`EE evidence note --kind observation --location <url> ...` stores the URL and date)",
         f"record it as evidence ({NOTE})"),
    ],
    "references/experts-architecture-design.md": [
        ("`discovery.json` lists them", "your discovery notes list them"),
    ],
    "references/experts-security-data-compliance.md": [
        ("- Committed secrets: the discovery secret scan (Observed; confirm each hit by reading the file)",
         "- Committed secrets: search the tracked files for keys, tokens, private-key blocks, passwords inside "
         "connection strings and real `.env` files (Observed; confirm each hit by reading the file)"),
    ],
    "references/experts-product-leadership.md": [
        ("(`npm outdated`, `pip list --outdated`, `go list -u -m all`) through `EE evidence run`.",
         f"(`npm outdated`, `pip list --outdated`, `go list -u -m all`) {LOG}."),
        ("using the stack's commands from discovery, through `EE evidence run`.",
         f"using the stack's commands from discovery, {LOG.replace('and record', 'recording', 1)}."),
    ],
    "references/experts-performance-reliability.md": [],
    "references/experts-quality-delivery-infra.md": [],
    "references/companion-skills.md": [],
    "references/project-types.md": [
        ("measured with `EE bench`", "measured by timing at least five runs"),
        ("write a small script and run it through `EE evidence run`.", f"write a small script, run it {LOG}."),
    ],
    "references/improvement-loop.md": [
        ("Agree the acceptance criterion now and record it with the baseline: `EE bench run --label baseline "
         "--max-regression 20 --min-abs-change 0.5 --workload <script> ...`. The thresholds are stored and cannot "
         "be changed once the candidate has been measured.",
         "Agree the acceptance criterion now and write it into the evidence log with the baseline, before anything "
         "is changed: the metric, the smallest change that counts, and the largest regression allowed elsewhere. "
         "Do not change these thresholds once the candidate has been measured."),
        ("Record it with `EE approve`.",
         "Record it in `approvals.md`: who approved, when, which findings, and which files the change may touch."),
        ("`EE bench run --label candidate`, the same test command", "the same benchmark, the same test command"),
        ("8. **Compare** (`EE bench compare`). The engine calls a change an improvement only when the difference is "
         "larger than the run-to-run noise and meets the agreed threshold. If runs failed, or the command, metric or "
         "environment differed, the comparison is refused.",
         "8. **Compare.** Run each side at least five times and write down every result. Call a change an improvement "
         "only when the difference is larger than the run-to-run noise (twice the standard deviation of the baseline "
         "runs) and meets the agreed threshold. If runs failed, or the command, metric or environment differed, there "
         "is no comparison: say so."),
        ("`scorecard-before-remediation.md` is kept automatically when the remediation phase opens.",
         "copy `scorecard.md` to `scorecard-before-remediation.md` before the first change."),
        ("Use `--warmup` so caches and JITs settle.", "Discard the first runs so caches and JITs settle."),
        ("use `--metric-regex` to capture p95 latency or throughput from a load tool's output rather than timing the "
         "tool itself", "record p95 latency or throughput from a load tool's output rather than timing the tool itself"),
    ],
    "references/visual-documentation.md": [
        ("`EE graph <project> --out <review>/graphs` generates the module dependency graph and database ERD from the "
         "files (Observed). Draw the rest in Mermaid from what you inspected, and label each diagram:",
         "Draw the module dependency graph from the import statements and the database diagram from the schema or "
         "model files (both Observed), in Mermaid, and the rest from what you inspected. Label each diagram:"),
        ("regenerate (`EE graph`) and update the affected diagrams", "update the affected diagrams"),
        ("2. Capture with a browser tool, through `EE evidence run` with `--output` naming the image, so the image "
         "itself becomes part of the record (a capture that fails, or an image edited afterwards, makes the record "
         "unusable):",
         "2. Capture with a browser tool, and record the command, its exit code and the image path in the evidence "
         "log (a capture that failed is not evidence of how the page looks):"),
        ('`EE evidence run --review <review> --area 13 --title "home, desktop" --project <project> --output '
         "<review>/screenshots/raw/home-desktop.png -- npx --no-install playwright screenshot",
         "`npx --no-install playwright screenshot"),
        ("run it through `EE evidence run`, and have it save", f"run it {LOG}, and have it save"),
    ],
    "assets/deliverable-template.md": [
        ("the Orchestrator fills it from `EE score`", "the Orchestrator fills it in when scoring"),
    ],
    "assets/final-report-template.md": [
        ("exactly as `EE score` wrote them. Do not adjust them.",
         "exactly as they are in scorecard.md. Do not adjust them."),
    ],
}

VISUAL_REGRESSION = """## Visual regression

This edition cannot compare images pixel by pixel. Keep the captures the user approved in
`enterprise-review/visual-baselines/`, beside the dated review folders. To compare, open the approved capture
and the new one, describe every difference you can see, and label the result Observed. Only the user decides
that a look is right: show a first capture to them and record who approved it and when.

A difference is not automatically a defect: if it was intended and the user approves, the new capture becomes
the baseline; otherwise it is a finding for UI/UX (13). After an approved UI fix, capture again, compare, and
refresh the screenshots used in documentation. Record the commit each capture was taken from.
"""

GENERATED_NOTE = ("<!-- Generated by tools/build_lite.py from the full skill. Edit the source in "
                  "skills/enterprise-experts/, then rebuild. -->\n")
FORBIDDEN = re.compile(r"`EE\b|\bEE (?:evidence|score|validate|discover|graph|bench|research|approve|state|package|"
                       r"visual|scan|export|trend|gate|questions|intake|capabilities)\b|enterprise_experts\.py")


def transform(rel):
    text = (FULL / rel).read_text(encoding="utf-8")
    for old, new in REPLACEMENTS[rel]:
        if old not in text:
            raise SystemExit(f"build_lite: text to replace is no longer in {rel}:\n  {old[:110]}…")
        text = text.replace(old, new)
    if rel == "references/visual-documentation.md":
        head, _, _ = text.partition("## Visual regression")
        text = head + VISUAL_REGRESSION
    hit = FORBIDDEN.search(text)
    if hit:
        line = text[:hit.start()].count("\n") + 1
        raise SystemExit(f"build_lite: {rel}:{line} still refers to the engine ({hit.group(0)!r}); add a replacement")
    first, _, rest = text.partition("\n")
    return first + "\n\n" + GENERATED_NOTE + rest


def intake_questions():
    from ee import intake
    groups = [("Always ask", lambda q: q["required"]),
              ("Ask when you cannot establish the answer from the project", lambda q: not q["required"] and not q["when"]),
              ("Ask only when the project has the thing in brackets", lambda q: not q["required"] and q["when"])]
    out = ["# Intake question list", "", GENERATED_NOTE.strip(), "",
           "Record each answer in `intake.json` under `answers`, with the key shown. \"I don't know\" is recorded "
           "as `\"unknown\"`. Never fill in an answer by guessing.", ""]
    for title, keep in groups:
        rows = [q for q in intake.QUESTIONS if keep(q)]
        out += [f"## {title}", "", "| Key | Question | Answers | Why it is asked |", "|---|---|---|---|"]
        for q in rows:
            when = f" [{q['when'].replace('_', ' ')}]" if q.get("when") else ""
            options = ", ".join(f"`{o}`" for o in q["options"]) or "free text"
            if q["type"] == "multi":
                options += " (several allowed)"
            cells = [f"`{q['key']}`{when}", q["question"], options, q["why"]]
            out.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
        out.append("")
    return "\n".join(out)


def outputs():
    files = {SKILL / rel: transform(rel) for rel in REPLACEMENTS}
    files[SKILL / "references" / "intake-question-list.md"] = intake_questions()
    files[LITE / "LICENSE"] = (ROOT / "LICENSE").read_text(encoding="utf-8")
    return files


def main():
    check = "--check" in sys.argv
    stale = []
    for path, text in outputs().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current != text:
            stale.append(path.relative_to(ROOT).as_posix())
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="\n")
    if check and stale:
        print("Out of date (run python tools/build_lite.py):\n  " + "\n  ".join(stale))
        return 1
    print(f"lite edition: {len(outputs())} generated files " + ("up to date" if not stale else f"({len(stale)} rewritten)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
