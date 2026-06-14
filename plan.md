# Flappy Bird Bot — WDA Automation Plan

> Companion to `wdaSetup.md`. Read that first for WDA install, port-forwarding, session management, and coordinate system.

---

## 1. Game Analysis (from screenshots)

| Element | Observation |
|---|---|
| Character X | Fixed — always left ~20% of screen. Only Y changes. |
| Character colour | Changes every game (seen: purple, cyan). Cape colour also changes. |
| Top obstacles | Pipes hang down from the cloud ceiling |
| Bottom obstacles | Pipes rise up from the bubble ground |
| The gap | A horizontal band of open sky between the two pipe sets |
| Score box | Pixelated counter, top-centre of screen |
| Ceiling | White puffy clouds |
| Floor | Blue bubble field |
| Input | Single tap anywhere = one flap upward |

---

## 2. The Speed Problem (and why it matters)

WDA screenshots over USB take **50–150ms** each. That limits you to **7–12 fps** in a naive loop. In those gaps between frames the character is in free fall with no feedback — on tight gaps that's enough to die.

Three things fix this:

| Problem | Fix |
|---|---|
| Waiting for screenshot blocks everything | Prefetch in a background thread |
| Running cv2 on full 1320×2868 is slow | Crop to ROI before any processing |
| Single tap per frame is too blunt | Tap multiple times if far below gap; tap early based on velocity |

---

## 3. Device & Coordinate Constants

Physical resolution: **1320 × 2868** (width × height). Scale 3×, logical = **440 × 956**.

```python
WDA_URL      = "http://localhost:8100"
COORD_SCALE  = 3.0

# ── Physical pixel constants (image analysis) ──
CHAR_X_PHYSICAL    = 280
SCAN_HALF_WIDTH    = 50

CEILING_Y_PHYSICAL = 283
FLOOR_Y_PHYSICAL   = 1770

GAP_SCAN_X_START   = 430     # Ahead of character
GAP_SCAN_X_END     = 730
GAP_SCAN_COLUMNS   = 15

# ── Crop ROIs (process only what you need) ──
# Character column strip
CHAR_ROI = (
    max(0, CHAR_X_PHYSICAL - SCAN_HALF_WIDTH),   # x1
    CEILING_Y_PHYSICAL,                           # y1
    CHAR_X_PHYSICAL + SCAN_HALF_WIDTH,            # x2
    FLOOR_Y_PHYSICAL                              # y2
)
# Gap scan strip
GAP_ROI = (
    GAP_SCAN_X_START,
    CEILING_Y_PHYSICAL,
    GAP_SCAN_X_END,
    FLOOR_Y_PHYSICAL
)

# ── Logical tap coordinate ──
TAP_X_LOGICAL = 220
TAP_Y_LOGICAL = 478

# ── Control tuning ──
FLAP_THRESHOLD = 30      # physical px — signal must exceed this to tap
FLAP_KP        = 1.0     # position gain
FLAP_KD        = 0.5     # velocity gain (reacts to how fast it's falling)
MAX_TAPS_PER_FRAME = 3   # cap multi-taps so it doesn't rocket into ceiling
```

---

## 4. Screenshot Prefetch (critical for speed)

Instead of waiting for a screenshot before doing anything, fire the next capture in a background thread the moment you finish processing the current frame. This overlaps network I/O with computation.

```python
import threading

_latest_frame   = [None]   # [image] shared between threads
_prefetch_lock  = threading.Lock()

def _prefetch_fn():
    img = take_screenshot()
    with _prefetch_lock:
        _latest_frame[0] = img

def start_prefetch():
    t = threading.Thread(target=_prefetch_fn, daemon=True)
    t.start()
    return t

def get_frame(prefetch_thread) -> Image.Image:
    prefetch_thread.join(timeout=1.0)
    with _prefetch_lock:
        img = _latest_frame[0]
        _latest_frame[0] = None
    return img if img is not None else take_screenshot()
```

Usage in the main loop:

```python
t = start_prefetch()           # fire first capture
while True:
    img = get_frame(t)         # wait for it (usually already done)
    t   = start_prefetch()     # immediately fire the next one
    # ... process img ...
```

