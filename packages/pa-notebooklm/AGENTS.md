# pa-notebooklm — NotebookLM explainers

**Goal: drop documents in, get audio + video + explainers out — to consume on your phone, not read.**

Wraps the **unofficial `notebooklm-py`** library, which drives Google NotebookLM through your
logged-in Google session. Feature availability depends on the configured account and subscription.

Generated artifacts live **inside the NotebookLM notebook** — open the NotebookLM app on your
phone to listen/watch. This package does NOT download anything.

## Setup
1. First-run auth (opens a browser — log into the configured Google account):
   ```bash
   uv run pa-notebooklm login
   ```
   This runs `notebooklm login` under the hood and stores a cookie profile.
   Optionally pin a storage-state file with `NOTEBOOKLM_AUTH_JSON=/path/to/storage_state.json` in `.env`.
2. Verify: `uv run pa-notebooklm list` (should list your notebooks).

## Usage
```bash
# Everything (audio + video + slides + report + mind map) from a file
uv run pa-notebooklm explain ~/Downloads/"Example document.pdf" --title "Example document"

# From a URL, just audio + video
uv run pa-notebooklm explain https://example.com/paper --only audio,video

# Multiple sources into one notebook
uv run pa-notebooklm explain a.pdf b.pdf https://x.y/article

# Block until generations finish (slow — video can take ~30 min)
uv run pa-notebooklm explain doc.pdf --wait

# List notebooks
uv run pa-notebooklm list [--json]
```

Artifacts: `audio` (podcast), `video` (Video Overview), `slides`, `report` (briefing doc), `mindmap`.
Default = all five. Use `--only` to subset.

## Caveats
- `notebooklm-py` uses **undocumented Google APIs** — it can break when Google changes things.
  Treat this as a personal tool, not production. Pin the version in `pyproject.toml`.
- Auth is cookie/session based — re-run `pa-notebooklm login` if the session expires.
- Generation is slow; default is fire-and-forget (`--wait` to block).
