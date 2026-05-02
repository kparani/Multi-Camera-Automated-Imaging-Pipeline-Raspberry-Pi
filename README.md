# Automated 360° Imaging System using Raspberry Pi & Arducam UC512

A distributed embedded system for automated 360° image acquisition of plant root structures using dual Raspberry Pi 4B microcontrollers, 8x 16MP autofocus cameras, and a GPIO-controlled stepper motor.

---

## Hardware

| Component | Details |
|-----------|---------|
| Controller Pi | Raspberry Pi 4B — IP: 192.168.1.5 |
| Secondary Pi | Raspberry Pi 4B — IP: 192.168.1.6 |
| OS | Raspberry Pi OS Bookworm (64-bit) |
| Camera HAT | Arducam UC512 Quad-Camera Multiplexer (x2) |
| Cameras | 8x Arducam IMX519 16MP Autofocus Modules (4 per Pi) |
| Stepper Motor | GPIO controlled — DIR pin 27, STEP pin 17 — 240,000 steps/rev |
| Real-time Display | Terminal progress output — position count, images captured, transfer status | 
| Connection | Direct ethernet cable between both Pis |

---

## Repository Structure

```
root-scanner/
├── scan.py           # Main scan controller — runs on Controller Pi only
└── img_capture.py    # Camera capture script — deployed identically on both Pis
```

---

## How It Works

### scan.py — Main Controller Script

Run on the Controller Pi with the number of scan positions as argument:

```bash
python3 scan.py -n 5
```

This performs a full 360° scan in 5 steps(can be changed based on the no of angles required). For each position it:

1. Calls `img_capture.py` locally to capture 4 images from the Controller Pi cameras
2. SSHes into the Secondary Pi and calls `img_capture.py` remotely to capture 4 more images
3. Moves the stepper motor to the next position

After all positions are complete:

4. Transfers all images from Secondary Pi to Controller Pi via SCP
5. Cleans up temporary images on Secondary Pi
6. Saves everything to `/home/pi/scans/YYYY-MM-DD/` with a clear naming convention

**Image naming convention:**
```
controller_pos02_cam3_2026-04-11-14-32-01.jpg
secondary_pos02_cam3_2026-04-11-14-32-05.jpg
```

**Key parameters inside scan.py:**
```python
SECONDARY_IP    = '192.168.1.6'
SECONDARY_USER  = 'pi'
SECONDARY_SAVE  = '/home/pi/scan_images'
CONTROLLER_SAVE = '/home/pi/scans'
CAPTURE_SCRIPT  = '/home/pi/code/img_capture.py'
DIR_PIN         = 27
STEP_PIN        = 17
STEPS_PER_REV   = 25 * 9600   # 240,000 steps per full revolution
```

---

### img_capture.py — Camera Capture Script

Deployed identically on both Pis. Called by `scan.py` with arguments:

```bash
python3 img_capture.py --save_path /home/pi/scans/2026-04-11 --pi_id controller --position 2
```

**Key design decisions:**

**1. picamera2 initialized once and kept open**

The camera instance is started once and remains open for all 4 captures. The Arducam UC512 mux is switched while the camera stays running. This is critical — opening and closing the camera between switches causes the AK7375 VCM driver to lose context with the camera lens motor on subsequent ports.

```python
picam2 = Picamera2()
picam2.configure(config)
picam2.set_controls({...})
picam2.start()

for cam_index in range(4):
    subprocess.run(MUX_COMMANDS[cam_index], shell=True)  # switch mux
    time.sleep(2)                                         # allow mux to settle
    frame = picam2.capture_array()                        # capture frame
    cv2.imwrite(filepath, frame)                          # save image

picam2.stop()
```

**2. Manual exposure for consistency**

Auto exposure is disabled so all 8 cameras produce images with identical brightness regardless of slight lighting differences between camera positions:

```python
picam2.set_controls({
    "AfMode":       0,        # Manual focus mode
    "LensPosition": 4.0,      # Fixed focus at ~40cm working distance
    "AeEnable":     False,    # Manual exposure
    "ExposureTime": 15000,    # Microseconds
    "AnalogueGain": 0.8,
})
```

**3. Full path for i2cset**

SSH sessions do not include `/usr/sbin` in PATH by default. All mux switch commands use the full binary path to ensure they work both locally and when called remotely:

```python
MUX_COMMANDS = {
    0: "/usr/sbin/i2cset -y 10 0x24 0x24 0x02",
    1: "/usr/sbin/i2cset -y 10 0x24 0x24 0x12",
    2: "/usr/sbin/i2cset -y 10 0x24 0x24 0x22",
    3: "/usr/sbin/i2cset -y 10 0x24 0x24 0x32",
}
```

---

## Setup & Requirements

### Both Pis

```bash
# Install dependencies
pip3 install picamera2 opencv-python

# Load AK7375 VCM autofocus driver permanently
echo "ak7375" | sudo tee /etc/modules-load.d/ak7375.conf

# /boot/firmware/config.txt settings
camera_auto_detect=0
dtoverlay=imx519
dtparam=i2c_arm_baudrate=25000
```

### Controller Pi — Passwordless SSH to Secondary

```bash
ssh-keygen -t rsa
ssh-copy-id pi@192.168.1.6
```

### Static IP (both Pis — add to /etc/network/interfaces)

```
# Controller Pi:
auto eth0
iface eth0 inet static
    address 192.168.1.5
    netmask 255.255.255.0

# Secondary Pi:
auto eth0
iface eth0 inet static
    address 192.168.1.6
    netmask 255.255.255.0
```

### Deploy capture script to Secondary Pi

```bash
scp img_capture.py pi@192.168.1.6:/home/pi/code/img_capture.py
```

---

## Output

All images saved to `/home/pi/scans/YYYY-MM-DD/` on the Controller Pi.

For a 5-position scan: **40 images total** (8 cameras x 5 positions)

```
/home/pi/scans/2026-04-11/
├── controller_pos00_cam0_2026-04-11-14-30-01.jpg
├── controller_pos00_cam1_2026-04-11-14-30-04.jpg
├── controller_pos00_cam2_2026-04-11-14-30-07.jpg
├── controller_pos00_cam3_2026-04-11-14-30-10.jpg
├── secondary_pos00_cam0_2026-04-11-14-30-15.jpg
├── secondary_pos00_cam1_2026-04-11-14-30-18.jpg
...
```
## Real-Time Terminal Display

During every scan the terminal updates live after each position showing:

- Current position number and total positions remaining
- Images successfully captured on Controller Pi and Secondary Pi
- Transfer status of Secondary Pi images
- Any failed captures with exact camera and position details
- Final summary — total images collected vs expected

This gives full visibility into scan progress across both devices without needing to check either Pi individually.


