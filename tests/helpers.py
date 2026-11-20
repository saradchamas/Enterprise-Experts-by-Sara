"""Shared helpers: builds a review folder with real evidence records."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills" / "enterprise-experts" / "scripts"
FIXTURES = REPO / "tests" / "fixtures"
sys.path.insert(0, str(SCRIPTS))

from ee import evidence  # noqa: E402
from ee.areas import AREAS, required_areas  # noqa: E402

OK_CMD = [sys.executable, "-c", "print('check passed')"]
BASE_ANSWERS = {"purpose": "Internal demo tool", "stage": "prototype", "exposure": "internal",
                "industry": "internal_tool", "data_types": ["none"], "handles_money": "no",
                "change_permission": "assess_only", "environments_allowed": ["local"]}


def build_review(path, mode="full", scope=None, answers=None, risk="standard"):
    """A complete, valid review: every required area assessed at 90 with one command
    record and one observation. Tests then break it in one specific way."""
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    project = path / "_project"
    project.mkdir()
    (project / "app.py").write_text("print('hi')\n")
    areas = []
    for aid in sorted(required_areas(mode, scope)):
        cmd = evidence.run_command(path, aid, f"check area {aid}", OK_CMD, cwd=str(project))
        obs = evidence.add_note(path, aid, f"read area {aid}", "observation", "looked at it", "app.py:1", str(project))
        areas.append({"id": aid, "name": AREAS[aid], "status": "assessed", "score": 90, "summary": "ok",
                      "checks": [{"id": f"C{aid}-1", "title": "ran it", "result": "pass", "evidence": [cmd["id"]]},
                                 {"id": f"C{aid}-2", "title": "read it", "result": "pass", "evidence": [obs["id"]]}],
                      "findings": []})
    findings = {"schema_version": 2, "project": "fixture", "review_date": "2026-11-20", "mode": mode,
                "risk_profile": risk, "areas": areas}
    if mode == "focused":
        findings["scope"] = sorted(scope)
    intake = {"schema_version": 1, "answers": dict(BASE_ANSWERS, review_mode=mode, **(answers or {}))}
    if mode == "focused":
        intake["answers"]["focus_areas"] = sorted(scope)
    write(path, findings, intake)
    return path


def write(path, findings=None, intake=None):
    if findings is not None:
        (Path(path) / "findings.json").write_text(json.dumps(findings, indent=1))
    if intake is not None:
        (Path(path) / "intake.json").write_text(json.dumps(intake, indent=1))


def read(path, name="findings.json"):
    return json.loads((Path(path) / name).read_text(encoding="utf-8"))


class ReviewCase:
    """Mixin: builds each base review once per class, then hands every test a private copy."""
    _base = {}

    @classmethod
    def base(cls, key, **kw):
        if key not in ReviewCase._base:
            ReviewCase._base[key] = build_review(Path(tempfile.mkdtemp(prefix="ee-base-")) / "review", **kw)
        return ReviewCase._base[key]

    def copy(self, key="full", **kw):
        dst = Path(tempfile.mkdtemp(prefix="ee-test-")) / "review"
        shutil.copytree(self.base(key, **(kw or {"mode": "full"})), dst)
        self.addCleanup(shutil.rmtree, dst.parent, ignore_errors=True)
        return dst


def area(findings, aid):
    return next(a for a in findings["areas"] if a["id"] == aid)
