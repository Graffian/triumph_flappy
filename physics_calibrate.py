"""
physics_calibrate.py — measures gravity (px/s^2) and flap impulse (px/s kick)
by watching the character fall freely, then tapping once and watching the kick.

Run on the idle/start screen. It will:
  1. Auto-tap to start the round (uses existing calibration flow)
  2. Record ~1.5s of free-fall (no taps) to fit gravity
  3. Fire one tap and record the velocity change to measure flap impulse
"""

import time
import numpy as np

import vision
from wda import get_session, take_screenshot, tap
from main import pil_to_bgr
from control import TAP_X_LOGICAL, TAP_Y_LOGICAL


def collect_samples(duration_s: float):
    samples = []  # (t, y)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < duration_s:
        img = take_screenshot()
        bgr = pil_to_bgr(img)
        y = vision.detect_character_y(bgr)
        if y is not None:
            samples.append((time.perf_counter() - t0, y))
    return samples


def fit_gravity(samples):
    """Fit y(t) = y0 + v0*t + 0.5*g*t^2 via least squares."""
    t = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    A = np.stack([np.ones_like(t), t, 0.5 * t**2], axis=1)
    coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    y0, v0, g = coeffs
    return g, v0  # px/s^2, px/s at t=0 of this window


def main():
    get_session()
    print("Calibrating character colour first...")
    calibrated = False
    while not calibrated:
        img = take_screenshot()
        bgr = pil_to_bgr(img)
        calibrated = vision.calibrate_character_colour(bgr)
    print("  OK. Starting round...")
    time.sleep(0.3)
    tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)
    time.sleep(0.5)  # let the round actually begin

    print("Recording free-fall (no taps, ~1.2s)...")
    fall_samples = collect_samples(1.2)
    if len(fall_samples) < 5:
        print("  Not enough samples — character may have hit ground/pipe. Try again.")
        return

    g, v_before_tap = fit_gravity(fall_samples)
    print(f"  Gravity estimate: {g:.1f} px/s^2")

    # Measure flap impulse: tap once, then watch velocity right after
    print("Tapping once to measure flap impulse...")
    t_tap = time.perf_counter()
    tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)

    post_samples = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 0.6:
        img = take_screenshot()
        bgr = pil_to_bgr(img)
        y = vision.detect_character_y(bgr)
        if y is not None:
            post_samples.append((time.perf_counter() - t0, y))

    if len(post_samples) < 4:
        print("  Not enough post-tap samples — try again.")
        return

    # Velocity immediately after tap, from first few samples (before gravity
    # curves it back down much) — simple two-point slope on earliest points.
    t = np.array([s[0] for s in post_samples[:4]])
    y = np.array([s[1] for s in post_samples[:4]])
    A = np.stack([np.ones_like(t), t], axis=1)
    coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    v_after_tap = coeffs[1]  # px/s, immediately post-tap

    flap_impulse = v_after_tap - v_before_tap  # negative = upward kick
    print(f"  Velocity before tap:  {v_before_tap:.1f} px/s")
    print(f"  Velocity after tap:   {v_after_tap:.1f} px/s")
    print(f"  Flap impulse:         {flap_impulse:.1f} px/s")

    print("\n--- Paste these into predictive_control.py ---")
    print(f"GRAVITY_PX_S2   = {g:.1f}")
    print(f"FLAP_IMPULSE    = {flap_impulse:.1f}")


if __name__ == "__main__":
    main()