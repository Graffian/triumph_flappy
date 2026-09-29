# Triumph Flappy — Automated iOS Flappy Bird Bot

An automated Python bot that plays Triumph Flappy Bird on an iOS device in real time. It captures high-rate screen frames via **WebDriverAgent (WDA)**, detects character and obstacle gap positions using **OpenCV**, and controls character flight using a **velocity-aware PD controller**.

---

## ⚡ Quick Start

Follow these 5 steps to get the bot running on a connected iPhone:

1. **Prerequisite Check**: Ensure you have macOS + Xcode to install WebDriverAgent onto your iPhone, an iOS device connected via USB with the Flappy game installed, and Python 3.9+.
2. **Setup Virtual Environment & Install Dependencies**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Build & Launch WebDriverAgent (WDA)**:
   Open `WebDriverAgent.xcodeproj` in Xcode, select your connected iPhone, sign with your Apple ID, and run the `WebDriverAgentRunner` scheme. (See [`wdaSetup.md`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/wdaSetup.md) for step-by-step WDA build instructions).
4. **Start USB Port Forwarding** (Forward BOTH ports 8100 and 9100):
   ```bash
   # In a terminal window:
   iproxy 8100 8100 & iproxy 9100 9100 &
   # OR using tidevice:
   # tidevice relay 8100 8100 & tidevice relay 9100 9100 &
   ```
   Verify services are responding:
   ```bash
   curl http://localhost:8100/status
   curl -i http://localhost:9100
   ```
5. **Run the Bot**:
   Open the Flappy game on your iPhone, ensure the start/idle screen is visible, then execute:
   ```bash
   python main.py
   ```
   *To stop the bot at any time, press `Ctrl+C` in your terminal.*

---

## 🏗️ Project Architecture & How It Works

```
                        ┌──────────────────────────────────────────────┐
                        │              Physical iOS Device             │
                        │   Running Flappy Game & WebDriverAgent       │
                        └──────────────────────┬───────────────────────┘
                                               │
                                      USB Cable (iproxy)
                                               │
                     ┌─────────────────────────┴─────────────────────────┐
                     │                                                   │
          Port 8100 (REST API)                               Port 9100 (MJPEG Stream)
        Actions / Taps / Sessions                              Live Screen Screenshots
                     │                                                   │
                     ▼                                                   ▼
       ┌───────────────────────────┐                       ┌───────────────────────────┐
       │          wda.py           │                       │          wda.py           │
       │  (tap, get_session, etc)  │                       │  (_mjpeg_reader worker)   │
       └─────────────▲─────────────┘                       └─────────────┬─────────────┘
                     │                                                   │
                     │                 PIL / OpenCV Image                │
                     │                         │                         │
                     │                         ▼                         │
                     │             ┌───────────────────────┐             │
                     │             │       main.py         │             │
                     │             │ (Double-Buffered      │             │
                     │             │  Prefetch Loop)       │             │
                     │             └───────────┬───────────┘             │
                     │                         │                         │
                     │                         ▼                         │
                     │             ┌───────────────────────┐             │
                     │             │       vision.py       │             │
                     │             │  - Sky Masking        │             │
                     │             │  - HSV Auto-Calib     │             │
                     │             │  - Char & Gap Y Pos   │             │
                     │             └───────────┬───────────┘             │
                     │                         │                         │
                     │                         ▼                         │
                     │             ┌───────────────────────┐             │
                     │             │      control.py       │             │
                     │             │  - ROIs & Coordinates │             │
                     │             │  - PD Tap Controller  │             │
                     └─────────────┤   (how_many_taps)     │             │
                                   └───────────────────────┘             │
```

### Module Overview

