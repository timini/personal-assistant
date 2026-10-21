"""Repo skills are shared by Claude Code (.claude/skills) and Codex (.agents/skills symlinks)."""

import importlib
import re
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
SKILLS = ROOT / ".claude" / "skills"
EXPECTED = {"email-triage", "daily-checkin", "task-hygiene", "research-doc", "visual-report"}
CLIS = {"pa-core": "pa_core.cli", "pa-google": "pa_google.cli", "pa-notion": "pa_notion.cli",
        "pa-health": "pa_health.cli"}


def _skill_dirs():
    return sorted(p for p in SKILLS.iterdir() if p.is_dir()) if SKILLS.exists() else []


def _frontmatter(text: str) -> dict:
    match = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must start with --- frontmatter ---"
    return dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)


def test_expected_skills_exist():
    assert {p.name for p in _skill_dirs()} == EXPECTED


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_frontmatter_names_the_skill_and_describes_it(skill):
    meta = _frontmatter((SKILLS / skill / "SKILL.md").read_text())
    assert meta["name"].strip() == skill
    assert len(meta["description"].strip()) > 40


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_codex_symlink_resolves_to_the_same_skill(skill):
    link = ROOT / ".agents" / "skills" / skill
    assert link.is_symlink()
    assert (link / "SKILL.md").resolve() == (SKILLS / skill / "SKILL.md").resolve()


def _commands(text: str):
    """Yield the subcommand words of every `pa-x ...` command mentioned in a skill."""
    for match in re.finditer(r"\b(pa-(?:core|google|notion|health))((?: [a-z][a-z-]*)+)", text):
        yield match.group(1), match.group(2).split()


@pytest.mark.parametrize("skill", sorted(EXPECTED))
def test_every_cli_command_in_a_skill_exists(skill):
    text = (SKILLS / skill / "SKILL.md").read_text()
    for cli, words in _commands(text):
        main = importlib.import_module(CLIS[cli]).main
        # Keep only leading words that parse as subcommands; stop at the first that is not.
        valid = []
        for word in words:
            with patch("sys.argv", [cli, *valid, word, "--help"]), \
                 patch("sys.stdout"), patch("sys.stderr"):
                try:
                    main()
                except SystemExit as exc:
                    if exc.code != 0:
                        break
            valid.append(word)
        assert valid, f"{skill}: `{cli} {' '.join(words)}` is not a {cli} command"


def test_no_instructions_md_stubs_remain():
    assert not list((ROOT / "packages").glob("*/INSTRUCTIONS.md"))


@pytest.mark.parametrize("path", ["private/memory/entries/x.md", "private/drafts/x.txt",
                                  "activity/reports/x/x.html", "activity/daily/x.jsonl",
                                  "activity/.state.json"])
def test_cli_managed_paths_are_ignored(path):
    """AGENTS.md lets agents skip git check-ignore for these; keep that true."""
    result = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT)
    assert result.returncode == 0, f"{path} is not ignored by git"


@pytest.mark.parametrize("skill", sorted(EXPECTED - {"email-triage"}))
def test_other_skills_point_to_email_triage(skill):
    assert "email-triage" in (SKILLS / skill / "SKILL.md").read_text()


def test_morning_checkin_triages_email():
    text = (SKILLS / "daily-checkin" / "SKILL.md").read_text()
    morning = text.split("## Morning", 1)[1].split("## Evening", 1)[0]
    assert "email-triage" in morning
