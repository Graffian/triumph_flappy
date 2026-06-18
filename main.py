"""
main.py — prefetch thread + main control loop.
"""

import threading
import time

import cv2
import numpy as np
from PIL import Image

import vision
from wda import get_session, take_screenshot, tap
from control import (
    CEILING_Y_PHYSICAL, FLOOR_Y_PHYSICAL,
    TAP_X_LOGICAL, TAP_Y_LOGICAL,
    how_many_taps, reset_controller,
)

_latest_frame = [None]   # [image] shared between threads
_prefetch_lock = threading.Lock()


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


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def run():
    get_session()
    print("Bot running — Ctrl+C to stop")

    calibrated = False
    no_char_frames = 0
    reset_controller()

    prefetch = start_prefetch()   # fire first capture

    while True:
        t0 = time.perf_counter()
        img = get_frame(prefetch)
        prefetch = start_prefetch()   # immediately fire the next one

        bgr = pil_to_bgr(img)

        # ── Calibration ──
        if not calibrated:
            calibrated = vision.calibrate_character_colour(bgr)
            continue

        # ── Detect character ──
        char_y = vision.detect_character_y(bgr)

        if char_y is None:
            no_char_frames += 1
            if no_char_frames >= 6:
                print("  Game over — restarting")
                time.sleep(0.4)
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
                time.sleep(0.3)
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
                time.sleep(0.3)
                tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)  # game-over screen often needs a 3rd tap
                vision.reset_calibration()
                calibrated = False
                no_char_frames = 0
                reset_controller()
            continue

        no_char_frames = 0

        # ── Detect gap ──
        gap_y = vision.detect_gap_y(bgr)

        mid = (CEILING_Y_PHYSICAL + FLOOR_Y_PHYSICAL) // 2
        target_y = gap_y if gap_y is not None else mid  # aim for gap or screen centre

        n = how_many_taps(char_y, target_y)
        for _ in range(n):
            tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
            time.sleep(0.02)

        elapsed = time.perf_counter() - t0
        print(f"  frame {elapsed*1000:.0f}ms  char={char_y}  gap={gap_y}  taps={n}")


if __name__ == "__main__":
    run()