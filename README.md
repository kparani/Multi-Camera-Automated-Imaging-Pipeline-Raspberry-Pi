# 360° Root Phenotyping Scanner

An automated imaging system for capturing high-resolution 360° photographs of plant structures using dual Raspberry Pi microcontrollers and 8 synchronized cameras.

---

## System Overview

This system rotates using a stepper motor and captures 8 images from 30 angles simultaneously at each position producing a full 360° image dataset for 3D reconstruction of the plant structure.

**Hardware:**
- 2x Raspberry Pi 4B (Controller + Secondary)
- 2x Arducam UC512 Quad-Camera Multiplexer HATs
- 8x Arducam IMX519 16MP Autofocus Camera Modules
- Stepper motor (GPIO controlled, 240,000 steps/rev)
- Direct ethernet connection between Pis
- Digital display connecetd to one of the raspberry pi.

**How it works:**
1. Run `scan.py -n 5` on the controller Pi
2. Controller captures 4 images from its cameras
3. Controller SSHes to secondary Pi and triggers 4 more images
4. Stepper motor rotates to next position
5. Repeat for all positions
6. All images transferred to controller and saved in a dated folder, on completion all the images in teh secondary pi is deleted

---

## Repository Structure

```
root-scanner/
├── original_code/       # Original scripts (with documented bugs)
│   ├── main.py
│   ├── img_capture.py
│   └── img_transfer.py
├── improved_code/       # Rewritten scripts (production ready)
    ├── scan.py
    └── img_capture.py

```

---

## Why the Code Was Rewritten

The original code had several critical bugs that prevented the system from working correctly. Here is a comparison:

| Issue | Original Code | Improved Code |
|-------|--------------|---------------|
| **Image transfer path** | SCP looked in `/home/pi/code/*/*.jpg` but images saved to `/home/pi/image_data/` — nothing ever transferred | Correct paths used throughout, images reliably transferred after every scan |
| **Save path ignored** | `img_capture.py` always saved to `os.getcwd()/image_data/` regardless of argument passed — unpredictable via SSH | Save path passed as explicit argument `--save_path`, always saved to correct location |
| **Images deleted each cycle** | `img_cap_remote.sh` ran `rm -rf` at start of every cycle — only the last cycle's images survived | No deletion — all images from all positions accumulated safely |
| **i2cset path** | Called as `i2cset` — not found in SSH sessions where `/usr/sbin` is not in PATH | Full path `/usr/sbin/i2cset` used in all scripts |
| **No retry on failure** | On capture failure, scan position silently skipped with no retry | Failures logged clearly with position tracking |
| **Image naming** | Timestamp-only filenames with no position or Pi ID — impossible to sort | Clear naming: `controller_pos02_cam3_2026-04-11.jpg` |
| **Autofocus approach** | Each camera opened and closed separately — VCM driver lost context on mux switch | `picamera2` kept open continuously, mux switches while camera runs (Arducam reference approach) |
| **Manual exposure** | Not set — inconsistent brightness across cameras | Fixed `ExposureTime=15000`, `AnalogueGain=0.8` for consistent images |

---

## Usage

### Requirements
Both Pis must have:
- Raspberry Pi OS Bookworm (64-bit)
- `picamera2`, `opencv-python` installed
- `ak7375` VCM driver loaded: `echo "ak7375" | sudo tee /etc/modules-load.d/ak7375.conf`
- Passwordless SSH from controller to secondary Pi
- `/boot/firmware/config.txt`: `camera_auto_detect=0` and `dtoverlay=imx519`

### Run a Scan
```bash
# On controller Pi:
python3 /home/pi/code/scan.py -n 5
# -n = number of positions (5 positions = 72° per step = full 360°)
```

Images saved to: `/home/pi/scans/YYYY-MM-DD/`

### Test Single Pi Cameras
```bash
python3 /home/pi/code/img_capture.py --save_path /home/pi/test --pi_id controller --position 0
```

---

## Known Issue — Autofocus on Camera Ports 1 & 3

Cameras connected to ports 1 and 3 of the UC512 HAT do not autofocus correctly — the lens position gets stuck at maximum (lp=12) instead of finding focus at ~40cm (lp~3.5). Cameras on ports 0 and 2 autofocus correctly.

**Diagnosis:** The AK7375 VCM driver initializes at boot for the first camera (port 0). When the mux switches to ports 1 and 3, the VCM driver loses I2C communication with those cameras' lens motors — confirmed by monitoring `lp=%lp` in `rpicam-hello`.

**Current workaround:** Fixed manual focus at `LensPosition=4.0` for all cameras — provides acceptable sharpness at 40cm scanning distance.

**Status:** Arducam support contacted. Awaiting firmware fix for UC512 HAT VCM routing on odd-numbered ports.

---

