"""Private Drive publication and HTML-email delivery for PA reports."""
from __future__ import annotations

import base64
import json
from email.message import EmailMessage
from pathlib import Path

from playwright.sync_api import sync_playwright

from pa_core.cli_runner import parse_json_output, run_cli, run_gws
from pa_core.config import get_user_config
from pa_google.drive import _load_user_yaml, _save_user_yaml


def _find_or_create_folder(name: str, parent_id: str | None = None) -> str:
    parent = f" and '{parent_id}' in parents" if parent_id else ""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false{parent}"
    found = run_gws("drive", "files", "list", {"q": query, "spaces": "drive", "fields": "files(id,name)"}).get("files", [])
    if found:
        return found[0]["id"]
    body = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id: body["parents"] = [parent_id]
    return run_gws("drive", "files", "create", body=body)["id"]


def ensure_reports_folder() -> str:
    config = _load_user_yaml()
    cached = config.get("reports", {}).get("drive_folder_id")
    if cached:
        return cached
    root = _find_or_create_folder("PA")
    folder_id = _find_or_create_folder("Reports", root)
    config.setdefault("reports", {})["drive_folder_id"] = folder_id
    config["reports"].setdefault("insights_enabled", True)
    config["reports"].setdefault("llm_model", "sonnet")
    _save_user_yaml(config)
    return folder_id


def _render_html_to_pdf(path: Path) -> Path:
    """Render an HTML report to a Drive-previewable PDF using Playwright."""
    pdf = path.with_suffix(".pdf")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            page = browser.new_page()
            page.goto(path.resolve().as_uri(), wait_until="networkidle")
            page.emulate_media(media="screen")
            page.pdf(
                path=str(pdf),
                format="A4",
                print_background=True,
                margin={"top": "10mm", "right": "10mm", "bottom": "10mm", "left": "10mm"},
            )
        finally:
            browser.close()
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RuntimeError(f"Playwright did not create the report preview: {pdf}")
    return pdf


def publish_report(path: Path, report_id: str) -> dict[str, str]:
    upload_path = _render_html_to_pdf(path) if path.suffix.casefold() == ".html" else path
    folder = ensure_reports_folder()
    query = f"name='{upload_path.name}' and '{folder}' in parents and trashed=false"
    existing = run_gws("drive", "files", "list", {"q": query, "fields": "files(id,name)", "pageSize": 10}).get("files", [])
    if existing:
        file_id = existing[0]["id"]
        run_cli(["gws", "drive", "files", "update", "--params", json.dumps({"fileId": file_id}),
                 "--upload", upload_path.name], cwd=upload_path.parent)
    else:
        created = parse_json_output(run_cli(["gws", "drive", "files", "create", "--json",
            json.dumps({"name": upload_path.name, "parents": [folder], "appProperties": {"paReportId": report_id}}),
            "--upload", upload_path.name], cwd=upload_path.parent))
        file_id = created["id"]
    meta = run_gws("drive", "files", "get", {"fileId": file_id, "fields": "id,name,webViewLink"})
    return {"id": meta["id"], "url": meta.get("webViewLink", f"https://drive.google.com/open?id={file_id}"),
            "format": upload_path.suffix.lstrip(".").casefold()}


def email_report(path: Path, title: str, drive_url: str | None) -> dict:
    recipient = get_user_config().get("email")
    if not recipient:
        raise RuntimeError("No email configured in user.yaml")
    html = path.read_text(encoding="utf-8")
    link = drive_url or "The attached HTML file is the durable copy."
    msg = EmailMessage()
    msg["To"] = recipient
    msg["Subject"] = title
    msg.set_content(f"{title}\n\nPublished report: {link}")
    linked_html = html.replace("<body>", f'<body><p style="text-align:center"><a href="{drive_url or "#"}">Open the private Drive copy</a></p>', 1)
    msg.add_alternative(linked_html, subtype="html")
    msg.add_attachment(path.read_bytes(), maintype="text", subtype="html", filename=path.name)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    return run_gws("gmail", "users.messages", "send", {"userId": "me"}, body={"raw": raw})