- [`wda.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/wda.py): Manages HTTP REST API sessions with WDA (`http://localhost:8100`), reads real-time JPEG frames from WDA's MJPEG stream (`http://localhost:9100`), and sends touch tap events (`/session/{id}/actions`).
- [`vision.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/vision.py): Computer vision processing pipeline. Masks sky background (`SKY_HSV_LOWER`/`UPPER`), auto-calibrates the character's HSV color profile on clean initial frames (`calibrate_character_colour`), and calculates pixel Y positions for both the character (`detect_character_y`) and obstacle gaps (`detect_gap_y`).
- [`control.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/control.py): Stores screen ROI constants (`CHAR_ROI`, `GAP_ROI`), logical tap coordinates (`TAP_X_LOGICAL`, `TAP_Y_LOGICAL`), coordinate scale factor (`COORD_SCALE = 3.0`), and implements the Proportional-Derivative (PD) controller (`how_many_taps`) to calculate flap multi-tap counts based on error and falling velocity.
- [`main.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/main.py): Entry point and execution loop. Uses an asynchronous background prefetch thread (`start_prefetch` / `get_frame`) to overlap network screenshot transfer with vision processing, manages round lifecycle, and triggers game-over auto-restarts.
- [`benchmark.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/benchmark.py): Measures screenshot acquisition speed over WDA to determine frame rates.
- [`calibrate.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/calibrate.py): Generates visual overlay PNGs in `./calib_out/` to verify sky mask accuracy and ROI box alignment.
- [`physics_calibrate.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/physics_calibrate.py): Estimates character free-fall gravity ($g$ in $px/s^2$) and flap impulse ($v$ in $px/s$).

---

## 💻 Hardware, Software & Platform Requirements

### Operating System Compatibility Matrix

| Phase | macOS | Linux | Windows |
|---|---|---|---|
| **WDA Building & Installation** (Xcode) | **Required** | Not Supported | Not Supported |
| **Running Python Bot & Relaying USB** | **Supported** | **Supported** | **Supported** (via `tidevice`) |

> **Note**: Building and installing WebDriverAgentRunner onto a physical iPhone **requires macOS with Xcode**. Once WDA is installed on the iPhone and running, you can connect the iPhone to a **Linux** or **Windows** host machine and run the Python bot script by using `tidevice` or `iproxy` to relay ports 8100 and 9100.

### Prerequisites

1. **iOS Device**: Physical iPhone running iOS 15+ (tested on iPhone 15 Pro resolution, 1320×2868 physical px / 3x Retina scaling).
2. **USB Cable**: Physical Lightning or USB-C cable connecting device to host computer.
3. **Apple Developer Account**: Required in Xcode to sign the `WebDriverAgentRunner` app.
4. **Python**: Python **3.9 or higher**.
5. **Port Forwarding Utility**: `libimobiledevice` (`iproxy`) or `tidevice`.

---

## 🛠️ Step-by-Step Installation & Setup

### 1. Environment & Dependencies

Clone the repository and set up a Python virtual environment:

```bash
git clone https://github.com/reddy895/triumph_flappy.git
cd triumph_flappy

python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. WebDriverAgent (WDA) Setup

WebDriverAgent runs on the iOS device as a W3C HTTP server.

1. Clone WebDriverAgent:
   ```bash
   git clone https://github.com/appium/WebDriverAgent.git
   cd WebDriverAgent
   ```
2. Open `WebDriverAgent.xcodeproj` in **Xcode**.
3. Select `WebDriverAgentRunner` scheme, select your connected iPhone as destination.
4. Under **Signing & Capabilities**, select your Apple Developer Development Team.
5. In Xcode menu, click **Product -> Test** to build and run WDA on the iPhone.
6. On the iPhone, go to **Settings -> General -> VPN & Device Management** and trust your Developer App certificate. Also enable **Developer Mode** under **Settings -> Privacy & Security**.

For detailed WDA setup guidelines, see [`wdaSetup.md`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/wdaSetup.md).

### 3. Required Ports & USB Forwarding

The bot relies on **two active network ports** forwarded from the iPhone over USB to `localhost`:

- **Port 8100**: WebDriverAgent HTTP REST API (for session management and touch input).
- **Port 9100**: WebDriverAgent MJPEG Stream (for real-time video screenshot capturing).

Run port forwarding in your terminal:

```bash
# Using iproxy (macOS / Linux via libimobiledevice):
iproxy 8100 8100 &
iproxy 9100 9100 &

# OR using tidevice (cross-platform):
tidevice relay 8100 8100 &
tidevice relay 9100 9100 &
```

#### Test Port Endpoints:

Verify ports are forwarded correctly before starting the bot:

```bash
# Test Port 8100 (WDA Status)
curl http://localhost:8100/status

# Test Port 9100 (MJPEG Video Stream)
curl -i http://localhost:9100
```

---

## 🚀 Running the Bot & Utilities

### 1. Benchmark WDA Latency (Recommended First Step)

Run `benchmark.py` to test screenshot capture latency:

```bash
python benchmark.py
```
- **< 60ms median**: Excellent (15+ fps).
- **60–100ms median**: Workable; prefetch thread will maintain speed.
- **> 100ms median**: High latency; ensure USB 3 connection and close heavy background apps.

### 2. Verify Vision & ROI Calibration

Run `calibrate.py` while the game is on a clean initial screen (score = 0, character visible, no pipes):

```bash
python calibrate.py
```
This generates diagnostic PNG images inside `./calib_out/`:
- `01_raw.png`: Unprocessed frame.
- `02_sky_mask.png`: Sky HSV masking test.
- `03_roi_overlay.png`: `CHAR_ROI`, `GAP_ROI`, ceiling, and floor lines overlay.
- `04_detection.png`: Character and gap detection lines.

### 3. Estimate Physics Parameters (Optional)

Run `physics_calibrate.py` to measure gravity ($g$) and flap impulse ($v$):

```bash
python physics_calibrate.py
```

### 4. Run the Main Bot Loop

Ensure the Flappy game is open on your iPhone screen, then execute:

```bash
python main.py
```

#### Expected Output:

```
Bot running — Ctrl+C to stop
  [hue span check] 32  lo=[10 120 140] hi=[35 255 255]
  [Calibrated] [10 120 140] -> [35 255 255]
  Starting game...
  frame 58ms  char=950  gap=940  taps=0
  frame 61ms  char=985  gap=940  taps=1
  frame 64ms  char=962  gap=940  taps=0
  ...
  Game over — restarting
```

#### How to Stop:
Press `Ctrl+C` in the terminal to stop `main.py`.

---

## ❓ Troubleshooting & Common Errors

### 1. WDA Connection Failure (`localhost:8100` Unavailable)
- **Symptom**: `requests.exceptions.ConnectionError` or `Connection refused` on `http://localhost:8100`.
- **Cause**: Port 8100 is not forwarded or WebDriverAgent process on iPhone crashed/stopped.
- **Fix**:
  1. Check if WDA is running on iPhone (Xcode status should say "Running WebDriverAgentRunner").
  2. Run `iproxy 8100 8100` (or `tidevice relay 8100 8100`).
  3. Verify with `curl http://localhost:8100/status`.

### 2. MJPEG Stream Unavailable (`RuntimeError: No new MJPEG frame received`)
- **Symptom**: `take_screenshot()` throws `RuntimeError: No new MJPEG frame received`.
- **Cause**: Port 9100 is not forwarded from the iPhone to `localhost`.
- **Fix**:
  1. Forward port 9100: `iproxy 9100 9100` or `tidevice relay 9100 9100`.
  2. Verify with `curl -i http://localhost:9100`.

### 3. Python Dependency Errors (`ModuleNotFoundError`)
- **Symptom**: `ModuleNotFoundError: No module named 'cv2'` or `'PIL'`.
- **Cause**: Script executed outside virtual environment or dependencies not installed.
- **Fix**:
  ```bash
  source venv/bin/activate
  pip install -r requirements.txt
  ```

### 4. Device Connection Problems
- **Symptom**: `iproxy` exits with device communication error or device dismounts.
- **Cause**: iPhone locked, "Trust This Computer" prompt ignored, or bad USB cable.
- **Fix**: Unlock iPhone screen, select "Trust", replace USB cable, and restart `iproxy`.

### 5. Incorrect Screen Coordinate Calibration / Character Not Detected
- **Symptom**: Console outputs `[Calibration rejected] hue range too wide` or character position remains `None`.
- **Cause**: Game screen resolution differs from default 1320×2868 (iPhone 15 Pro @3x), or game was not on a clean starting screen.
- **Fix**: Run `python calibrate.py`, inspect `calib_out/03_roi_overlay.png`, and update `COORD_SCALE`, `CHAR_ROI`, or `GAP_ROI` constants in [`control.py`](file:///home/reddy895/Downloads/forked%20repo/triumph_flappy/control.py) to match your device dimensions.

---

## 📄 License & Attribution

This project is built for research and educational iOS automation testing. WebDriverAgent is open-source software maintained by Appium/Meta.
