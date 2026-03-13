"""Common infrastructure for running CLI tools as subprocesses."""

import json
import subprocess
import sys
from typing import Any


def run_cli(
    command: list[str],
    *,
    timeout: int = 60,
    capture: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess:
    """Run a CLI command as a subprocess.

    Args:
        command: Command and arguments as a list.
        timeout: Timeout in seconds.
        capture: Whether to capture stdout/stderr.
        check: Whether to raise on non-zero exit code.

    Returns:
        CompletedProcess with stdout/stderr as strings.
    """
    try:
        result = subprocess.run(
            command,
            capture_output=capture,
            text=True,
            timeout=timeout,
            check=check,
        )
        return result
    except subprocess.TimeoutExpired:
        print(f"Error: command timed out after {timeout}s: {' '.join(command)}", file=sys.stderr)
        raise
    except subprocess.CalledProcessError as e:
        print(f"Error running {' '.join(command)}:", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        raise


def parse_json_output(result: subprocess.CompletedProcess) -> Any:
    """Parse JSON from a command's stdout, skipping any non-JSON preamble lines."""
    stdout = result.stdout.strip()
    # Some CLI tools (e.g. gws) print info lines before JSON — find the first { or [
    for i, char in enumerate(stdout):
        if char in ('{', '['):
            stdout = stdout[i:]
            break
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        print(f"Failed to parse JSON from output: {result.stdout[:200]}", file=sys.stderr)
        raise


def run_gws(
    service: str,
    resource: str,
    method: str,
    params: dict | None = None,
    *,
    body: dict | None = None,
    timeout: int = 60,
    page_all: bool = False,
) -> Any:
    """Convenience wrapper for Google Workspace CLI (gws) calls.

    Resource can use dots or spaces: "users.messages" becomes "users messages".
    Example: run_gws("gmail", "users.messages", "list", {"userId": "me", "maxResults": 10})
    """
    # gws expects space-separated resource parts, not dots
    resource_parts = resource.replace(".", " ").split()
    cmd = ["gws", service, *resource_parts, method]
    if params:
        cmd.extend(["--params", json.dumps(params)])
    if body:
        cmd.extend(["--json", json.dumps(body)])
    if page_all:
        cmd.append("--page-all")
    result = run_cli(cmd, timeout=timeout)
    return parse_json_output(result)
