import base64
import os
import subprocess
import urllib.error
import urllib.request

from auth import redact


def run_script(path: str, argv: list[str], sudo: bool = False, timeout: int = 10, check: bool = True) -> str:
    cmd = (["sudo", "-n"] if sudo else []) + [path, *argv]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"Failed to run {os.path.basename(path)}: {exc}"

    output = result.stdout.strip()
    if check and result.returncode != 0:
        detail = result.stderr.strip() or output or f"exit {result.returncode}"
        return f"{os.path.basename(path)} failed: {redact(detail)}"
    return redact(output or result.stderr.strip()) or "(no output)"


def _auth_headers(auth: dict | None) -> dict:
    if not auth:
        return {}
    kind = auth.get("type")
    if kind == "basic":
        username = os.environ[auth["username_env"]]
        password = os.environ[auth["password_env"]]
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    if kind == "bearer":
        return {"Authorization": f"Bearer {os.environ[auth['token_env']]}"}
    if kind == "header":
        return {auth["name"]: os.environ[auth["value_env"]]}
    raise ValueError(f"Unknown auth type: {kind!r}")


def call_api(method: str, url: str, auth: dict | None = None, timeout: int = 10) -> str:
    try:
        headers = _auth_headers(auth)
    except KeyError as exc:
        return f"Missing environment variable for API auth: {exc}"

    req = urllib.request.Request(url, method=method.upper(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
    except urllib.error.HTTPError as exc:
        return f"API error: HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return f"API error: {exc.reason}"
    return body.strip() or "(empty response)"