---

## 5. Sky Mask

```python
import cv2
import numpy as np

SKY_HSV_LOWER = np.array([195, 20,  160], dtype=np.uint8)
SKY_HSV_UPPER = np.array([225, 100, 255], dtype=np.uint8)

def make_sky_mask_roi(img_bgr: np.ndarray, roi: tuple) -> np.ndarray:
    """Apply sky mask to a cropped ROI only — much faster than full image."""
    x1, y1, x2, y2 = roi
    crop = img_bgr[y1:y2, x1:x2]
    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, SKY_HSV_LOWER, SKY_HSV_UPPER)
```

---

## 6. Character Colour Calibration (auto, once per game)

You never input the colour manually. On the first clean frame (score = 0, no pipes), the bot samples whatever non-sky pixels are at the character's fixed X column and stores their HSV range. When the round ends and the colour changes, `CHARACTER_HSV` is reset to `None` and the bot re-calibrates on the next clean frame.

```python
CHARACTER_HSV = None

def calibrate_character_colour(img_bgr: np.ndarray) -> bool:
    global CHARACTER_HSV
    mask = make_sky_mask_roi(img_bgr, CHAR_ROI)
    ys, xs = np.where(mask == 0)

    if len(ys) < 10:
        return False   # Nothing found yet — try next frame

    x1, y1, _, _ = CHAR_ROI
    char_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)[y1:y1+mask.shape[0], x1:x1+mask.shape[1]]
    pixels = char_hsv[ys, xs]

    lo = np.array([
        max(0,   int(np.percentile(pixels[:,0], 5))  - 15),
        max(0,   int(np.percentile(pixels[:,1], 5))  - 20),
        max(0,   int(np.percentile(pixels[:,2], 5))  - 20),
    ], dtype=np.uint8)
    hi = np.array([
        min(180, int(np.percentile(pixels[:,0], 95)) + 15),
        min(255, int(np.percentile(pixels[:,1], 95)) + 20),
        min(255, int(np.percentile(pixels[:,2], 95)) + 20),
    ], dtype=np.uint8)

    CHARACTER_HSV = (lo, hi)
    print(f"  [Calibrated] {lo} → {hi}")
    return True
```

---

## 7. Character Y Detection

Runs on the cropped ROI only.

```python
def detect_character_y(img_bgr: np.ndarray) -> int | None:
    if CHARACTER_HSV is None:
        return None

    x1, y1, x2, y2 = CHAR_ROI
    crop = img_bgr[y1:y2, x1:x2]
    hsv  = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, CHARACTER_HSV[0], CHARACTER_HSV[1])

    ys = np.where(mask > 0)[0]
    if len(ys) < 5:
        return None

    return int(np.median(ys)) + y1   # convert back to full-image Y
```

---

## 8. Gap Y Detection

Runs on the cropped ROI only.

```python
def detect_gap_y(img_bgr: np.ndarray) -> int | None:
    x1, y1, x2, y2 = GAP_ROI
    mask = make_sky_mask_roi(img_bgr, GAP_ROI)

    col_positions = np.linspace(0, mask.shape[1]-1, GAP_SCAN_COLUMNS, dtype=int)
    tops, bottoms = [], []

    for cx in col_positions:
        col = mask[:, cx]
        sky = np.where(col == 255)[0]
        if len(sky) == 0:
            continue
        tops.append(int(sky[0]))
        bottoms.append(int(sky[-1]))

    if not tops:
        return None

    return int((np.median(tops) + np.median(bottoms)) / 2) + y1
```

---

## 9. Control Logic (velocity-aware, multi-tap)

The key upgrade over a simple threshold: the controller looks at **how fast the character is falling**, not just where it is. If it's plummeting toward the bottom pipe, it taps immediately rather than waiting until the threshold is crossed. It also taps multiple times in one cycle when far off target.

