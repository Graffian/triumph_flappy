# WebDriverAgent (WDA) Setup Guide

A generalised reference for integrating WebDriverAgent into any Python-based iOS automation project, extracted from a working implementation.

---

## What is WDA?

WebDriverAgent (WDA) is an open-source WebDriver server for iOS developed by Facebook/Meta. It runs directly on a physical iOS device (or simulator) and exposes a standard W3C WebDriver HTTP API that lets you control the device programmatically — screenshots, touch input, gestures, and more.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| iOS device (physical or simulator) | Physical device needs a valid Apple Developer account |
| Xcode | Required to build and sign the WDA runner |
| `libimobiledevice` or `tidevice` | For USB port forwarding |
| Python 3.9+ | With `requests` and `Pillow` at minimum |

Install port-forwarding tools:

```bash
# macOS — via Homebrew
brew install libimobiledevice
# or: pip install tidevice
```

---

## Step 1 — Build & Install WDA on the Device

Clone Facebook's WDA repo and build it with Xcode:

```bash
git clone https://github.com/appium/WebDriverAgent.git
cd WebDriverAgent
```

Open `WebDriverAgent.xcodeproj` in Xcode, select your device as the target, set your Team/Bundle ID under Signing, then run the `WebDriverAgentRunner` scheme. You only need to do this once per device.

Alternatively, if you use Appium, it handles WDA installation automatically.

---

## Step 2 — Port Forwarding (USB tunnel to localhost)

WDA listens on port **8100** on the device. Forward it to your machine:

```bash
# Using iproxy (libimobiledevice)
iproxy 8100 8100 &

# Using tidevice
tidevice relay 8100 8100
```

Verify WDA is reachable:

```bash
curl http://localhost:8100/status
```

A successful response contains a JSON blob with `sessionId` and device info.

---

## Step 3 — Python Configuration Constants

Define these at the top of your script. Adjust to match your device and use case.

```python
WDA_URL = "http://localhost:8100"  # Always localhost after port-forward
```

**Coordinate scale factor** — WDA operates in *logical* pixels. Screenshots are in *physical* pixels. The scale factor bridges them:

```python
COORD_SCALE = 3.0  # 3× for most modern iPhones (Retina @3x)
                   # Use 2.0 for older or non-Pro iPhones
```

To find your device's actual scale: `physical_width / logical_width`. Logical dimensions are shown in WDA's `/status` response.

**Touch timing** — tune these for your target app's responsiveness:

```python
HOLD_MS       = 50    # ms to hold before starting a swipe
TILE_PAUSE_MS = 18    # ms between each intermediate pointer move
LIFT_DELAY_MS = 100   # ms pause before lifting the finger
```

---

## Step 4 — Session Management

WDA requires an active session for all API calls. A session is created via a POST and reused across requests.

```python
import requests

_http = requests.Session()
_http.headers.update({"Content-Type": "application/json"})
_session_id = None

def _create_session() -> str:
    """Creates a fresh WDA session."""
    r = _http.post(
        f"{WDA_URL}/session",
        json={"capabilities": {"alwaysMatch": {}}},
        timeout=30
    )
    r.raise_for_status()
    sid = r.json().get("sessionId") or r.json().get("value", {}).get("sessionId")
    return sid

def get_session() -> str:
    """Returns the existing session ID, or creates one if none exists."""
    global _session_id
    if _session_id:
        return _session_id
    try:
        r = _http.get(f"{WDA_URL}/status", timeout=8)
        sid = r.json().get("sessionId") or r.json().get("value", {}).get("sessionId")
        if sid:
            _session_id = sid
            return _session_id
    except Exception:
        pass
    _session_id = _create_session()
    return _session_id
```

**Key detail:** if a screenshot call returns HTTP 404, the session has expired. Reset `_session_id = None` and call `get_session()` again to recover without restarting your script.

---

## Step 5 — Taking Screenshots

```python
import base64
from PIL import Image
from io import BytesIO

def take_screenshot(retries: int = 3) -> Image.Image:
    global _session_id
    for attempt in range(retries):
        try:
            r = _http.get(
                f"{WDA_URL}/session/{_session_id}/screenshot",
                timeout=10
            )
            if r.status_code == 404:        # Session died — refresh it
                _session_id = None
                get_session()
                continue
            r.raise_for_status()
            raw = r.json().get("value", "")
            if isinstance(raw, dict):
                raw = raw.get("value", "")  # Older WDA wraps value in value
            return Image.open(BytesIO(base64.b64decode(raw)))
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.2)
    raise RuntimeError("Screenshot failed after all retries.")
```

The response is a base64-encoded PNG. The returned `Image` object is at **physical pixel** resolution.

---

## Step 6 — Sending Touch / Swipe Actions

WDA uses the W3C WebDriver Actions API. Build an action sequence as a list of dicts and POST it to `/actions`.

