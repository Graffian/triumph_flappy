"""
wda.py — WebDriverAgent session management, screenshots, and taps.
"""

import base64
import time
from io import BytesIO
import cv2
import numpy as np
from PIL import Image
import threading
import requests


WDA_URL = "http://localhost:8100"
COORD_SCALE = 3.0  # physical_px / logical_px — 3x for most modern iPhones
_mjpeg_thread = None
_mjpeg_latest = [None]
_mjpeg_lock = threading.Lock()
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


def _mjpeg_reader():
    buf = b""
    r = requests.get("http://localhost:9100", stream=True, timeout=30)
    for chunk in r.iter_content(chunk_size=4096):
        buf += chunk
        a = buf.find(b'\xff\xd8')   # JPEG start
        b = buf.find(b'\xff\xd9')   # JPEG end
        if a != -1 and b != -1 and b > a:
            jpg = buf[a:b+2]
            buf = buf[b+2:]
            with _mjpeg_lock:
                _mjpeg_latest[0] = Image.open(BytesIO(jpg)).copy()

def _ensure_mjpeg():
    global _mjpeg_thread
    if _mjpeg_thread is None or not _mjpeg_thread.is_alive():
        _mjpeg_thread = threading.Thread(target=_mjpeg_reader, daemon=True)
        _mjpeg_thread.start()

def take_screenshot() -> Image.Image:
    _ensure_mjpeg()
    for _ in range(50):           # wait up to 0.5s for first frame
        with _mjpeg_lock:
            if _mjpeg_latest[0] is not None:
                return _mjpeg_latest[0]
        time.sleep(0.01)
    raise RuntimeError("No MJPEG frame received")


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