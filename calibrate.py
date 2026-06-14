"""
calibrate.py — sanity-check sky mask, ROIs, and detection on a single live frame.

Run AFTER benchmark.py. Saves annotated PNGs to ./calib_out/ so you can eyeball
whether SKY_HSV_LOWER/UPPER and the ROI boxes line up with the real screen.

For a useful calibration check, run this while the game is on a CLEAN frame
(score = 0, character visible, no pipes yet).
"""

import os

import cv2

import vision
from wda import get_session, take_screenshot
from main import pil_to_bgr
from control import CHAR_ROI, GAP_ROI, CEILING_Y_PHYSICAL, FLOOR_Y_PHYSICAL

OUT_DIR = "calib_out"


def draw_roi(img, roi, color, label):
    x1, y1, x2, y2 = roi
    cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
    cv2.putText(img, label, (x1, max(0, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    get_session()

    img = take_screenshot()
    bgr = pil_to_bgr(img)
    cv2.imwrite(f"{OUT_DIR}/01_raw.png", bgr)

    # Full-frame sky mask — visual check of SKY_HSV_LOWER/UPPER
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    full_sky = cv2.inRange(hsv, vision.SKY_HSV_LOWER, vision.SKY_HSV_UPPER)
    cv2.imwrite(f"{OUT_DIR}/02_sky_mask.png", full_sky)

    # ROI overlay — check CHAR_ROI/GAP_ROI/ceiling/floor line up with the device screen
    overlay = bgr.copy()
    draw_roi(overlay, CHAR_ROI, (0, 255, 0), "CHAR_ROI")
    draw_roi(overlay, GAP_ROI, (0, 0, 255), "GAP_ROI")
    cv2.line(overlay, (0, CEILING_Y_PHYSICAL), (overlay.shape[1], CEILING_Y_PHYSICAL), (255, 255, 0), 2)
    cv2.line(overlay, (0, FLOOR_Y_PHYSICAL), (overlay.shape[1], FLOOR_Y_PHYSICAL), (255, 255, 0), 2)
    cv2.imwrite(f"{OUT_DIR}/03_roi_overlay.png", overlay)

    # Calibration + detection
    ok = vision.calibrate_character_colour(bgr)
    print(f"Calibration on this frame: {'OK' if ok else 'FAILED (need a clean frame, score=0, no pipes)'}")

    if ok:
        char_y = vision.detect_character_y(bgr)
        gap_y = vision.detect_gap_y(bgr)
        print(f"  detect_character_y -> {char_y}")
        print(f"  detect_gap_y       -> {gap_y}")

        annotated = bgr.copy()
        draw_roi(annotated, CHAR_ROI, (0, 255, 0), "CHAR_ROI")
        draw_roi(annotated, GAP_ROI, (0, 0, 255), "GAP_ROI")
        if char_y is not None:
            cv2.line(annotated, (0, char_y), (annotated.shape[1], char_y), (0, 255, 0), 2)
        if gap_y is not None:
            cv2.line(annotated, (0, gap_y), (annotated.shape[1], gap_y), (0, 0, 255), 2)
        cv2.imwrite(f"{OUT_DIR}/04_detection.png", annotated)

    print(f"\nCheck {OUT_DIR}/ for: raw frame, sky mask, ROI overlay, detection lines.")


if __name__ == "__main__":
    main()