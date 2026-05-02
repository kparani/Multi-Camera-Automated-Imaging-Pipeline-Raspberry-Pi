"""
img_capture.py - Camera capture script
Copy this IDENTICAL file to BOTH Pis at: /home/pi/code/img_capture.py

Called automatically by scan.py - do not run manually unless testing.

Usage (for testing only):
    python3 /home/pi/code/img_capture.py --save_path /home/pi/test_images --pi_id controller --position 0
    python3 /home/pi/code/img_capture.py --save_path /home/pi/test_images --pi_id secondary --position 0

Key approach:
    - picamera2 is initialized ONCE and kept open the whole time
    - Mux switches while camera stays open (Arducam reference approach)
    - Manual focus at fixed lens position 4.0 (works reliably on all 4 ports)
    - Manual exposure for consistent lighting
"""

import subprocess
import os
import argparse
import time
from datetime import datetime
from picamera2 import Picamera2
import cv2

# ─────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────

MUX_COMMANDS = {
    0: "/usr/sbin/i2cset -y 10 0x24 0x24 0x02",
    1: "/usr/sbin/i2cset -y 10 0x24 0x24 0x12",
    2: "/usr/sbin/i2cset -y 10 0x24 0x24 0x22",
    3: "/usr/sbin/i2cset -y 10 0x24 0x24 0x32",
}

IMAGE_WIDTH   = 4656
IMAGE_HEIGHT  = 3496
LENS_POSITION = 4.0     # Fixed manual focus position (~40cm distance)
EXPOSURE_TIME = 15000   # Manual exposure time in microseconds
ANALOGUE_GAIN = 0.8     # Manual analogue gain

# ─────────────────────────────────────────────────────────
# CAPTURE ALL 4 CAMERAS
# ─────────────────────────────────────────────────────────
def capture_all_cameras(save_path, pi_id, position):
    print(f"\nCapturing 4 cameras on [{pi_id}] at position {position}...")
    os.makedirs(save_path, exist_ok=True)

    # Initialize camera ONCE and keep open (Arducam reference approach)
    print("  Initializing camera...")
    picam2 = Picamera2()
    config = picam2.create_still_configuration(
        main={"format": "RGB888", "size": (IMAGE_WIDTH, IMAGE_HEIGHT)}
    )
    picam2.configure(config)
    picam2.set_controls({
        "AfMode":       0,              # Manual focus
        "LensPosition": LENS_POSITION,  # Fixed lens position
        "AeEnable":     False,          # Manual exposure
        "ExposureTime": EXPOSURE_TIME,
        "AnalogueGain": ANALOGUE_GAIN,
    })
    picam2.start()
    print("  Camera started, waiting 3s to settle...")
    time.sleep(3)

    results = []
    for cam_index in range(4):
        print(f"\n  --- Camera {cam_index} ---")

        # Switch mux while camera stays open
        mux_cmd = MUX_COMMANDS[cam_index]
        result = subprocess.run(mux_cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  WARNING: Mux switch failed: {result.stderr.strip()}")
            results.append(False)
            continue

        # Wait for mux to settle
        time.sleep(2)

        # Build filename
        timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
        filename  = f"{pi_id}_pos{position:02d}_cam{cam_index}_{timestamp}.jpg"
        filepath  = os.path.join(save_path, filename)

        # Capture frame
        frame = picam2.capture_array()
        cv2.imwrite(filepath, frame)

        if os.path.exists(filepath):
            size_kb = os.path.getsize(filepath) // 1024
            print(f"  Saved: {filename} ({size_kb} KB)")
            results.append(True)
        else:
            print(f"  ERROR: Image file not created!")
            results.append(False)

        time.sleep(1)

    # Clean up
    picam2.stop()
    picam2.close()

    success_count = sum(results)
    print(f"\n  Captured {success_count}/4 cameras successfully.")

    if success_count < 4:
        failed = [str(i) for i, ok in enumerate(results) if not ok]
        print(f"  Failed cameras: {', '.join(failed)}")
        return False

    return True

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--save_path", type=str, required=True)
    parser.add_argument("--pi_id",     type=str, required=True, choices=["controller", "secondary"])
    parser.add_argument("--position",  type=int, required=True)
    args = parser.parse_args()

    success = capture_all_cameras(
        save_path=args.save_path,
        pi_id=args.pi_id,
        position=args.position,
    )
    exit(0 if success else 1)
