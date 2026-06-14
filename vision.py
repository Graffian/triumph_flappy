"""
vision.py — sky masking, character colour calibration, and Y-position detection.

All detection runs on cropped ROIs (CHAR_ROI / GAP_ROI), not the full frame.
"""

import cv2
import numpy as np

from control import CHAR_ROI, GAP_ROI, GAP_SCAN_COLUMNS

SKY_HSV_LOWER = np.array([195, 20, 160], dtype=np.uint8)
SKY_HSV_UPPER = np.array([225, 100, 255], dtype=np.uint8)

# Set once per round by calibrate_character_colour(), reset by reset_calibration()
CHARACTER_HSV = None


def make_sky_mask_roi(img_bgr: np.ndarray, roi: tuple) -> np.ndarray:
    """Apply sky mask to a cropped ROI only — much faster than full image."""
    x1, y1, x2, y2 = roi
    crop = img_bgr[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, SKY_HSV_LOWER, SKY_HSV_UPPER)


def calibrate_character_colour(img_bgr: np.ndarray) -> bool:
    """
    Auto-calibrates CHARACTER_HSV from the first clean frame (score=0, no pipes).
    Returns False (try again next frame) if not enough non-sky pixels found yet.
    """
    global CHARACTER_HSV
    mask = make_sky_mask_roi(img_bgr, CHAR_ROI)
    ys, xs = np.where(mask == 0)

    if len(ys) < 10:
        return False  # nothing found yet — try next frame

    x1, y1, _, _ = CHAR_ROI
    char_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)[y1:y1 + mask.shape[0], x1:x1 + mask.shape[1]]
    pixels = char_hsv[ys, xs]

    lo = np.array([
        max(0, int(np.percentile(pixels[:, 0], 5)) - 15),
        max(0, int(np.percentile(pixels[:, 1], 5)) - 20),
        max(0, int(np.percentile(pixels[:, 2], 5)) - 20),
    ], dtype=np.uint8)
    hi = np.array([
        min(180, int(np.percentile(pixels[:, 0], 95)) + 15),
        min(255, int(np.percentile(pixels[:, 1], 95)) + 20),
        min(255, int(np.percentile(pixels[:, 2], 95)) + 20),
    ], dtype=np.uint8)

    CHARACTER_HSV = (lo, hi)
    print(f"  [Calibrated] {lo} -> {hi}")
    return True


def reset_calibration():
    """Call on every game-over so the bot re-samples the new character/cape colour."""
    global CHARACTER_HSV
    CHARACTER_HSV = None


def detect_character_y(img_bgr: np.ndarray) -> int | None:
    """Median Y of character-coloured pixels in CHAR_ROI, in full-image coords."""
    if CHARACTER_HSV is None:
        return None

    x1, y1, x2, y2 = CHAR_ROI
    crop = img_bgr[y1:y2, x1:x2]
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, CHARACTER_HSV[0], CHARACTER_HSV[1])

    ys = np.where(mask > 0)[0]
    if len(ys) < 5:
        return None

    return int(np.median(ys)) + y1


def detect_gap_y(img_bgr: np.ndarray) -> int | None:
    """Vertical midpoint of the pipe gap in GAP_ROI, in full-image coords."""
    x1, y1, x2, y2 = GAP_ROI
    mask = make_sky_mask_roi(img_bgr, GAP_ROI)

    col_positions = np.linspace(0, mask.shape[1] - 1, GAP_SCAN_COLUMNS, dtype=int)
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