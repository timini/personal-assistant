import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_publish_report_updates_existing_file(tmp_path):
    from pa_google.reports import publish_report

    report = tmp_path / "2026-08-24-daily-report.html"
    report.write_text("<html>report</html>")
    preview = tmp_path / "2026-08-24-daily-report.pdf"
    preview.write_bytes(b"%PDF-preview")
    with (
        patch("pa_google.reports.ensure_reports_folder", return_value="folder"),
        patch("pa_google.reports._render_html_to_pdf", return_value=preview),
        patch("pa_google.reports.run_gws", side_effect=[
            {"files": [{"id": "existing"}]},
            {"id": "existing", "webViewLink": "https://drive/report"},
        ]) as gws,
        patch("pa_google.reports.run_cli", return_value=subprocess.CompletedProcess([], 0, '{"id":"existing"}', "")) as cli,
    ):
        result = publish_report(report, "daily-2026-08-24")

    assert result["id"] == "existing"
    assert result["url"] == "https://drive/report"
    assert "update" in cli.call_args.args[0]
    assert gws.call_count == 2


def test_publish_html_report_uses_rendered_pdf_for_drive_preview(tmp_path):
    from pa_google.reports import publish_report

    report = tmp_path / "2026-08-24-daily-report.html"
    report.write_text("<html>report</html>")
    preview = tmp_path / "2026-08-24-daily-report.pdf"
    preview.write_bytes(b"%PDF-preview")
    with (
        patch("pa_google.reports.ensure_reports_folder", return_value="folder"),
        patch("pa_google.reports._render_html_to_pdf", return_value=preview) as render,
        patch("pa_google.reports.run_gws", side_effect=[
            {"files": []},
            {"id": "pdf-id", "webViewLink": "https://drive/rendered-report"},
        ]) as gws,
        patch("pa_google.reports.run_cli", return_value=subprocess.CompletedProcess([], 0, '{"id":"pdf-id"}', "")) as cli,
    ):
        result = publish_report(report, "daily-2026-08-24")

    render.assert_called_once_with(report)
    create_args = cli.call_args.args[0]
    assert "--json" in create_args
    metadata = create_args[create_args.index("--json") + 1]
    assert '"name": "2026-08-24-daily-report.pdf"' in metadata
    assert "2026-08-24-daily-report.pdf" in create_args
    assert result == {"id": "pdf-id", "url": "https://drive/rendered-report", "format": "pdf"}
    assert gws.call_count == 2


def test_render_html_to_pdf_uses_playwright_and_closes_browser(tmp_path):
    from pa_google.reports import _render_html_to_pdf

    report = tmp_path / "report.html"
    report.write_text("<html><body>Rendered</body></html>")
    page = MagicMock()
    page.pdf.side_effect = lambda **kwargs: Path(kwargs["path"]).write_bytes(b"%PDF-rendered")
    browser = MagicMock()
    browser.new_page.return_value = page
    playwright = MagicMock()
    playwright.chromium.launch.return_value = browser
    manager = MagicMock()
    manager.__enter__.return_value = playwright

    with patch("pa_google.reports.sync_playwright", return_value=manager):
        pdf = _render_html_to_pdf(report)

    assert pdf.read_bytes() == b"%PDF-rendered"
    playwright.chromium.launch.assert_called_once_with(channel="chrome", headless=True)
    page.goto.assert_called_once_with(report.resolve().as_uri(), wait_until="networkidle")
    browser.close.assert_called_once_with()


def test_email_report_sends_html_and_attachment(tmp_path):
    from pa_google.reports import email_report

    report = tmp_path / "report.html"
    report.write_text("<html><body>Hello</body></html>")
    with (
        patch("pa_google.reports.get_user_config", return_value={"email": "user@example.com"}),
        patch("pa_google.reports.run_gws", return_value={"id": "sent"}) as send,
    ):
        result = email_report(report, "Daily report", "https://drive/report")

    assert result == {"id": "sent"}
    body = send.call_args.kwargs["body"]
    assert "raw" in body
