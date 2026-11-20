"""Verified optimisation loop: measure before, measure after, and only call it an
improvement when the difference is larger than the run-to-run noise.

A benchmark is the same command run several times. Each run's wall-clock time is
recorded, or a number parsed from its output with --metric-regex (for example the
p95 line printed by a load-testing tool).
"""
import json
import os
import platform
import re
import statistics
import subprocess
import time
from pathlib import Path

from . import evidence
from .policy import check_command
from .secrets import mask_text

DIR = "benchmarks"
LABELS = ("baseline", "candidate")
NAME_RX = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


def environment():
    return {"platform": platform.platform(), "machine": platform.machine(), "cpus": os.cpu_count(),
            "python": platform.python_version()}


def stats(samples):
    return {"n": len(samples), "median": statistics.median(samples), "mean": statistics.fmean(samples),
            "stdev": statistics.stdev(samples) if len(samples) > 1 else 0.0, "min": min(samples), "max": max(samples)}


def _latest(review, name, label):
    files = sorted((Path(review) / DIR).glob(f"{name}-{label}-[0-9][0-9].json"))
    return files[-1] if files else None


def run(review_dir, name, label, argv, runs=5, warmup=1, cwd=".", metric_regex=None, unit=None, area=3,
        timeout=600, approved=False, also_areas=(), workload_files=(), acceptance=None):
    """`acceptance` (baseline only) records the thresholds agreed before the change:
    {"min_improvement_pct", "max_regression_pct", "min_abs_change"}. `workload_files` are hashed so
    that the comparison can tell the same script and data were used."""
    if not NAME_RX.match(name or ""):
        raise ValueError("benchmark name must be lowercase letters, digits and dashes")
    if label not in LABELS:
        raise ValueError(f"label must be one of {list(LABELS)}")
    if runs < 3:
        raise ValueError("at least 3 runs are needed to see the noise")
    if not argv:
        raise ValueError("no command given")
    reason = check_command(argv)
    if reason and not approved:
        raise PermissionError(f"Refused: this command {reason}. Get the user's explicit approval, then use --approved.")
    rx = re.compile(metric_regex) if metric_regex else None
    samples, failures, log = [], 0, []
    for i in range(warmup + runs):
        t0 = time.perf_counter()
        try:
            proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout, errors="replace",
                                  stdin=subprocess.DEVNULL)
            code, out = proc.returncode, (proc.stdout or "") + (proc.stderr or "")
        except subprocess.TimeoutExpired:
            code, out = None, "[timed out]"
        except FileNotFoundError:
            code, out = 127, f"[command not found: {argv[0]}]"
        elapsed = time.perf_counter() - t0
        value = elapsed
        if rx:
            m = rx.search(out)
            value = float(m.group(1)) if m else None
        measured = i >= warmup
        ok = code == 0 and value is not None
        log.append({"run": i + 1, "warmup": not measured, "exit_code": code, "seconds": round(elapsed, 4),
                    "value": value})
        if measured:
            if ok:
                samples.append(value)
            else:
                failures += 1
    review = Path(review_dir)
    (review / DIR).mkdir(parents=True, exist_ok=True)
    if acceptance and label != "baseline":
        raise ValueError("acceptance thresholds are agreed before the change: record them with the baseline run")
    result = {"name": name, "label": label, "command": mask_text(" ".join(argv)), "cwd": str(cwd),
              "workload": {Path(f).name: evidence.sha256_file(f) for f in workload_files},
              "acceptance": acceptance or None,
              "metric": metric_regex or "wall-clock seconds", "unit": unit or ("s" if not rx else ""),
              "runs": runs, "warmup": warmup, "failures": failures, "samples": samples,
              "stats": stats(samples) if samples else None, "environment": environment(),
              "commit": evidence.git_commit(cwd), "log": log}
    # Every run keeps its own file: re-running a label must not rewrite evidence already cited.
    n = len(list((review / DIR).glob(f"{name}-{label}-[0-9][0-9].json"))) + 1
    path = review / DIR / f"{name}-{label}-{n:02d}.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    rec = evidence.add_artifact(review, area, f"benchmark {name} ({label}, run {n})", result["command"], path,
                                exit_code=0 if not failures else 1, commit=result["commit"], also_areas=also_areas)
    result["evidence"] = rec["id"]
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    evidence.refresh_hash(review, rec["id"])
    return result


