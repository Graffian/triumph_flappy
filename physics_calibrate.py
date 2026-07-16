"""
physics_calibrate.py — measures gravity (px/s^2) and flap impulse (px/s kick)
by watching the character fall freely, then tapping once and watching the kick.

Run on the idle/start screen and DO NOT TAP ANYTHING YOURSELF. The script
taps on its own, at the right moments, and prints progress the whole way
so you can see it's alive.
"""

import time
import numpy as np

import vision
from wda import get_session, take_screenshot, tap
from main import pil_to_bgr
from control import TAP_X_LOGICAL, TAP_Y_LOGICAL


def collect_samples(duration_s: float, label: str):
    samples = []  # (t, y)
    t0 = time.perf_counter()
    n = 0
    while time.perf_counter() - t0 < duration_s:
        img = take_screenshot()
        bgr = pil_to_bgr(img)
        y = vision.detect_character_y(bgr)
        t = time.perf_counter() - t0
        if y is not None:
            samples.append((t, y))
        n += 1
        if n % 5 == 0:
            print(f"    [{label}] t={t:.2f}s  y={y}")
    return samples


def fit_gravity(samples):
    t = np.array([s[0] for s in samples])
    y = np.array([s[1] for s in samples])
    A = np.stack([np.ones_like(t), t, 0.5 * t**2], axis=1)
    coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    y0, v0, g = coeffs
    return g, v0


def main():
    get_session()

    print("Calibrating character colour (do NOT tap)...")
    calibrated = False
    attempts = 0
    while not calibrated:
        img = take_screenshot()
        bgr = pil_to_bgr(img)
        calibrated = vision.calibrate_character_colour(bgr)
        attempts += 1
        if attempts % 5 == 0:
            print(f"  ... still trying ({attempts} frames so far)")
        if attempts >= 100:
            print("  Giving up after 100 attempts — is the game actually on screen?")
            return
    print(f"  Calibrated after {attempts} frame(s).")

    print("Tapping to start the round...")
    time.sleep(0.3)
    tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)

    # Confirm the round actually started by waiting for the character to
    # MOVE — not just be detected. A frozen idle frame gives y with zero
    # variance, which is exactly what produced g=0 last time.
    print("Waiting for character to actually start moving...")
    y_positions = []
    settle_t0 = time.perf_counter()
    while time.perf_counter() - settle_t0 < 2.0:
        img = take_screenshot()
        bgr = pil_to_bgr(img)
        y = vision.detect_character_y(bgr)
        if y is not None:
            y_positions.append(y)
        if len(y_positions) >= 5 and (max(y_positions[-5:]) - min(y_positions[-5:])) > 15:
            print(f"  Movement detected (recent y range: {y_positions[-5:]})")
            break
    else:
        print("  WARNING: no clear movement detected in 2s — proceeding anyway, "
              "but results may be unreliable. Check the game actually started.")

    print("Recording free-fall (do NOT tap, ~1.2s)...")
    fall_samples = collect_samples(1.2, "fall")
    print(f"  Got {len(fall_samples)} samples.")
    if len(fall_samples) < 5:
        print("  Not enough samples — character may have hit ground/pipe, or "
              "detection failed. Re-run and don't tap during this phase.")
        return

    y_span = max(s[1] for s in fall_samples) - min(s[1] for s in fall_samples)
    print(f"  y range during fall: {y_span:.0f}px")
    if y_span < 10:
        print("  Character barely moved — this looks like a frozen/idle frame, "
              "not a real fall. Re-run.")
        return

    g, v_before_tap = fit_gravity(fall_samples)
    print(f"  Gravity estimate: {g:.1f} px/s^2")

    print("Tapping once to measure flap impulse...")
    tap(TAP_X_LOGICAL, TAP_Y_LOGICAL)

    post_samples = collect_samples(0.6, "post-tap")
    print(f"  Got {len(post_samples)} post-tap samples.")
    if len(post_samples) < 4:
        print("  Not enough post-tap samples — try again.")
        return

    t = np.array([s[0] for s in post_samples[:4]])
    y = np.array([s[1] for s in post_samples[:4]])
    A = np.stack([np.ones_like(t), t], axis=1)
    coeffs, *_ = np.linalg.lstsq(A, y, rcond=None)
    v_after_tap = coeffs[1]

    flap_impulse = v_after_tap - v_before_tap
    print(f"  Velocity before tap:  {v_before_tap:.1f} px/s")
    print(f"  Velocity after tap:   {v_after_tap:.1f} px/s")
    print(f"  Flap impulse:         {flap_impulse:.1f} px/s")

    print("\n--- Paste these into predictive_control.py ---")
    print(f"GRAVITY_PX_S2   = {g:.1f}")
    print(f"FLAP_IMPULSE    = {flap_impulse:.1f}")


if __name__ == "__main__":
    main()