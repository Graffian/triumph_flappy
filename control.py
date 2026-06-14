"""
control.py — coordinate/ROI constants and the velocity-aware tap controller.
"""

# ── Physical pixel constants (from image analysis) ──
CHAR_X_PHYSICAL = 280
SCAN_HALF_WIDTH = 50

CEILING_Y_PHYSICAL = 283
FLOOR_Y_PHYSICAL = 1770

GAP_SCAN_X_START = 430   # ahead of character
GAP_SCAN_X_END = 730
GAP_SCAN_COLUMNS = 15

# ── Crop ROIs (process only what you need) ──
CHAR_ROI = (
    max(0, CHAR_X_PHYSICAL - SCAN_HALF_WIDTH),   # x1
    CEILING_Y_PHYSICAL,                          # y1
    CHAR_X_PHYSICAL + SCAN_HALF_WIDTH,           # x2
    FLOOR_Y_PHYSICAL,                            # y2
)

GAP_ROI = (
    GAP_SCAN_X_START,
    CEILING_Y_PHYSICAL,
    GAP_SCAN_X_END,
    FLOOR_Y_PHYSICAL,
)

# ── Logical tap coordinate ──
TAP_X_LOGICAL = 220
TAP_Y_LOGICAL = 478

# ── Control tuning ──
FLAP_THRESHOLD = 30      # physical px — signal must exceed this to tap
FLAP_KP = 1.0            # position gain
FLAP_KD = 0.5            # velocity gain (reacts to how fast it's falling)
MAX_TAPS_PER_FRAME = 3   # cap multi-taps so it doesn't rocket into ceiling


_prev_char_y = None


def reset_controller():
    """Call this on every game restart so velocity isn't computed across rounds."""
    global _prev_char_y
    _prev_char_y = None


def how_many_taps(char_y: int, gap_y: int) -> int:
    """
    Returns 0-MAX_TAPS_PER_FRAME based on position error and fall velocity.

    error    = char_y - gap_y   (positive = below the gap, needs to go up)
    velocity = char_y - prev_y  (positive = falling)
    signal   = Kp*error + Kd*velocity
    """
    global _prev_char_y

    error = char_y - gap_y
    velocity = (char_y - _prev_char_y) if _prev_char_y is not None else 0
    _prev_char_y = char_y

    signal = FLAP_KP * error + FLAP_KD * velocity

    if signal <= FLAP_THRESHOLD:
        return 0
    if signal < 80:
        return 1
    if signal < 160:
        return 2
    return min(MAX_TAPS_PER_FRAME, 3)