"""NotebookLM client wrapper — create notebooks from documents and fire explainer generations.

Wraps the unofficial ``notebooklm-py`` library, which drives NotebookLM through the
user's logged-in Google session (their AI Ultra entitlement powers audio/video). The
generated artifacts live inside the NotebookLM notebook — they are consumed in the
NotebookLM app, so this module does NOT download anything.

The core orchestration ``_explain`` takes an injected client so it can be unit-tested
with an AsyncMock (no network / auth).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from pa_core.daily_log import log_event
from pa_core.log import get_logger

logger = get_logger(__name__)

# Everything Tim wants by default.
DEFAULT_ARTIFACTS = ("audio", "video", "slides", "report", "mindmap")

# Rough per-artifact completion timeouts (seconds), only used when wait=True.
_WAIT_TIMEOUTS = {"audio": 1200, "video": 1800, "slides": 600, "report": 600}


def _is_url(source: str) -> bool:
    return source.lower().startswith(("http://", "https://"))


def _derive_title(sources: list[str]) -> str:
    first = sources[0]
    if _is_url(first):
        name = first.rstrip("/").split("/")[-1] or first
    else:
        name = Path(first).stem
    return f"Explainer — {name}"


async def _explain(
    client,
    sources: list[str],
    *,
    title: str | None = None,
    artifacts: set[str] | None = None,
    wait: bool = False,
    language: str = "en",
) -> dict:
    """Create a notebook from ``sources`` and fire the requested artifact generations.

    ``client`` is injected (a real NotebookLMClient, or an AsyncMock in tests).
    Returns a summary dict. Does not download artifacts — they live in the notebook.
    """
    from notebooklm import AudioFormat, MindMapKind, ReportFormat, VideoFormat

    wanted = set(artifacts) if artifacts else set(DEFAULT_ARTIFACTS)
    nb_title = title or _derive_title(sources)

    nb = await client.notebooks.create(nb_title)
    logger.info("Created notebook %s (%s)", nb.id, nb_title)

    added = []
    for src in sources:
        if _is_url(src):
            source = await client.sources.add_url(nb.id, src)
        else:
            source = await client.sources.add_file(nb.id, Path(src))
        added.append(source)

    # Sources must finish processing before artifacts can be generated.
    await asyncio.gather(
        *[client.sources.wait_until_ready(nb.id, s.id) for s in added]
    )

    started: list[str] = []
    pending: list[tuple[str, object]] = []  # (name, GenerationStatus with .task_id)

    if "audio" in wanted:
        st = await client.artifacts.generate_audio(
            nb.id, language=language, audio_format=AudioFormat.DEEP_DIVE
        )
        started.append("audio")
        pending.append(("audio", st))
    if "video" in wanted:
        st = await client.artifacts.generate_video(
            nb.id, language=language, video_format=VideoFormat.EXPLAINER
        )
        started.append("video")
        pending.append(("video", st))
    if "slides" in wanted:
        st = await client.artifacts.generate_slide_deck(nb.id, language=language)
        started.append("slides")
        pending.append(("slides", st))
    if "report" in wanted:
        st = await client.artifacts.generate_report(
            nb.id, report_format=ReportFormat.BRIEFING_DOC, language=language
        )
        started.append("report")
        pending.append(("report", st))
    if "mindmap" in wanted:
        # mind_maps.generate blocks internally when wait=True; pass through our flag.
        await client.mind_maps.generate(
            nb.id, kind=MindMapKind.INTERACTIVE, language=language, wait=wait
        )
        started.append("mindmap")

    waited = False
    if wait:
        for name, st in pending:
            await client.artifacts.wait_for_completion(
                nb.id, st.task_id, timeout=_WAIT_TIMEOUTS.get(name, 600)
            )
        waited = True

    return {
        "notebook_id": nb.id,
        "title": nb_title,
        "artifacts_started": started,
        "waited": waited,
    }


async def _with_client(fn):
    """Build an authenticated client from stored cookies and run ``fn(client)``."""
    from notebooklm import NotebookLMClient

    async with NotebookLMClient.from_storage() as client:
        return await fn(client)


def explain(
    sources: list[str],
    *,
    title: str | None = None,
    artifacts: set[str] | None = None,
    wait: bool = False,
    language: str = "en",
) -> dict:
    """Create a NotebookLM notebook from documents/URLs and generate explainers.

    Args:
        sources: Local file paths and/or http(s) URLs.
        title: Notebook title (derived from the first source if omitted).
        artifacts: Subset of {"audio","video","slides","report","mindmap"} (default: all).
        wait: Block until generations complete (slow — video can take ~30 min).
        language: Generation language (default "en").
    """
    result = asyncio.run(
        _with_client(
            lambda c: _explain(
                c, sources, title=title, artifacts=artifacts, wait=wait, language=language
            )
        )
    )
    log_event(
        "info",
        "generated",
        f"NotebookLM explainer: {result['title']} ({', '.join(result['artifacts_started'])})",
        details={"notebook_id": result["notebook_id"], "artifacts": result["artifacts_started"]},
    )
    return result


def list_notebooks() -> list[dict]:
    """List the user's NotebookLM notebooks."""

    async def _fn(client):
        nbs = await client.notebooks.list()
        return [{"id": n.id, "title": n.title, "sources": n.sources_count} for n in nbs]

    return asyncio.run(_with_client(_fn))


def check_auth() -> bool:
    """Return True if the stored NotebookLM session is valid, False otherwise."""

    async def _fn(client):
        await client.notebooks.list()
        return True

    try:
        return asyncio.run(_with_client(_fn))
    except Exception as e:  # noqa: BLE001 — any failure means "not authed"
        logger.warning("NotebookLM auth check failed: %s", e)
        return False
