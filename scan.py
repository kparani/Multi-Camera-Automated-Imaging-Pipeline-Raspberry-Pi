"""
scan.py - Main controller script
Run on Controller Pi (192.168.1.5) ONLY

Usage:
    python3 scan.py -n 5              # 5 stops, 72 degrees each
    python3 scan.py -n 5 -sf 0.0001  # with custom stepper speed

What it does per position:
    1. Capture 4 images on Controller Pi
    2. Capture 4 images on Secondary Pi (via SSH)
    3. Move stepper motor to next position
After all positions:
    4. Transfer all images from Secondary Pi to Controller Pi
    5. Everything saved in /home/pi/scans/YYYY-MM-DD/
"""

import subprocess
import os
import argparse
import time
from datetime import date
import RPi.GPIO as GPIO

# ─────────────────────────────────────────────────────────
# CONFIG - edit these if anything changes
# ─────────────────────────────────────────────────────────
SECONDARY_USER    = "pi"
SECONDARY_IP      = "192.168.1.6"
SECONDARY_SAVE    = "/home/pi/scan_images"   # image folder on secondary Pi
CONTROLLER_SAVE   = "/home/pi/scans"         # base folder on controller Pi

CAPTURE_SCRIPT    = "/home/pi/code/img_capture.py"

# GPIO pins for stepper motor
DIR_PIN           = 27
STEP_PIN          = 17
CW                = 0    # clockwise

# Stepper: 25 microsteps x 9600 steps per revolution
STEPS_PER_REV     = 25 * 9600

# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────
def run_cmd(cmd, timeout=120):
    """Run a shell command. Returns True on success, False on failure."""
    print(f"\n>> {cmd}")
    try:
        subprocess.run(cmd, shell=True, timeout=timeout, check=True)
        return True
    except subprocess.TimeoutExpired:
        print("ERROR: Command timed out.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Command failed with exit code {e.returncode}")
        return False


def degree_to_steps(degrees):
    return round(degrees * STEPS_PER_REV / 360)


def move_motor(steps, speed_sec):
    """Move stepper motor the given number of steps."""
    print(f"\nMoving motor {steps} steps...")
    start = time.time()
    for _ in range(steps):
        GPIO.output(STEP_PIN, GPIO.HIGH)
        time.sleep(speed_sec)
        GPIO.output(STEP_PIN, GPIO.LOW)
        time.sleep(speed_sec)
    print(f"Motor move complete in {time.time() - start:.2f}s")

# ─────────────────────────────────────────────────────────
# CAPTURE
# ─────────────────────────────────────────────────────────
def capture_controller(save_path, position):
    """Capture 4 images on the controller Pi."""
    print(f"\n[Controller Pi] Capturing position {position + 1}...")
    cmd = (
        f"python3 {CAPTURE_SCRIPT} "
        f"--save_path {save_path} "
        f"--pi_id controller "
        f"--position {position}"
    )
    return run_cmd(cmd, timeout=120)


def capture_secondary(position):
    """Capture 4 images on the secondary Pi via SSH."""
    print(f"\n[Secondary Pi] Capturing position {position + 1}...")
    remote_cmd = (
        f"python3 {CAPTURE_SCRIPT} "
        f"--save_path {SECONDARY_SAVE} "
        f"--pi_id secondary "
        f"--position {position}"
    )
    cmd = f"ssh {SECONDARY_USER}@{SECONDARY_IP} '{remote_cmd}'"
    return run_cmd(cmd, timeout=120)

