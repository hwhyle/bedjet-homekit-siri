"""Minimal Home Assistant REST helper. Token comes from the environment only."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


class HAError(RuntimeError):
    pass


def load_dotenv(path: str | None = None) -> None:
    """Load KEY=VALUE pairs from a .env file if present. Does not override env."""
    candidates = []
    if path:
        candidates.append(path)
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(here)
    candidates.extend(
        [
            os.path.join(os.getcwd(), ".env"),
            os.path.join(repo_root, ".env"),
        ]
    )
    seen = set()
    for candidate in candidates:
        candidate = os.path.abspath(candidate)
        if candidate in seen or not os.path.isfile(candidate):
            continue
        seen.add(candidate)
        with open(candidate, encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'").strip('"')
                if key and key not in os.environ:
                    os.environ[key] = value


def get_credentials() -> tuple[str, str]:
    load_dotenv()
    url = (os.environ.get("HA_URL") or "").strip().rstrip("/")
    token = (os.environ.get("HA_TOKEN") or "").strip()
    if not url:
        raise HAError(
            "HA_URL is not set. Export it or add it to a .env file "
            "(see .env.example). Example: http://homeassistant.local:8123"
        )
    if not token:
        raise HAError(
            "HA_TOKEN is not set. Create a long-lived access token in Home "
            "Assistant (Profile -> Security -> Long-Lived Access Tokens) and "
            "export it, or put it in a .env file. Do not commit the token."
        )
    return url, token


def request(
    method: str,
    path: str,
    body: Any | None = None,
    timeout: int = 20,
) -> Any:
    url, token = get_credentials()
    if not path.startswith("/"):
        path = "/" + path
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HAError(f"Home Assistant returned HTTP {exc.code} for {method} {path}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise HAError(f"Could not reach Home Assistant at {url}: {exc.reason}") from exc


def get_json(path: str, timeout: int = 20) -> Any:
    return request("GET", path, timeout=timeout)


def die(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)
