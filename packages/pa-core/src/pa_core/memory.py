"""Shared assistant memory: one plain-file store that Codex and Claude both use.

Layout (default `private/memory/`, gitignored):

    entries/<name>.md     one durable fact per file, YAML frontmatter + body
    archive/<name>.md     superseded entries and closed loops, kept for history
    journal/YYYY-MM.md    dated one-line notes of what happened

Entry types:

    preference  how the user wants things done
    lesson      a mistake or tool quirk, and what to do instead
    person      who someone is and how to deal with them
    fact        stable facts: places, accounts, where things live
    project     current state of an ongoing piece of work
    loop        an open commitment the assistant must follow up, with a due date

`render_brief()` is the session-start pack: due loops first, then rules,
lessons, people, facts, projects and the recent journal.
"""

from __future__ import annotations

import datetime
import difflib
import os
import re
from pathlib import Path

import yaml

TYPES = ("preference", "lesson", "person", "fact", "project", "loop")

# Order and headings used in the brief.
_BRIEF_SECTIONS = (
    ("preference", "Rules and preferences"),
    ("lesson", "Lessons"),
    ("person", "People"),
    ("fact", "Facts"),
    ("project", "Projects"),
)

STALE_LOOP_DAYS = 14
_UNSET = object()


def memory_dir() -> Path:
    """Store location: $PA_MEMORY_DIR, else user.yaml `memory_dir`, else private/memory."""
    from pa_core.config import PA_ROOT

    env = os.environ.get("PA_MEMORY_DIR")
    if env:
        return Path(env).expanduser()
    try:
        from pa_core.config import get_user_config

        configured = get_user_config().get("memory_dir")
    except (FileNotFoundError, AttributeError):
        configured = None
    if configured:
        path = Path(configured).expanduser()
        return path if path.is_absolute() else PA_ROOT / path
    return PA_ROOT / "private" / "memory"


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise ValueError(f"Cannot make a name from {name!r}")
    return slug


def _today() -> str:
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _read(path: Path) -> dict:
    text = path.read_text()
    meta, body = {}, text
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            meta = yaml.safe_load(text[4:end]) or {}
            body = text[end + 4:]
    meta = {k: (v.isoformat() if isinstance(v, datetime.date) else v) for k, v in meta.items()}
    meta["body"] = body.strip()
    meta.setdefault("name", path.stem)
    meta.setdefault("tags", [])
    return meta


def _write(path: Path, entry: dict) -> None:
    meta = {k: v for k, v in entry.items() if k != "body" and v not in (None, [], "")}
    path.parent.mkdir(parents=True, exist_ok=True)
    front = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=1000)
    body = entry.get("body") or ""
    path.write_text(f"---\n{front}---\n\n{body}\n" if body else f"---\n{front}---\n")


def _entry_path(name: str) -> Path:
    return memory_dir() / "entries" / f"{name}.md"


# ---------------------------------------------------------------------------
# Entries
# ---------------------------------------------------------------------------

def add(
    type: str,
    name: str,
    summary: str,
    body: str | None = None,
    tags: list[str] | tuple[str, ...] = (),
    due: str | None = None,
    source: str | None = None,
    today: str | None = None,
) -> dict:
    """Create or update an entry. Updating keeps `created` and any field not given."""
    if type not in TYPES:
        raise ValueError(f"Unknown type {type!r}. Use one of: {', '.join(TYPES)}")
    if not summary or not summary.strip():
        raise ValueError("A one-line summary is required")
    slug = slugify(name)
    today = today or _today()
    existing = get(slug) or {}
    if type == "loop" and not (due or existing.get("due")):
        raise ValueError("A loop needs a due date (the day to next check it)")

    entry = {
        "name": slug,
        "type": type,
        "summary": summary.strip(),
        "tags": list(tags) or existing.get("tags", []),
        "due": due or existing.get("due"),
        "source": source or existing.get("source"),
        "status": "active",
        "created": existing.get("created", today),
        "updated": today,
        "body": body if body is not None else existing.get("body", ""),
    }
    _write(_entry_path(slug), entry)
    return entry


def update(
    name: str,
    summary: str | None = None,
    append: str | None = None,
    due: str | None = None,
    tags: list[str] | tuple[str, ...] | None = None,
    today: str | None = None,
) -> dict:
    """Change only the given fields of an existing entry. `append` adds a dated paragraph."""
    entry = get(name)
    if entry is None:
        raise KeyError(f"No memory entry named {name!r}")
    today = today or _today()
    if summary and summary.strip():
        entry["summary"] = summary.strip()
    if due:
        entry["due"] = due
    if tags:
        entry["tags"] = list(tags)
    if append and append.strip():
        note = f"{today}: {append.strip()}"
        entry["body"] = f"{entry['body']}\n\n{note}" if entry.get("body") else note
    entry["updated"] = today
    _write(_entry_path(entry["name"]), entry)
    return entry


