"""Tests for pa_notebooklm.client — the explain orchestration with an injected client."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from pa_notebooklm import client as c


def _fake_client():
    """A MagicMock NotebookLMClient with all the async methods _explain uses."""
    cl = MagicMock()
    cl.notebooks.create = AsyncMock(return_value=MagicMock(id="nb1", title="T"))

    def _src(*a, **k):
        return MagicMock(id=f"src-{len(cl.sources.add_url.mock_calls) + len(cl.sources.add_file.mock_calls)}")

    cl.sources.add_url = AsyncMock(side_effect=_src)
    cl.sources.add_file = AsyncMock(side_effect=_src)
    cl.sources.wait_until_ready = AsyncMock()
    cl.artifacts.generate_audio = AsyncMock(return_value=MagicMock(task_id="t-audio"))
    cl.artifacts.generate_video = AsyncMock(return_value=MagicMock(task_id="t-video"))
    cl.artifacts.generate_slide_deck = AsyncMock(return_value=MagicMock(task_id="t-slides"))
    cl.artifacts.generate_report = AsyncMock(return_value=MagicMock(task_id="t-report"))
    cl.artifacts.wait_for_completion = AsyncMock()
    cl.mind_maps.generate = AsyncMock()
    return cl


# --- pure helpers ---

def test_is_url():
    assert c._is_url("https://example.com")
    assert c._is_url("http://x.y")
    assert not c._is_url("/Users/tim/doc.pdf")
    assert not c._is_url("doc.pdf")


def test_derive_title_from_file():
    assert c._derive_title(["/Users/tim/Downloads/AI SDLC Strategy.pdf"]) == "Explainer — AI SDLC Strategy"


def test_derive_title_from_url():
    assert c._derive_title(["https://example.com/papers/foundation-models"]) == "Explainer — foundation-models"


# --- _explain orchestration ---

async def test_creates_notebook_with_explicit_title():
    cl = _fake_client()
    res = await c._explain(cl, ["doc.pdf"], title="My Title")
    cl.notebooks.create.assert_awaited_once_with("My Title")
    assert res["notebook_id"] == "nb1"
    assert res["title"] == "My Title"


async def test_derives_title_when_none():
    cl = _fake_client()
    await c._explain(cl, ["/x/notes.pdf"], title=None)
    cl.notebooks.create.assert_awaited_once_with("Explainer — notes")


async def test_url_uses_add_url_and_file_uses_add_file():
    cl = _fake_client()
    await c._explain(cl, ["https://example.com/a", "/local/b.pdf"])
    cl.sources.add_url.assert_awaited_once()
    cl.sources.add_file.assert_awaited_once()
    assert cl.sources.add_url.await_args.args[1] == "https://example.com/a"


async def test_waits_for_each_source_before_generating():
    cl = _fake_client()
    await c._explain(cl, ["a.pdf", "b.pdf"])
    assert cl.sources.wait_until_ready.await_count == 2


async def test_fires_all_default_artifacts():
    cl = _fake_client()
    res = await c._explain(cl, ["doc.pdf"])
    cl.artifacts.generate_audio.assert_awaited_once()
    cl.artifacts.generate_video.assert_awaited_once()
    cl.artifacts.generate_slide_deck.assert_awaited_once()
    cl.artifacts.generate_report.assert_awaited_once()
    cl.mind_maps.generate.assert_awaited_once()
    assert set(res["artifacts_started"]) == {"audio", "video", "slides", "report", "mindmap"}


async def test_only_subset_honoured():
    cl = _fake_client()
    res = await c._explain(cl, ["doc.pdf"], artifacts={"audio", "mindmap"})
    cl.artifacts.generate_audio.assert_awaited_once()
    cl.mind_maps.generate.assert_awaited_once()
    cl.artifacts.generate_video.assert_not_awaited()
    cl.artifacts.generate_slide_deck.assert_not_awaited()
    cl.artifacts.generate_report.assert_not_awaited()
    assert set(res["artifacts_started"]) == {"audio", "mindmap"}


async def test_wait_false_does_not_wait_for_completion():
    cl = _fake_client()
    res = await c._explain(cl, ["doc.pdf"], wait=False)
    cl.artifacts.wait_for_completion.assert_not_awaited()
    assert res["waited"] is False


async def test_wait_true_calls_wait_for_completion_per_artifact():
    cl = _fake_client()
    res = await c._explain(cl, ["doc.pdf"], artifacts={"audio", "video"}, wait=True)
    assert cl.artifacts.wait_for_completion.await_count == 2
    assert res["waited"] is True


async def test_never_downloads():
    cl = _fake_client()
    await c._explain(cl, ["doc.pdf"])
    cl.artifacts.download_audio.assert_not_called()
    cl.artifacts.download_video.assert_not_called()
    cl.artifacts.download_slide_deck.assert_not_called()


def test_check_auth_false_on_error(monkeypatch):
    async def boom(_fn):
        raise RuntimeError("no cookies")

    monkeypatch.setattr(c, "_with_client", boom)
    assert c.check_auth() is False
