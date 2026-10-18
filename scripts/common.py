"""Shared helpers: paths, config/state IO, Graph API client, small utils.

Sab scripts isi module ko import karte hain. Paths repo root ke relative hain.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config.json"
EXAMPLE_CONFIG_PATH = ROOT / "config.example.json"
STATE_PATH = ROOT / "state" / "state.json"
SCENARIOS_PATH = ROOT / "content" / "scenarios.json"
OUT_DIR = ROOT / "out"
ASSETS_DIR = ROOT / "assets"

IST = timezone(timedelta(hours=5, minutes=30))
GRAPH_BASE = os.environ.get("IG_GRAPH_HOST", "https://graph.instagram.com")
API_VERSION = os.environ.get("IG_API_VERSION", "v25.0")


def log(*parts) -> None:
    text = " ".join(str(p) for p in parts)
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        # Windows console (cp1252) can't render "→" etc. — degrade gracefully.
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        print(text.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def _requests():
    """Lazy import — engine/votes ka selftest bina dependencies chalta hai."""
    import requests
    return requests


def load_json(path: Path, default=None):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_config() -> dict:
    cfg = load_json(CONFIG_PATH) or load_json(EXAMPLE_CONFIG_PATH)
    if cfg is None:
        raise RuntimeError("config.example.json not found — repo structure broken?")
    return cfg


def load_state() -> dict:
    state = load_json(STATE_PATH)
    if state is None:
        raise RuntimeError("state/state.json not found — repo structure broken?")
    return state


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE_PATH)


def ist_now() -> datetime:
    return datetime.now(IST)


def run(cmd, cwd=None, capture=True, check=True):
    res = subprocess.run(
        [str(c) for c in cmd], cwd=str(cwd) if cwd else None,
        check=False, text=True, capture_output=capture,
        encoding="utf-8", errors="replace",
    )
    if check and res.returncode != 0:
        raise RuntimeError(
            f"Command failed ({res.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"stderr: {(res.stderr or '')[-2000:]}"
        )
    return res


class ApiError(RuntimeError):
    def __init__(self, message: str, code=None, subcode=None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class GraphClient:
    """Instagram Graph API (Instagram Login flavor → graph.instagram.com)."""

    def __init__(self, access_token: str, version: str = None, base: str = None):
        self.token = access_token
        self.version = version or API_VERSION
        self.base = base or GRAPH_BASE

    def _handle(self, response):
        try:
            payload = response.json()
        except ValueError:
            raise ApiError(f"Non-JSON response (HTTP {response.status_code}): {response.text[:300]}")
        if isinstance(payload, dict) and payload.get("error"):
            err = payload["error"]
            raise ApiError(
                f"{err.get('message', 'unknown error')} "
                f"(code={err.get('code')}, subcode={err.get('error_subcode')})",
                code=err.get("code"), subcode=err.get("error_subcode"),
            )
        if response.status_code >= 400:
            raise ApiError(f"HTTP {response.status_code}: {str(payload)[:300]}")
        return payload

    def get(self, path: str, **params):
        url = f"{self.base}/{self.version}/{path.lstrip('/')}"
        params["access_token"] = self.token
        return self._handle(_requests().get(url, params=params, timeout=90))

    def post(self, path: str, **data):
        url = f"{self.base}/{self.version}/{path.lstrip('/')}"
        data["access_token"] = self.token
        return self._handle(_requests().post(url, data=data, timeout=90))

    def get_next(self, url: str):
        if "access_token=" not in url:
            url += ("&" if "?" in url else "?") + "access_token=" + self.token
        return self._handle(_requests().get(url, timeout=90))