def compare(review_dir, name, min_improvement=None, max_regression=None, higher_is_better=False, min_abs_change=None):
    """Verdict: improved | regressed | no_significant_change | not_comparable.
    Uses the latest baseline and candidate runs, and the thresholds agreed with the baseline if any."""
    review = Path(review_dir)
    paths = [_latest(review, name, label) for label in LABELS]
    if None in paths:
        raise ValueError("both a baseline and a candidate run are needed for " + name)
    base, cand = (json.loads(p.read_text(encoding="utf-8")) for p in paths)
    agreed = base.get("acceptance") or {}
    given = {"min_improvement_pct": min_improvement, "max_regression_pct": max_regression, "min_abs_change": min_abs_change}
    for key, value in given.items():
        if value is not None and key in agreed and agreed[key] != value:
            raise ValueError(f"{key} was agreed as {agreed[key]} when the baseline was recorded; it cannot be changed "
                             "after seeing the candidate. Record a new baseline if the criterion really changed.")
    min_improvement = agreed.get("min_improvement_pct", 10.0 if min_improvement is None else min_improvement)
    max_regression = agreed.get("max_regression_pct", 5.0 if max_regression is None else max_regression)
    min_abs_change = agreed.get("min_abs_change", 0.0 if min_abs_change is None else min_abs_change)
    problems = []
    if base.get("workload") != cand.get("workload"):
        problems.append("the benchmark script or data files differ between baseline and candidate")
    if base["command"] != cand["command"]:
        problems.append("the command differs between baseline and candidate")
    if base["metric"] != cand["metric"]:
        problems.append("the metric differs between baseline and candidate")
    if base["environment"] != cand["environment"]:
        problems.append("the runs were made in different environments")
    for run_ in (base, cand):
        if run_["failures"]:
            problems.append(f"{run_['label']}: {run_['failures']} run(s) failed, so the workload was not the same")
        if not run_["stats"] or run_["stats"]["n"] < 3:
            problems.append(f"{run_['label']}: fewer than 3 successful runs")
    out = {"name": name, "metric": base["metric"], "unit": base.get("unit", ""), "baseline": base["stats"],
           "candidate": cand["stats"], "baseline_commit": base.get("commit"), "candidate_commit": cand.get("commit"),
           "evidence": [base.get("evidence"), cand.get("evidence")], "problems": problems,
           "thresholds": {"min_improvement_pct": min_improvement, "max_regression_pct": max_regression,
                          "min_abs_change": min_abs_change, "agreed_with_baseline": bool(agreed)}}
    if problems:
        out.update(verdict="not_comparable", change_pct=None, reason="; ".join(problems))
    else:
        b, c = base["stats"], cand["stats"]
        change = (c["median"] - b["median"]) / b["median"] * 100 if b["median"] else 0.0
        gain = change if higher_is_better else -change            # positive = better
        noise = 2 * max(b["stdev"], c["stdev"])
        significant = abs(c["median"] - b["median"]) > noise
        out.update(change_pct=round(change, 2), gain_pct=round(gain, 2), noise_band=noise, significant=significant)
        if not significant:
            out.update(verdict="no_significant_change",
                       reason="the difference is within the run-to-run noise (2 standard deviations)")
        elif abs(c["median"] - b["median"]) < min_abs_change:
            out.update(verdict="no_significant_change",
                       reason=f"a real change of {gain:+.1f}%, but smaller in absolute terms than the agreed "
                              f"{min_abs_change} {base.get('unit', '')} that matters for this project")
        elif gain >= min_improvement:
            out.update(verdict="improved", reason=f"median better by {gain:.1f}%, beyond noise")
        elif gain <= -max_regression:
            out.update(verdict="regressed", reason=f"median worse by {-gain:.1f}%, beyond noise")
        else:
            out.update(verdict="no_significant_change",
                       reason=f"a real change of {gain:+.1f}%, below the agreed {min_improvement}% threshold")
    (review / DIR / f"{name}-comparison.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (review / DIR / f"{name}-comparison.md").write_text(to_markdown(out), encoding="utf-8")
    return out


def to_markdown(c):
    def row(label, s):
        if not s:
            return f"| {label} | — | — | — | — | — |"
        return f"| {label} | {s['n']} | {s['median']:.4g} | {s['mean']:.4g} | {s['stdev']:.3g} | {s['min']:.4g} – {s['max']:.4g} |"
    lines = [f"# Benchmark comparison: {c['name']}", "",
             f"**Verdict: {c['verdict'].replace('_', ' ').upper()}** — {c['reason']}", "",
             f"Metric: {c['metric']} {c['unit']}  |  Evidence: {', '.join(e for e in c['evidence'] if e)}", "",
             "| Run | Samples | Median | Mean | Std dev | Range |", "|---|---|---|---|---|---|",
             row("Baseline", c["baseline"]), row("Candidate", c["candidate"]), ""]
    if c.get("change_pct") is not None:
        lines += [f"Change in median: {c['change_pct']:+.2f}%  |  Noise band: ±{c['noise_band']:.3g}", ""]
    lines += ["A change counts as an improvement only when it is larger than the noise and meets the agreed threshold. "
              "Keep the code change only if this verdict is IMPROVED and the test suite still passes.", ""]
    return "\n".join(lines)
