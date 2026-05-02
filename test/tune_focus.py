"""
tune_focus.py - Find the best lens position for cameras 1 and 3
Run: python3 /home/pi/tune_focus.py
"""

import subprocess
import os
import time
from datetime import datetime
from picamera2 import Picamera2
import cv2

SAVE_PATH = "/home/pi/tune_focus"
os.makedirs(SAVE_PATH, exist_ok=True)

MUX_CAM1 = "/usr/sbin/i2cset -y 10 0x24 0x24 0x12"
MUX_CAM3 = "/usr/sbin/i2cset -y 10 0x24 0x24 0x32"

# Lens positions to test
LENS_POSITIONS = [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]

print("Initializing camera...")
picam2 = Picamera2()
config = picam2.create_still_configuration(
    main={"format": "RGB888", "size": (4656, 3496)}
)
picam2.configure(config)
picam2.set_controls({
    "AeEnable":     False,
    "ExposureTime": 15000,
    "AnalogueGain": 0.8,
})
picam2.start()
time.sleep(3)

for cam_index, mux_cmd in [(1, MUX_CAM1), (3, MUX_CAM3)]:
    print(f"\n=== Testing Camera {cam_index} ===")
    
    # Switch to this camera
    subprocess.run(mux_cmd, shell=True)
    time.sleep(2)
    
    for lp in LENS_POSITIONS:
        print(f"  Lens position: {lp}")
        
        # Set manual focus to this position
        picam2.set_controls({
            "AfMode":       0,
            "LensPosition": lp,
        })
        time.sleep(2)  # wait for lens to move
        
        frame = picam2.capture_array()
        filename = f"cam{cam_index}_lp{lp:.1f}.jpg"
        filepath = os.path.join(SAVE_PATH, filename)
        cv2.imwrite(filepath, frame)
        print(f"  Saved: {filename}")

picam2.stop()
picam2.close()
print("\nDone! Check images in /home/pi/tune_focus/")
print("Find the sharpest lens position for each camera and note it down.")