```python
prev_char_y = None

def how_many_taps(char_y: int, gap_y: int) -> int:
    global prev_char_y

    error    = char_y - gap_y                                 # positive = below gap
    velocity = (char_y - prev_char_y) if prev_char_y else 0  # positive = falling
    prev_char_y = char_y

    signal = FLAP_KP * error + FLAP_KD * velocity

    if signal <= FLAP_THRESHOLD:
        return 0   # above gap or close enough, don't tap

    # Scale taps to how far/fast off target we are
    if signal < 80:
        return 1
    elif signal < 160:
        return 2
    else:
        return min(MAX_TAPS_PER_FRAME, 3)
```

---

## 10. Full Main Loop

```python
import time
from PIL import Image

def pil_to_bgr(img: Image.Image) -> np.ndarray:
    import cv2
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)

def run():
    global CHARACTER_HSV, prev_char_y
    get_session()
    print("Bot running — Ctrl+C to stop")

    calibrated     = False
    no_char_frames = 0
    prev_char_y    = None

    prefetch = start_prefetch()   # fire first screenshot

    while True:
        t0  = time.perf_counter()
        img = get_frame(prefetch)
        prefetch = start_prefetch()   # fire next one immediately

        bgr = pil_to_bgr(img)

        # ── Calibration ──
        if not calibrated:
            calibrated = calibrate_character_colour(bgr)
            continue

        # ── Detect character ──
        char_y = detect_character_y(bgr)

        if char_y is None:
            no_char_frames += 1
            if no_char_frames >= 6:
                print("  Game over — restarting")
                time.sleep(0.4)
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
                time.sleep(0.3)
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
                CHARACTER_HSV  = None
                calibrated     = False
                no_char_frames = 0
                prev_char_y    = None
            continue

        no_char_frames = 0

        # ── Detect gap ──
        gap_y = detect_gap_y(bgr)

        if gap_y is None:
            # No pipes — hold near vertical midpoint
            mid = (CEILING_Y_PHYSICAL + FLOOR_Y_PHYSICAL) // 2
            if char_y > mid + 80:
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
        else:
            n = how_many_taps(char_y, gap_y)
            for _ in range(n):
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
                time.sleep(0.02)   # tiny gap between rapid taps
            if n:
                print(f"  ×{n} TAP  char={char_y}  gap={gap_y}")

        elapsed = time.perf_counter() - t0
        print(f"  frame {elapsed*1000:.0f}ms")   # monitor actual loop speed

if __name__ == "__main__":
    run()
```

---

## 11. Benchmark WDA Speed First

Before anything else, run this to know what frame rate you're actually getting. Everything else is tuning around that number.

```python
# benchmark.py
import time
get_session()

times = []
for i in range(20):
    t0 = time.perf_counter()
    take_screenshot()
    times.append(time.perf_counter() - t0)
    print(f"  {i+1:02d}: {times[-1]*1000:.0f}ms")

import numpy as np
print(f"\n  Median: {np.median(times)*1000:.0f}ms  →  ~{1/np.median(times):.1f} fps")
print(f"  Min:    {min(times)*1000:.0f}ms")
print(f"  Max:    {max(times)*1000:.0f}ms")
```

| Result | What it means |
|---|---|
| < 60ms median | You're fine at 15+ fps |
| 60–100ms | Workable — prefetch thread essential |
| > 100ms | Tight — consider lowering image quality in WDA settings or using tidevice instead of iproxy |

---

## 12. File Structure

```
flappy_bot/
├── wdaSetup.md     ← WDA reference (done)
├── plan.md         ← This file
├── wda.py          ← get_session, take_screenshot, tap
├── vision.py       ← calibrate, detect_character_y, detect_gap_y
├── control.py      ← how_many_taps, constants
├── main.py         ← run() loop with prefetch
├── benchmark.py    ← run this first
└── calibrate.py    ← verify sky mask and detection
```

---

## 13. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| WDA > 100ms per screenshot | Run benchmark.py first; try tidevice relay if iproxy is slow |
| Sky HSV range wrong | Run calibrate.py, tune `SKY_HSV_LOWER/UPPER` |
| Pipe overlapping char column | Colour-specific mask rejects pipe pixels |
| Brief occlusion triggers restart | 6-frame (~0.5s) threshold absorbs it |
| Character rockets into ceiling | `MAX_TAPS_PER_FRAME = 3` cap prevents it |
| Game-over screen needs extra tap | Add a third tap in the restart block |