# ─────────────────────────────────────────────────────────
# TRANSFER
# ─────────────────────────────────────────────────────────
def transfer_images(local_save):
    """SCP all images from secondary Pi to controller Pi, then clean up."""
    print(f"\nTransferring images from Secondary Pi to Controller Pi...")
    cmd = (
        f"scp {SECONDARY_USER}@{SECONDARY_IP}:"
        f"{SECONDARY_SAVE}/*.jpg {local_save}/"
    )
    success = run_cmd(cmd, timeout=300)
    if success:
        print("Transfer successful. Cleaning up Secondary Pi...")
        run_cmd(
            f"ssh {SECONDARY_USER}@{SECONDARY_IP} "
            f"'rm -f {SECONDARY_SAVE}/*.jpg'"
        )
    else:
        print("ERROR: Transfer failed!")
        print(f"  Manual recovery command:")
        print(f"  scp {SECONDARY_USER}@{SECONDARY_IP}:{SECONDARY_SAVE}/*.jpg {local_save}/")
    return success

# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="360 root scanner controller")
    parser.add_argument(
        "-n", "--num_positions",
        type=int, default=5,
        help="Number of scan stops (e.g. 5 = every 72 degrees)"
    )
    parser.add_argument(
        "-sf", "--speed_forward",
        type=float, default=0.0001,
        help="Stepper motor speed in seconds per half-step"
    )
    args = parser.parse_args()

    n_positions  = args.num_positions
    speed_sec    = args.speed_forward
    degrees_each = 360.0 / n_positions
    steps_each   = degree_to_steps(degrees_each)

    print("=" * 55)
    print("  ROOT SCANNER - START")
    print("=" * 55)
    print(f"  Scan positions : {n_positions}")
    print(f"  Degrees/stop   : {degrees_each:.2f}")
    print(f"  Steps/stop     : {steps_each}")
    print(f"  Motor speed    : {speed_sec}s per half-step")
    print("=" * 55)

    # ── Create save folders ──────────────────────────────
    today      = str(date.today())
    local_save = os.path.join(CONTROLLER_SAVE, today)
    os.makedirs(local_save, exist_ok=True)
    print(f"\nImages will be saved to: {local_save}")

    # Create image folder on secondary Pi
    run_cmd(
        f"ssh {SECONDARY_USER}@{SECONDARY_IP} "
        f"'mkdir -p {SECONDARY_SAVE}'"
    )

    # ── GPIO Setup ───────────────────────────────────────
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(DIR_PIN,  GPIO.OUT)
    GPIO.setup(STEP_PIN, GPIO.OUT)
    GPIO.output(DIR_PIN, CW)

    # ── Main scan loop ───────────────────────────────────
    failed = []

    for i in range(n_positions):
        print(f"\n{'='*55}")
        print(f"  POSITION {i+1} of {n_positions}")
        print(f"{'='*55}")

        # Step 1: Controller Pi captures
        if not capture_controller(local_save, i):
            print(f"WARNING: Controller capture failed at position {i+1}")
            failed.append(f"Position {i+1} - Controller Pi")

        time.sleep(2)

        # Step 2: Secondary Pi captures
        if not capture_secondary(i):
            print(f"WARNING: Secondary capture failed at position {i+1}")
            failed.append(f"Position {i+1} - Secondary Pi")

        time.sleep(2)

        # Step 3: Move motor (skip after last position)
        if i < n_positions - 1:
            move_motor(steps_each, speed_sec)
        else:
            print("\nLast position — no motor movement needed.")

    # ── Transfer images from secondary Pi ────────────────
    print(f"\n{'='*55}")
    print("  TRANSFERRING IMAGES FROM SECONDARY PI")
    print(f"{'='*55}")
    transfer_images(local_save)

    # ── GPIO Cleanup ─────────────────────────────────────
    GPIO.cleanup()

    # ── Final summary ────────────────────────────────────
    print(f"\n{'='*55}")
    print("  SCAN COMPLETE - SUMMARY")
    print(f"{'='*55}")
    print(f"  Folder : {local_save}")

    jpg_count = len([f for f in os.listdir(local_save) if f.endswith('.jpg')])
    expected  = n_positions * 8
    print(f"  Images found    : {jpg_count}")
    print(f"  Images expected : {expected}  ({n_positions} positions x 8 cameras)")

    if failed:
        print(f"\n  Failed captures:")
        for f in failed:
            print(f"    - {f}")
    else:
        print("\n  All captures successful!")
