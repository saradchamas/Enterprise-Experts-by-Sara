"""The engine-free edition for plugin directories: only what such a directory accepts from an
unverified publisher, and never a reference to a program it does not ship."""
import json
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LITE = ROOT / "directory" / "enterprise-experts-lite"
ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
ALLOWED_NAMES = {"LICENSE"}
MANIFEST_FIELDS = {"name", "version", "description", "author", "homepage", "repository", "license", "keywords", "icon"}
ENGINE = re.compile(r"`EE\b|enterprise_experts\.py|scripts/ee\b|\bEE (?:evidence|score|validate|discover|graph|bench|research)\b")


def files():
    return sorted(p for p in LITE.rglob("*") if p.is_file())


class LiteEdition(unittest.TestCase):
    def test_only_accepted_file_types_and_no_hooks(self):
        for path in files():
            rel = path.relative_to(LITE).as_posix()
            self.assertTrue(path.suffix.lower() in ALLOWED_SUFFIXES or path.name in ALLOWED_NAMES, rel)
            self.assertNotIn(path.name, {"hooks.json", ".mcp.json", ".lsp.json", "monitors.json"}, rel)
            self.assertNotIn("hooks", path.relative_to(LITE).parts, rel)
            self.assertNotIn("scripts", path.relative_to(LITE).parts, rel)

    def test_text_files_are_plain_utf8_without_a_shebang(self):
        for path in files():
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}:
                continue
            data = path.read_bytes()
            self.assertNotIn(b"\x00", data, path.name)
            self.assertFalse(data.startswith(b"#!"), path.name)
            data.decode("utf-8")

    def test_nothing_refers_to_the_engine_as_something_to_run(self):
        for path in files():
            if path.suffix != ".md":
                continue
            text = path.read_text(encoding="utf-8")
            hit = ENGINE.search(text)
            self.assertIsNone(hit, f"{path.relative_to(LITE)}: {hit.group(0) if hit else ''}")

    def test_manifest_has_only_plain_fields(self):
        manifest = json.loads((LITE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertLessEqual(set(manifest), MANIFEST_FIELDS)
        self.assertEqual(manifest["name"], "enterprise-experts-lite")
        self.assertEqual(sorted(p.name for p in (LITE / ".claude-plugin").iterdir()), ["icon.png", "plugin.json"])

    def test_icon_is_a_square_png_of_the_required_size(self):
        data = (LITE / ".claude-plugin" / "icon.png").read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", data[16:24])
        self.assertEqual(width, height)
        self.assertTrue(512 <= width <= 2048)
        self.assertLess(len(data), 2 * 1024 * 1024)

    def test_skill_has_its_frontmatter_and_every_reference_it_names(self):
        skill = LITE / "skills" / "enterprise-experts-lite"
        text = (skill / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---\nname: enterprise-experts-lite\n"))
        description = re.search(r'(?m)^description: "(.*)"$', text).group(1)
        self.assertLessEqual(len(description), 1024)
        for ref in set(re.findall(r"`((?:references|assets)/[\w.-]+\.md)`", text)):
            self.assertTrue((skill / ref).is_file(), ref)

    def test_the_user_is_told_what_this_edition_cannot_check(self):
        skill = LITE / "skills" / "enterprise-experts-lite"
        self.assertIn("not checked by an independent program", (skill / "SKILL.md").read_text(encoding="utf-8"))
        self.assertIn("No independent program validated", (skill / "references" / "evidence-and-scoring.md").read_text(encoding="utf-8"))

    def test_generated_files_match_the_full_skill(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_lite.py"), "--check"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