def get(name: str) -> dict | None:
    path = _entry_path(slugify(name))
    return _read(path) if path.exists() else None


def list_entries(type: str | None = None) -> list[dict]:
    folder = memory_dir() / "entries"
    if not folder.exists():
        return []
    entries = [_read(p) for p in sorted(folder.glob("*.md"))]
    return [e for e in entries if type is None or e.get("type") == type]


def archive(name: str, reason: str, today: str | None = None, status: str = "archived") -> dict:
    """Move an entry out of the active set, recording why. Nothing is deleted."""
    slug = slugify(name)
    entry = get(slug)
    if entry is None:
        raise KeyError(f"No memory entry named {slug!r}")
    today = today or _today()
    entry["status"] = status
    entry["updated"] = today
    note = f"{status.capitalize()} {today}: {reason}"
    entry["body"] = f"{entry['body']}\n\n{note}".strip()
    _write(memory_dir() / "archive" / f"{slug}.md", entry)
    _entry_path(slug).unlink()
    return entry


# ---------------------------------------------------------------------------
# Loops: open commitments with a next-check date
# ---------------------------------------------------------------------------

def due_loops(today: str | None = None) -> list[dict]:
    today = today or _today()
    loops = [e for e in list_entries("loop") if str(e.get("due", "")) <= today]
    return sorted(loops, key=lambda e: str(e.get("due", "")))


def upcoming_loops(today: str | None = None, days: int = 7) -> list[dict]:
    today = today or _today()
    horizon = (datetime.date.fromisoformat(today) + datetime.timedelta(days=days)).isoformat()
    loops = [e for e in list_entries("loop") if today < str(e.get("due", "")) <= horizon]
    return sorted(loops, key=lambda e: str(e.get("due", "")))


def close_loop(name: str, outcome: str, today: str | None = None) -> dict:
    entry = get(name)
    if entry is None:
        raise KeyError(f"No memory entry named {slugify(name)!r}")
    if entry.get("type") != "loop":
        raise ValueError(f"{entry['name']} is a {entry.get('type')}, not a loop")
    today = today or _today()
    closed = archive(name, outcome, today=today, status="done")
    journal(f"Closed loop {closed['name']}: {outcome}", now=f"{today} {datetime.datetime.now():%H:%M}")
    return closed


# ---------------------------------------------------------------------------
# Journal: what happened, one dated line per note
# ---------------------------------------------------------------------------

def journal(text: str, now: str | None = None) -> str:
    stamp = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- {stamp} {' '.join(text.split())}"
    path = memory_dir() / "journal" / f"{stamp[:7]}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(line + "\n")
    return line


def _journal_lines() -> list[str]:
    folder = memory_dir() / "journal"
    if not folder.exists():
        return []
    lines: list[str] = []
    for path in sorted(folder.glob("*.md")):
        lines += [l for l in path.read_text().splitlines() if l.startswith("- ")]
    return lines


def recent_journal(today: str | None = None, days: int = 3) -> list[str]:
    today = today or _today()
    start = (datetime.date.fromisoformat(today) - datetime.timedelta(days=days - 1)).isoformat()
    return [l for l in _journal_lines() if start <= l[2:12] <= today]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _terms(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 1]


def search(query: str, limit: int = 10) -> list[dict]:
    """Keyword search over entries (name and summary weigh most) and the journal."""
    terms = _terms(query)
    if not terms:
        return []
    results = []
    for entry in list_entries():
        fields = (
            (entry["name"].replace("-", " "), 3),
            (entry.get("summary", ""), 3),
            (" ".join(entry.get("tags") or []), 2),
            (entry.get("body", ""), 1),
        )
        score = sum(weight for term in terms for text, weight in fields if term in text.lower())
        if score:
            results.append({**entry, "score": score})
    for line in _journal_lines():
        score = sum(1 for term in terms if term in line.lower())
        if score:
            results.append({"type": "journal", "name": line[2:18], "summary": line[19:], "score": score})
    results.sort(key=lambda r: (-r["score"], r["type"] == "journal"))
    return results[:limit]


# ---------------------------------------------------------------------------
# Session brief
# ---------------------------------------------------------------------------

def _checked_in_today(today: str) -> str | None:
    """Time of today's wellness check-in from the daily log, if any."""
    try:
        from pa_core.daily_log import get_events
    except ImportError:  # pragma: no cover
        return None
    for event in get_events(today):
        if event.get("category") == "wellness" and event.get("action") == "check_in":
            return event.get("timestamp", "")[11:16]
    return None


