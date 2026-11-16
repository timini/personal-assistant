"""Tests for pa_browser.seed — cloning session files from the real Chrome profile
into the dedicated automation profile. Pure filesystem work against tmp dirs, so
no real Chrome is needed.
"""

import json

import pytest

from pa_browser import seed


def _make_source(root, profile="Default", *, with_cookies=True):
    """Build a fake Chrome user-data-dir with a profile holding session files."""
    (root / profile).mkdir(parents=True)
    (root / "Local State").write_text(json.dumps({"profile": {"last_used": profile}}))
    if with_cookies:
        (root / profile / "Cookies").write_text("cookie-db")
        (root / profile / "Network").mkdir()
        (root / profile / "Network" / "Cookies").write_text("network-cookie-db")
        (root / profile / "Local Storage").mkdir()
        (root / profile / "Local Storage" / "leveldb").mkdir()
        (root / profile / "Local Storage" / "leveldb" / "0.log").write_text("ls")
        (root / profile / "Login Data").write_text("logins")
    return root


def test_seed_copies_allowlisted_files(tmp_path):
    src = _make_source(tmp_path / "real")
    dest_root = tmp_path / "pa-chrome"
    copied = seed.seed_profile(
        src_user_data_dir=src, dest_user_data_dir=dest_root, force=True
    )
    dest = dest_root / "Default"
    assert (dest / "Cookies").read_text() == "cookie-db"
    assert (dest / "Network" / "Cookies").read_text() == "network-cookie-db"
    assert (dest / "Local Storage" / "leveldb" / "0.log").read_text() == "ls"
    assert (dest / "Login Data").read_text() == "logins"
    assert (dest_root / "Local State").exists()  # top-level file copied too
    assert "Cookies" in copied


def test_seed_autodetects_source_profile_from_local_state(tmp_path):
    # last_used points at "Profile 2", not Default
    src = _make_source(tmp_path / "real", profile="Profile 2")
    (src / "Default").mkdir()  # a Default exists but is empty / stale
    dest_root = tmp_path / "pa-chrome"
    seed.seed_profile(src_user_data_dir=src, dest_user_data_dir=dest_root, force=True)
    assert (dest_root / "Default" / "Cookies").read_text() == "cookie-db"


def test_detect_source_profile_falls_back_to_default(tmp_path):
    (tmp_path / "Default").mkdir()
    assert seed.detect_source_profile(tmp_path) == "Default"


def test_seed_is_idempotent(tmp_path):
    src = _make_source(tmp_path / "real")
    dest_root = tmp_path / "pa-chrome"
    seed.seed_profile(src_user_data_dir=src, dest_user_data_dir=dest_root, force=True)
    # second run must not raise and must leave the copy intact
    seed.seed_profile(src_user_data_dir=src, dest_user_data_dir=dest_root, force=True)
    assert (dest_root / "Default" / "Cookies").read_text() == "cookie-db"


def test_seed_refuses_when_automation_chrome_running(tmp_path, monkeypatch):
    src = _make_source(tmp_path / "real")
    monkeypatch.setattr(seed, "chrome_running", lambda *a, **k: True)
    with pytest.raises(seed.SeedError):
        seed.seed_profile(
            src_user_data_dir=src, dest_user_data_dir=tmp_path / "pa-chrome"
        )


def test_seed_missing_source_raises(tmp_path):
    with pytest.raises(seed.SeedError):
        seed.seed_profile(
            src_user_data_dir=tmp_path / "nope",
            dest_user_data_dir=tmp_path / "pa-chrome",
            force=True,
        )
