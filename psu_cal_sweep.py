#!/usr/bin/env python3
"""
PSU calibration sweep: steps through a range of voltages, prompts for
multimeter readings at each step, and fits a linear calibration curve.
Saves all points to psu_cal.json so psu_test.py picks them up automatically.

Usage:
    python psu_cal_sweep.py [start] [stop] [step]
    python psu_cal_sweep.py              # defaults: 12.0 to 15.0, 0.5 V steps
    python psu_cal_sweep.py 12.0 15.0 0.5
"""
import serial
import time
import sys
import json
import os

import APW_PSU

CAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'psu_cal.json')

# ---- helpers ----------------------------------------------------------------

def load_cal_points():
    if os.path.exists(CAL_FILE):
        try:
            with open(CAL_FILE) as f:
                data = json.load(f)
            return [tuple(p) for p in data.get('points', [])]
        except Exception as e:
            print(f"Warning: could not load {CAL_FILE}: {e}")
    return []

def save_cal_points(points):
    try:
        with open(CAL_FILE, 'w') as f:
            json.dump({'points': [list(p) for p in points]}, f, indent=2)
    except Exception as e:
        print(f"Warning: could not save {CAL_FILE}: {e}")

def frange(start, stop, step):
    """Inclusive float range."""
    vals = []
    v = start
    while v <= stop + step * 0.01:
        vals.append(round(v, 4))
        v += step
    return vals

# ---- args -------------------------------------------------------------------

args = sys.argv[1:]
try:
    v_start = float(args[0]) if len(args) > 0 else 12.0
    v_stop  = float(args[1]) if len(args) > 1 else 15.0
    v_step  = float(args[2]) if len(args) > 2 else 0.5
except ValueError:
    print("Usage: python psu_cal_sweep.py [start] [stop] [step]")
    sys.exit(1)

voltages = frange(v_start, v_stop, v_step)
print(f"Sweep: {voltages}")

# ---- serial -----------------------------------------------------------------

try:
    ser = serial.Serial(
        port='/dev/tty.usbmodemb310cc521',
        baudrate=115200,
        timeout=1
    )
except serial.SerialException as e:
    print(f"Error opening serial port: {e}")
    sys.exit(1)

# ---- enable PSU, disable watchdog ------------------------------------------

print("\nEnabling PSU...")
APW_PSU.PSU_set_enable(ser, True, debug=False)
time.sleep(0.5)
APW_PSU.PSU_config_watchdog(ser, 0x00, False)

# ---- load existing cal points and do initial fit ---------------------------

cal_points = load_cal_points()
print(f"\nLoaded {len(cal_points)} existing calibration point(s).")

if len(cal_points) >= 2:
    cal = APW_PSU.PSU_fit_calibration(cal_points)
    dac_ref    = cal['dac_ref']
    dac_offset = cal['dac_offset']
else:
    dac_ref    = APW_PSU.DAC_REF_DEFAULT
    dac_offset = APW_PSU.DAC_OFFSET_DEFAULT

print(f"Starting with: dac_ref={dac_ref:.4f} V, dac_offset={dac_offset:.6f} V/count\n")

# ---- sweep ------------------------------------------------------------------

print("=" * 60)
print(f"Starting sweep: {v_start} V to {v_stop} V in {v_step} V steps")
print("Measure the output with your multimeter at each step.")
print("Press Enter to skip a point (keeps existing data if any).")
print("Type 'q' at any prompt to stop the sweep early.")
print("=" * 60)

for v_target in voltages:
    print(f"\n{'─'*50}")
    print(f"  Target: {v_target:.1f} V")

    # Set voltage
    APW_PSU.PSU_set_voltage(ser, v_target, dac_ref, dac_offset, debug=False)
    time.sleep(1.5)  # let output settle

    # ADC readback (informational)
    data_adc = None
    adc_raw = APW_PSU.PSU_measure_voltage(ser, debug=False)

    # Read back DAC code
    getv_data = APW_PSU.PSU_get_voltage(ser, dac_ref, dac_offset, debug=False)
    if getv_data is None or len(getv_data) < 5:
        print("  WARNING: could not read DAC code -- skipping this point")
        continue
    dac_code = getv_data[4]
    predicted_v = dac_ref + dac_offset * dac_code
    print(f"  DAC code : 0x{dac_code:02X} ({dac_code})  predicted = {predicted_v:.4f} V")

    # Prompt for multimeter reading
    try:
        raw = input(f"  Multimeter reading (V) [Enter=skip, q=quit]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nInterrupted.")
        break

    if raw.lower() == 'q':
        print("Stopping sweep.")
        break

    if not raw:
        print("  Skipped.")
        continue

    try:
        meas_v = float(raw)
    except ValueError:
        print(f"  Invalid input '{raw}' -- skipping.")
        continue

    # Add/replace point for this DAC code
    cal_points = [p for p in cal_points if p[0] != dac_code]
    cal_points.append((dac_code, meas_v))
    save_cal_points(cal_points)

    err = meas_v - predicted_v
    print(f"  Saved:  DAC 0x{dac_code:02X} -> {meas_v:.4f} V  (prediction error: {err:+.4f} V)")

    # Refit with all points so far to improve accuracy for remaining steps
    if len(cal_points) >= 2:
        cal = APW_PSU.PSU_fit_calibration(cal_points)
        dac_ref    = cal['dac_ref']
        dac_offset = cal['dac_offset']

# ---- final fit & summary ----------------------------------------------------

print(f"\n{'='*60}")
print("SWEEP COMPLETE")
print(f"{'='*60}")
print(f"\nAll calibration points ({len(cal_points)} total):")

if len(cal_points) >= 2:
    cal = APW_PSU.PSU_fit_calibration(cal_points)
    print(f"\nFinal calibration:")
    print(f"  DAC_REF_DEFAULT    = {cal['dac_ref']:.4f}")
    print(f"  DAC_OFFSET_DEFAULT = {cal['dac_offset']:.6f}")
    print(f"  R²                 = {cal.get('r_squared', 'N/A')}")
    print(f"\nTo hardcode these in APW_PSU.py update lines:")
    print(f"  DAC_REF_DEFAULT    = {cal['dac_ref']:.4f}")
    print(f"  DAC_OFFSET_DEFAULT = {cal['dac_offset']:.6f}")
else:
    print("  Not enough points for a fit (need at least 2).")

# Leave PSU at v_start (12 V) when done
print(f"\nReturning PSU to {v_start:.1f} V...")
APW_PSU.PSU_set_voltage(ser, v_start, dac_ref, dac_offset, debug=False)
