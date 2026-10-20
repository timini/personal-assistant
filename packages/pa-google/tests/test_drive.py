"""Tests for Google Drive backup uploads."""

import subprocess
from pathlib import Path
from unittest.mock import patch

from pa_google.drive import upload_file


@patch("pa_google.drive.run_cli")
def test_upload_runs_from_file_directory(mock_run_cli):
    """gws 0.22+ only accepts upload paths inside its working directory."""
    mock_run_cli.return_value = subprocess.CompletedProcess(
        args=[], returncode=0, stdout='{"id": "drive-file"}', stderr=""
    )
    archive = Path("/tmp/pa-backups/pa-backup.tar.gz")

    upload_file(archive, "folder-id", archive.name)

    command = mock_run_cli.call_args.args[0]
    assert command[-2:] == ["--upload", archive.name]
    assert mock_run_cli.call_args.kwargs["cwd"] == archive.parent


def test_backup_includes_memory_store(tmp_path, monkeypatch):
    import tarfile

    from pa_google import drive

    (tmp_path / "private" / "memory" / "entries").mkdir(parents=True)
    (tmp_path / "private" / "memory" / "entries" / "a.md").write_text("---\nname: a\n---\n")
    (tmp_path / "private" / "health-preferences.md").write_text("prefs")
    (tmp_path / "private" / "big.pdf").write_text("not backed up")
    monkeypatch.setattr(drive, "PA_ROOT", tmp_path)
    monkeypatch.setattr(drive.tempfile, "gettempdir", lambda: str(tmp_path))

    with tarfile.open(drive.create_backup_tarball()) as tar:
        names = tar.getnames()
    assert "private/memory/entries/a.md" in names
    assert "private/health-preferences.md" in names
    assert "private/big.pdf" not in names
