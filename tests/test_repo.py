"""Repo rules: the skill stays within the Agent Skills limits, the config template and permissions
are well-formed, keys and data stay out of git, every Python file compiles, links resolve, and the
docs follow the house style. Offline; standard library plus PyYAML.

    python3 -m unittest discover -s tests -v
"""
import glob
import json
import os
import py_compile
import re
import subprocess
import sys
import unittest

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
SKILL_DIR = os.path.join(ROOT, ".claude", "skills", "creator-sourcing-youtube")
SKILL = os.path.join(SKILL_DIR, "SKILL.md")
DOCS = ["README.md", "SECURITY.md", "CONTRIBUTING.md", "CHANGELOG.md", "CLAUDE.md"] + sorted(
    os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, "docs", "*.md")))
SPEC_SKILL_LINES = 500          # Agent Skills spec: keep SKILL.md under 500 lines
SPEC_DESCRIPTION_CHARS = 1024   # Agent Skills spec: description max length


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return yaml.safe_load(m.group(1)) if m else None


class Skill(unittest.TestCase):
    def test_frontmatter(self):
        fm = frontmatter(read(SKILL))
        self.assertIsNotNone(fm, "SKILL.md needs YAML frontmatter")
        self.assertEqual(fm.get("name"), "creator-sourcing-youtube")
        self.assertTrue(fm.get("description"))
        self.assertLessEqual(len(fm["description"]), SPEC_DESCRIPTION_CHARS)

    def test_size(self):
        n = read(os.path.relpath(SKILL, ROOT)).count("\n")
        self.assertLess(n, SPEC_SKILL_LINES, "SKILL.md has %d lines: move detail into references/" % n)

    def test_references_exist(self):
        text = read(SKILL)
        for ref in sorted(set(re.findall(r"references/[\w.-]+\.md", text))):
            self.assertTrue(os.path.exists(os.path.join(SKILL_DIR, ref)), "missing %s" % ref)


class Config(unittest.TestCase):
    def test_template_parses_and_loads(self):
        cfg = yaml.safe_load(read("config/_template.yml"))
        for key in ("company", "website", "geo", "band", "format_focus", "lanes", "core_rx", "domain_rx", "seeds", "caps"):
            self.assertIn(key, cfg)
        self.assertIn("audience_target", cfg["geo"])
        from engine import filters
        filters.Cfg(os.path.join(ROOT, "config", "_template.yml"))  # every pattern compiles

    def test_env_example_has_empty_keys(self):
        lines = [l for l in read(".env.example").splitlines() if l and not l.startswith("#")]
        self.assertEqual(sorted(l.split("=")[0] for l in lines), ["SCRAPECREATORS_API_KEY", "SERPER_API_KEY", "YOUTUBE_API_KEY"])
        self.assertTrue(all(l.endswith("=") for l in lines), ".env.example must not carry values")


class Safety(unittest.TestCase):
    def test_settings_block_the_key_file(self):
        s = json.loads(read(".claude/settings.json"))["permissions"]
        for rule in ("Read(**/.env)", "Edit(**/.env)"):
            self.assertIn(rule, s["deny"])
        self.assertFalse(any("set_key" in r for r in s["allow"]), "Claude must never be allowed to run set_key.py")

    def test_data_is_git_ignored(self):
        if subprocess.run(["git", "rev-parse"], cwd=ROOT, capture_output=True).returncode:
            self.skipTest("not a git checkout")
        paths = [".env", ".leak-patterns.local", "config/acme.yml", "crm", "out", "state", "seeds", "brand",
                 "stage5/acme", "calibration/acme-2026-01-01.html", ".venv"]
        out = subprocess.run(["git", "check-ignore", "--no-index"] + paths, cwd=ROOT, capture_output=True, text=True).stdout.split()
        self.assertEqual(sorted(out), sorted(paths), "not ignored: %s" % sorted(set(paths) - set(out)))
        tracked = subprocess.run(["git", "check-ignore", "--no-index", "config/_template.yml", "stage5/_template_build.py",
                                  "calibration/template.html"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        self.assertEqual(tracked, [], "templates must stay tracked")

    def test_scripts_are_executable(self):
        for f in ("setup.sh", "run_brand.sh", "scripts/leak-scan.sh"):
            self.assertTrue(os.access(os.path.join(ROOT, f), os.X_OK), "%s is not executable" % f)


class Code(unittest.TestCase):
    def test_python_compiles(self):
        for p in glob.glob(os.path.join(ROOT, "**", "*.py"), recursive=True):
            rel = os.path.relpath(p, ROOT)
            if rel.startswith(".venv") or (rel.startswith("stage5" + os.sep) and rel != os.path.join("stage5", "_template_build.py")):
                continue  # the environment, and per-brand builders (git-ignored data)
            py_compile.compile(p, doraise=True)


class Docs(unittest.TestCase):
    def test_local_links_resolve(self):
        for rel in DOCS + [os.path.relpath(SKILL, ROOT)]:
            for target in re.findall(r"\]\(([^)#\s]+)(?:#[^)]*)?\)", read(rel)):
                if re.match(r"[a-z]+:", target) or target.startswith("../../"):
                    continue
                path = os.path.normpath(os.path.join(ROOT, os.path.dirname(rel), target))
                self.assertTrue(os.path.exists(path), "%s links to missing %s" % (rel, target))

    def test_house_style(self):
        for rel in DOCS + [os.path.relpath(SKILL, ROOT)]:
            text = read(rel)
            self.assertNotIn("—", text, "%s: use a spaced hyphen, not an em dash" % rel)


if __name__ == "__main__":
    unittest.main()