def _last_triage() -> dict | None:
    """The cursor `pa-google emails --mark-triaged` saves: {epoch, display}."""
    from pa_core.state import get_state
    return get_state("last_email_triage")


def _triaged_today(today: str, last=_UNSET) -> str | None:
    """Time (HH:MM, user's time zone) of today's email triage, if it has happened."""
    import zoneinfo

    from pa_core.config import get_user_config
    if last is _UNSET:
        last = _last_triage()
    if not isinstance(last, dict) or not last.get("epoch"):
        return None
    tz = zoneinfo.ZoneInfo(get_user_config().get("timezone", "Europe/London"))
    when = datetime.datetime.fromtimestamp(last["epoch"], tz)
    return when.strftime("%H:%M") if when.date().isoformat() == today else None


def _training_summary(today: str) -> str | None:
    """The training log's one-line summary; None if the log cannot be read."""
    try:
        from pa_core.training import brief_line
        return brief_line(today)
    except Exception:
        return None


def render_brief(today: str | None = None, checked_in=_UNSET, triaged=_UNSET) -> str:
    """Compact session-start context. Empty string when the store is empty."""
    today = today or _today()
    entries = list_entries()
    if not entries and not recent_journal(today):
        return ""
    if checked_in is _UNSET:
        checked_in = _checked_in_today(today)

    lines = ["## Memory brief", ""]
    lines.append(f"Check-in: done today at {checked_in}" if checked_in else "Check-in: not yet today")
    if triaged is _UNSET:
        triaged = _triaged_today(today)
    lines.append(f"Email triage: done today at {triaged}" if triaged else
                 "Email triage: not yet today. Load the email-triage skill before planning the day.")
    exercise = _training_summary(today)
    if exercise:
        lines.append(exercise)
    lines.append("")

    due = due_loops(today)
    lines.append("### Due now (act on these first)")
    lines += [f"- {e['name']}: {e['summary']} (due {e['due']})" for e in due] or ["- none"]
    upcoming = upcoming_loops(today)
    if upcoming:
        lines += ["", "### Coming up"]
        lines += [f"- {e['name']}: {e['summary']} (due {e['due']})" for e in upcoming]

    for type_, heading in _BRIEF_SECTIONS:
        group = [e for e in entries if e.get("type") == type_]
        if group:
            lines += ["", f"### {heading}"]
            lines += [f"- {e['name']}: {e['summary']}" for e in group]

    recent = recent_journal(today)
    if recent:
        lines += ["", "### Recent journal"] + recent

    lines += ["", "Details: `uv run pa-core memory show <name>`. "
              "Search: `uv run pa-core memory search <terms>`."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Hygiene
# ---------------------------------------------------------------------------

def lint(today: str | None = None) -> list[str]:
    """Problems worth fixing: stale loops, loops without dates, near-duplicate entries."""
    today = today or _today()
    stale_before = (datetime.date.fromisoformat(today) - datetime.timedelta(days=STALE_LOOP_DAYS)).isoformat()
    issues = []
    entries = list_entries()
    for e in entries:
        if e.get("type") == "loop":
            due = str(e.get("due") or "")
            if not due:
                issues.append(f"{e['name']}: loop has no due date")
            elif due < stale_before:
                issues.append(f"{e['name']}: loop overdue since {due}; close it or set a new date")
    for i, a in enumerate(entries):
        for b in entries[i + 1:]:
            if a.get("type") != b.get("type"):
                continue
            ratio = difflib.SequenceMatcher(None, a["summary"].lower(), b["summary"].lower()).ratio()
            if ratio >= 0.9:
                issues.append(f"{a['name']} and {b['name']}: near-duplicate; merge or archive one")
    return issues


# ---------------------------------------------------------------------------
# Import from Claude Code auto-memory
# ---------------------------------------------------------------------------

_CLAUDE_TYPES = {"user": "fact", "feedback": "preference", "project": "project", "reference": "fact"}


def import_claude_memory(src: Path, today: str | None = None) -> int:
    """Copy Claude Code memory files (frontmatter: name, description, type) into the store."""
    count = 0
    for path in sorted(Path(src).glob("*.md")):
        if path.name == "MEMORY.md":
            continue
        meta = _read(path)
        kind = meta.get("type") or (meta.get("metadata") or {}).get("type") or "fact"
        add(
            _CLAUDE_TYPES.get(kind, "fact"),
            meta.get("name") or path.stem,
            meta.get("description") or meta["body"].splitlines()[0],
            body=meta["body"],
            source="claude-memory",
            today=today,
        )
        count += 1
    return count
