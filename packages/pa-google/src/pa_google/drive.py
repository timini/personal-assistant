"""Google Drive backup for personal/gitignored PA files."""

import json
import tarfile
import tempfile
from datetime import date
from pathlib import Path

import yaml

from pa_core.cli_runner import run_cli, run_gws, parse_json_output
from pa_core.config import PA_ROOT


# Files and dirs to back up (relative to PA_ROOT)
BACKUP_PATHS = [
    ".env",
    "user.yaml",
    "user-instructions.md",
    "activity",
]
# Glob patterns to match (relative to PA_ROOT)
BACKUP_GLOBS = [
    "client_secret_*.json",
]

BACKUP_FOLDER_NAME = "PA-Backups"


def create_backup_tarball() -> Path:
    """Create .tar.gz of personal files in tempdir. Returns tarball path."""
    filename = f"pa-backup-{date.today().isoformat()}.tar.gz"
    tarball_path = Path(tempfile.gettempdir()) / filename

    with tarfile.open(tarball_path, "w:gz") as tar:
        # Add fixed paths
        for rel in BACKUP_PATHS:
            full = PA_ROOT / rel
            if full.exists():
                tar.add(str(full), arcname=rel)

        # Add glob matches
        for pattern in BACKUP_GLOBS:
            for match in PA_ROOT.glob(pattern):
                tar.add(str(match), arcname=match.relative_to(PA_ROOT))

    return tarball_path


def _load_user_yaml() -> dict:
    path = PA_ROOT / "user.yaml"
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_user_yaml(data: dict) -> None:
    path = PA_ROOT / "user.yaml"
    with open(path, "w") as f:
        yaml.safe_dump(data, f, default_flow_style=False)


def ensure_backup_folder() -> str:
    """Get or create PA-Backups folder on Drive. Caches ID in user.yaml."""
    # Check cached ID
    config = _load_user_yaml()
    folder_id = config.get("backup", {}).get("drive_folder_id")
    if folder_id:
        return folder_id

    # Search for existing folder
    result = run_gws(
        "drive", "files", "list",
        {
            "q": f"name='{BACKUP_FOLDER_NAME}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            "spaces": "drive",
            "fields": "files(id,name)",
        },
    )
    files = result.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        # Create folder
        created = run_gws(
            "drive", "files", "create",
            body={
                "name": BACKUP_FOLDER_NAME,
                "mimeType": "application/vnd.google-apps.folder",
            },
        )
        folder_id = created["id"]

    # Cache in user.yaml
    config.setdefault("backup", {})["drive_folder_id"] = folder_id
    _save_user_yaml(config)
    return folder_id


def upload_file(file_path: Path, folder_id: str, filename: str) -> dict:
    """Upload file to Drive folder using gws drive files create --upload."""
    result = run_cli([
        "gws", "drive", "files", "create",
        "--params", json.dumps({"name": filename, "parents": [folder_id]}),
        "--upload", str(file_path),
    ])
    return parse_json_output(result)


def cleanup_old_backups(folder_id: str, keep: int = 7) -> list[str]:
    """List backups in folder, delete all but most recent `keep`."""
    result = run_gws(
        "drive", "files", "list",
        {
            "q": f"'{folder_id}' in parents and name contains 'pa-backup-' and trashed=false",
            "fields": "files(id,name)",
            "orderBy": "name desc",
            "pageSize": 100,
        },
    )
    files = result.get("files", [])
    deleted = []
    for f in files[keep:]:
        run_cli(
            ["gws", "drive", "files", "delete", "--params", json.dumps({"fileId": f["id"]})],
            check=False,
        )
        deleted.append(f["name"])
    return deleted


def run_backup(keep: int = 7) -> dict:
    """Full pipeline: tarball -> upload -> cleanup -> delete temp."""
    tarball = create_backup_tarball()
    try:
        folder_id = ensure_backup_folder()
        upload_file(tarball, folder_id, tarball.name)
        deleted = cleanup_old_backups(folder_id, keep=keep)
    finally:
        tarball.unlink(missing_ok=True)
    return {"filename": tarball.name, "deleted": deleted}
