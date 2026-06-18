"""
wda.py — WebDriverAgent session management, screenshots, and taps.
"""

import base64
import time
from io import BytesIO
import cv2
import numpy as np
from PIL import Image
import requests


WDA_URL = "http://localhost:8100"
COORD_SCALE = 3.0  # physical_px / logical_px — 3x for most modern iPhones
_mjpeg_cap = None
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


def get_mjpeg_cap():
    global _mjpeg_cap
    if _mjpeg_cap is None or not _mjpeg_cap.isOpened():
        _mjpeg_cap = cv2.VideoCapture("http://localhost:9100")
    return _mjpeg_cap

def take_screenshot() -> Image.Image:
    cap = get_mjpeg_cap()
    ret, frame = cap.read()   # frame is already BGR numpy array
    if not ret:
        raise RuntimeError("MJPEG stream read failed")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


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