**Minimal single tap:**

```python
def tap(x: int, y: int):
    sid = get_session()
    actions = [
        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
        {"type": "pointerDown"},
        {"type": "pause",       "duration": 80},
        {"type": "pointerUp"},
    ]
    payload = {
        "actions": [{
            "type": "pointer",
            "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": actions
        }]
    }
    _http.post(f"{WDA_URL}/session/{sid}/actions", json=payload, timeout=5)
```

**Multi-stop swipe (drag through a sequence of coordinates):**

```python
def swipe_path(coords: list[tuple[int, int]]):
    """
    coords: list of (x, y) in WDA logical pixels.
    Builds a continuous drag gesture through all points.
    """
    sid  = get_session()
    sx, sy = coords[0]
    acts = [
        {"type": "pointerMove", "duration": 0,       "x": int(sx), "y": int(sy)},
        {"type": "pointerDown"},
        {"type": "pause",       "duration": HOLD_MS},
    ]
    for x, y in coords[1:]:
        acts.append({"type": "pointerMove", "duration": TILE_PAUSE_MS, "x": int(x), "y": int(y)})
    acts.append({"type": "pause",    "duration": LIFT_DELAY_MS})
    acts.append({"type": "pointerUp"})

    payload = {
        "actions": [{
            "type": "pointer",
            "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": acts
        }]
    }
    r = _http.post(f"{WDA_URL}/session/{sid}/actions", json=payload, timeout=5)
    return r.status_code == 200
```

**Coordinate note:** all `x`/`y` values sent to `/actions` must be in **logical pixels** (not multiplied by `COORD_SCALE`). The scale factor only applies when mapping back from screenshot pixel positions to logical tap positions.

---

## Coordinate System Summary

```
Screenshot image  →  physical pixels  (e.g. 1290 × 2796 on iPhone 15 Pro)
WDA touch actions →  logical pixels   (e.g.  430 ×  932)
Scale factor      =  physical / logical  (3.0 for @3x devices)

# Convert a screenshot pixel position → logical tap coordinate:
logical_x = screenshot_x / COORD_SCALE
logical_y = screenshot_y / COORD_SCALE

# Convert a known logical coordinate → screenshot pixel region:
phys_x = logical_x * COORD_SCALE
phys_y = logical_y * COORD_SCALE
```

---

## Core API Endpoints Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/status` | Check WDA is alive; may return existing session ID |
| `POST` | `/session` | Create a new session |
| `GET` | `/session/{id}/screenshot` | Capture screen as base64 PNG |
| `POST` | `/session/{id}/actions` | Execute touch / pointer actions |
| `DELETE` | `/session/{id}` | Destroy a session |

---

## Common Failure Modes & Fixes

| Symptom | Likely Cause | Fix |
|---|---|---|
| `curl /status` times out | Port forward not running | Re-run `iproxy 8100 8100` |
| `404` on screenshot | WDA session expired | Reset `_session_id = None`, call `get_session()` |
| Swipe lands in wrong spot | Wrong `COORD_SCALE` | Verify with `physical_px / logical_px` for your device |
| Session creation times out | WDA crashed on device | Re-run the WDA Xcode scheme or restart `tidevice` |
| Base64 decode error | WDA returned error JSON, not image | Check `r.json()` for an error message before decoding |

---

## Minimal Working Skeleton

```python
import requests, base64, time
from PIL import Image
from io import BytesIO

WDA_URL      = "http://localhost:8100"
COORD_SCALE  = 3.0

_http        = requests.Session()
_http.headers.update({"Content-Type": "application/json"})
_session_id  = None

def get_session():
    global _session_id
    if _session_id: return _session_id
    r = _http.post(f"{WDA_URL}/session",
                   json={"capabilities": {"alwaysMatch": {}}}, timeout=30)
    r.raise_for_status()
    _session_id = r.json().get("sessionId") or r.json()["value"]["sessionId"]
    return _session_id

def screenshot() -> Image.Image:
    sid = get_session()
    r   = _http.get(f"{WDA_URL}/session/{sid}/screenshot", timeout=10)
    r.raise_for_status()
    return Image.open(BytesIO(base64.b64decode(r.json()["value"])))

def tap(lx: int, ly: int):
    sid  = get_session()
    acts = [
        {"type": "pointerMove", "duration": 0,  "x": lx, "y": ly},
        {"type": "pointerDown"},
        {"type": "pause",       "duration": 80},
        {"type": "pointerUp"},
    ]
    _http.post(f"{WDA_URL}/session/{sid}/actions", timeout=5, json={
        "actions": [{"type":"pointer","id":"finger1",
                     "parameters":{"pointerType":"touch"},"actions":acts}]
    })

# --- usage ---
img = screenshot()
img.save("screen.png")
tap(200, 400)   # tap at logical coords (200, 400)
```