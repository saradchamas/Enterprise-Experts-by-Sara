#!/usr/bin/env python3
"""Build the release artifacts into dist/: the installable skill archive, an SBOM and checksums.

  python tools/build_release.py            # build
  python tools/build_release.py --verify   # build, then re-check the checksums and archive contents

Deterministic: file order, timestamps and permissions are fixed, so the same commit
always produces the same archive and the same checksum.
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills" / "enterprise-experts"
DIST = REPO / "dist"
FIXED_TIME = (2020, 1, 1, 0, 0, 0)


def version():
    text = (SKILL / "scripts" / "ee" / "__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__ = "([^"]+)"', text).group(1)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def skill_files():
    return sorted(p for p in SKILL.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")


def build():
    v = version()
    DIST.mkdir(exist_ok=True)
    for old in DIST.iterdir():
        old.unlink()
    archive = DIST / "enterprise-experts.skill"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in skill_files():
            info = zipfile.ZipInfo(f"enterprise-experts/{path.relative_to(SKILL).as_posix()}", FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, path.read_bytes())
    sbom = {
        "bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
        "metadata": {"component": {"type": "application", "name": "enterprise-experts", "version": v,
                                   "description": "Claude skill with a dependency-free Python engine"}},
        # The engine imports only the Python standard library (enforced by a test), so there are
        # no third-party runtime components. Each shipped file is listed with its hash instead.
        "components": [{"type": "file", "name": p.relative_to(REPO).as_posix(),
                        "hashes": [{"alg": "SHA-256", "content": sha256(p)}]} for p in skill_files()],
    }
    (DIST / "sbom.cdx.json").write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    names = ["enterprise-experts.skill", "sbom.cdx.json"]
    (DIST / "SHA256SUMS").write_text("".join(f"{sha256(DIST / n)}  {n}\n" for n in names), encoding="utf-8")
    return v, archive


def verify():
    problems = []
    for line in (DIST / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if sha256(DIST / name) != digest:
            problems.append(f"checksum mismatch: {name}")
    with zipfile.ZipFile(DIST / "enterprise-experts.skill") as z:
        if z.testzip():
            problems.append("archive is corrupt")
        names = set(z.namelist())
        expected = {f"enterprise-experts/{p.relative_to(SKILL).as_posix()}" for p in skill_files()}
        if names != expected:
            problems.append(f"archive contents differ from the skill folder: {sorted(names ^ expected)[:5]}")
        if "enterprise-experts/SKILL.md" not in names:
            problems.append("SKILL.md is missing from the archive")
    return problems


if __name__ == "__main__":
    v, archive = build()
    print(f"built {archive.relative_to(REPO)} for version {v}")
    print((DIST / "SHA256SUMS").read_text(), end="")
    if "--verify" in sys.argv:
        problems = verify()
        for p in problems:
            print("FAIL:", p)
        sys.exit(1 if problems else 0)
