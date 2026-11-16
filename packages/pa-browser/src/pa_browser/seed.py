"""Seed the dedicated automation profile from the user's real Chrome profile.

One-time clone of the session-bearing files (cookies, local/session storage,
saved logins) from the everyday Chrome profile into `~/.pa-chrome/Default`, so
most sites are already logged in without a manual `login` per site.

On macOS the "Chrome Safe Storage" Keychain key is shared per OS user across
profiles, so v10-encrypted cookies copied between profiles on the same machine
decrypt in the automation profile. Sites using device-bound session credentials
(Google, some banks) may not survive the copy — top those up with
`pa-browser login <url>`.

Chrome must be quit for the copy to be clean (the Cookies DB is otherwise locked
/ mid-WAL). Run `pa-browser stop` (and quit the everyday Chrome) first.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from pa_browser.driver import chrome_running, resolve_profile_dir

# Profile-relative files/dirs that hold sessions. Files that don't exist are
# skipped (Chrome versions differ on where Cookies lives — top-level vs Network/).
SEED_ITEMS = [
    "Cookies",
    "Cookies-journal",
    "Network/Cookies",
    "Network/Cookies-journal",
    "Local Storage",
    "Session Storage",
    "Login Data",
    "Login Data For Account",
    "Web Data",
    "IndexedDB",
]
# user-data-dir-relative (not profile-relative) files worth carrying.
TOP_LEVEL_ITEMS = ["Local State"]

_REAL_CHROME_DEFAULT = "~/Library/Application Support/Google/Chrome"


class SeedError(RuntimeError):
    """Raised when the profile clone can't be done safely."""


def real_user_data_dir() -> Path:
    """The everyday Chrome user-data-dir (override $PA_REAL_CHROME_DIR)."""
    return Path(
        os.environ.get("PA_REAL_CHROME_DIR", os.path.expanduser(_REAL_CHROME_DEFAULT))
    )


def detect_source_profile(user_data_dir: Path) -> str:
    """Which profile to clone: `Local State` → profile.last_used, else 'Default'."""
    ls = Path(user_data_dir) / "Local State"
    if ls.exists():
        try:
            data = json.loads(ls.read_text())
            last = data.get("profile", {}).get("last_used")
            if last:
                return last
        except (ValueError, OSError):
            pass
    return "Default"


def _copy_into(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)


def seed_profile(
    *,
    src_user_data_dir: str | os.PathLike | None = None,
    src_profile: str | None = None,
    dest_user_data_dir: str | os.PathLike | None = None,
    force: bool = False,
) -> list[str]:
    """Clone session files from the real Chrome profile into the automation one.

    Returns the list of items copied. Raises SeedError if the automation Chrome
    is running (unless force=True) or the source profile is missing.
    """
    if not force and chrome_running():
        raise SeedError(
            "The automation Chrome is running — run `pa-browser stop` first so the "
            "cookie DB copies cleanly."
        )
    src_root = Path(src_user_data_dir) if src_user_data_dir else real_user_data_dir()
    profile = src_profile or detect_source_profile(src_root)
    src = src_root / profile
    if not src.exists():
        raise SeedError(f"Source Chrome profile not found: {src}")

    dest_root = (
        Path(dest_user_data_dir) if dest_user_data_dir else resolve_profile_dir()
    )
    dest = dest_root / "Default"
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for name in TOP_LEVEL_ITEMS:
        s = src_root / name
        if s.exists():
            _copy_into(s, dest_root / name)
            copied.append(name)
    for rel in SEED_ITEMS:
        s = src / rel
        if s.exists():
            _copy_into(s, dest / rel)
            copied.append(rel)
    return copied
