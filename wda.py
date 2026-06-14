"""
wda.py — WebDriverAgent session management, screenshots, and taps.
"""

import base64
import time
from io import BytesIO

import requests
from PIL import Image

WDA_URL = "http://localhost:8100"
COORD_SCALE = 3.0  # physical_px / logical_px — 3x for most modern iPhones

_http = requests.Session()
_http.headers.update({"Content-Type": "application/json"})
_session_id = None


def _create_session() -> str:
    r = _http.post(
        f"{WDA_URL}/session",
        json={"capabilities": {"alwaysMatch": {}}},
        timeout=30,
    )
    r.raise_for_status()
    body = r.json()
    return body.get("sessionId") or body.get("value", {}).get("sessionId")


def get_session() -> str:
    """Returns the existing session ID, or creates one if none exists."""
    global _session_id
    if _session_id:
        return _session_id
    try:
        r = _http.get(f"{WDA_URL}/status", timeout=8)
        body = r.json()
        sid = body.get("sessionId") or body.get("value", {}).get("sessionId")
        if sid:
            _session_id = sid
            return _session_id
    except Exception:
        pass
    _session_id = _create_session()
    return _session_id


def take_screenshot(retries: int = 3) -> Image.Image:
    """Returns the current screen as a PIL Image at PHYSICAL pixel resolution."""
    global _session_id
    get_session()
    for attempt in range(retries):
        try:
            r = _http.get(f"{WDA_URL}/session/{_session_id}/screenshot", timeout=10)
            if r.status_code == 404:  # session died — refresh it
                _session_id = None
                get_session()
                continue
            r.raise_for_status()
            raw = r.json().get("value", "")
            if isinstance(raw, dict):
                raw = raw.get("value", "")  # older WDA wraps value in value
            return Image.open(BytesIO(base64.b64decode(raw)))
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.2)
    raise RuntimeError("Screenshot failed after all retries.")


def tap(x: int, y: int):
    """Single tap. x/y must be in WDA LOGICAL pixels (not scaled by COORD_SCALE)."""
    sid = get_session()
    actions = [
        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
        {"type": "pointerDown"},
        {"type": "pause", "duration": 80},
        {"type": "pointerUp"},
    ]
    payload = {
        "actions": [{
            "type": "pointer",
            "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": actions,
        }]
    }
    _http.post(f"{WDA_URL}/session/{sid}/actions", json=payload, timeout=5)