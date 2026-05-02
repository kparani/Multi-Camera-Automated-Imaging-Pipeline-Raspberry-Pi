"""
test_arducam.py - Test script following Arducam's own reference code approach
Camera stays open the whole time, mux switches while camera is running
Manual focus at fixed lens position

Run: python3 /home/pi/test_arducam.py
"""

import subprocess
import os
import time
from datetime import datetime
from picamera2 import Picamera2
import cv2

SAVE_PATH = "/home/pi/test_arducam"
os.makedirs(SAVE_PATH, exist_ok=True)

MUX_COMMANDS = [
    "/usr/sbin/i2cset -y 10 0x24 0x24 0x02",
    "/usr/sbin/i2cset -y 10 0x24 0x24 0x12",
    "/usr/sbin/i2cset -y 10 0x24 0x24 0x22",
    "/usr/sbin/i2cset -y 10 0x24 0x24 0x32",
]

# Initialize camera ONCE and keep it open
print("Initializing camera...")
picam2 = Picamera2()
config = picam2.create_still_configuration(
    main={"format": "RGB888", "size": (4656, 3496)}
)
picam2.configure(config)

# Manual focus and manual exposure - exactly like Arducam reference code
picam2.set_controls({
    "AfMode":       0,      # manual focus
    "LensPosition": 4.0,    # fixed focus position
    "AeEnable":     False,  # manual exposure
    "ExposureTime": 15000,
    "AnalogueGain": 0.8,
})

picam2.start()
print("Camera started, waiting 3s to settle...")
time.sleep(3)

# Capture all 4 cameras with camera staying open
for cam_index, mux_cmd in enumerate(MUX_COMMANDS):
    print(f"\n--- Camera {cam_index} ---")
    
    # Switch mux while camera is running
    subprocess.run(mux_cmd, shell=True)
    time.sleep(2)  # wait for mux to settle
    
    # Capture frame
    frame = picam2.capture_array()
    
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M-%S')
    filename = f"cam{cam_index}_{timestamp}.jpg"
    filepath = os.path.join(SAVE_PATH, filename)
    
    cv2.imwrite(filepath, frame)
    size_kb = os.path.getsize(filepath) // 1024
    print(f"Saved: {filename} ({size_kb} KB)")

picam2.stop()
picam2.close()
print("\nDone! All 4 images saved to /home/pi/test_arducam/")
