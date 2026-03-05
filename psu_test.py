import serial
import time
import sys
import json
import os
import APW_PSU

# Calibration data persisted across runs so the linear fit improves over time.
CAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'psu_cal.json')

def load_cal_points():
    """Load saved (dac_code, voltage) calibration points from disk."""
    if os.path.exists(CAL_FILE):
        try:
            with open(CAL_FILE) as f:
                data = json.load(f)
            points = [tuple(p) for p in data.get('points', [])]
            print(f"Loaded {len(points)} calibration point(s) from {CAL_FILE}")
            return points
        except Exception as e:
            print(f"Warning: could not load {CAL_FILE}: {e}")
    return []

def save_cal_points(points):
    """Persist calibration points to disk."""
    try:
        with open(CAL_FILE, 'w') as f:
            json.dump({'points': [list(p) for p in points]}, f, indent=2)
        print(f"Saved {len(points)} calibration point(s) to {CAL_FILE}")
    except Exception as e:
        print(f"Warning: could not save {CAL_FILE}: {e}")

# Take command line argument for voltage
if len(sys.argv) != 2:
    print("Usage: python psu_test.py <voltage>")
    print("  voltage: Voltage to set (0 to disable PSU)")
    exit(1)

try:
    voltage = float(sys.argv[1])
except ValueError:
    print("Error: voltage must be a number")
    exit(1)

try:
    serial_port_ctrl = serial.Serial(
        port='/dev/tty.usbmodemb310cc521',  # Update this to your serial port
        baudrate=115200,
        timeout=1
    )
except serial.SerialException as e:
    print(f"Error opening Control serial port: {e}")
    exit(1)


if voltage == 0:
    print("Disabling PSU...")
    APW_PSU.PSU_set_enable(serial_port_ctrl, False, debug=False)
else:
    print(f"Enabling PSU and setting voltage to {voltage} V...")
    APW_PSU.PSU_set_enable(serial_port_ctrl, True, debug=False)
    time.sleep(0.5)  # wait for PSU to power up

    # Disable watchdog before doing anything else
    APW_PSU.PSU_config_watchdog(serial_port_ctrl, 0x00, False)

    # -----------------------------------------------------------------------
    # Step 1: Read GET_VOLTAGE *before* any SET_VOLTAGE.
    # The PIC loads its factory calibration code from program flash into
    # register 0x1e0 at boot. GET_VOLTAGE (0x03) returns that register
    # directly, so the FIRST read after a TRUE HARDWARE POWER CYCLE gives
    # the per-unit factory DAC code.
    #
    # NOTE: the PSU holds its last setpoint across enable/disable cycles --
    # only a full hardware power-cycle reloads the flash cal code. So this
    # read is informational; DAC_REF_DEFAULT is used for the initial set.
    # -----------------------------------------------------------------------
    print("\n--- Reading current DAC setpoint (pre-set, informational) ---")
    boot_data = APW_PSU.PSU_get_voltage(serial_port_ctrl,
                                         APW_PSU.DAC_REF_DEFAULT,
                                         APW_PSU.DAC_OFFSET_DEFAULT, debug=False)

    # Load persisted calibration points and fit
    cal_points = load_cal_points()
    if len(cal_points) >= 2:
        print("\n--- Fitting calibration from saved points ---")
        cal = APW_PSU.PSU_fit_calibration(cal_points)
        dac_ref    = cal['dac_ref']
        dac_offset = cal['dac_offset']
        print(f"  Using fitted: dac_ref={dac_ref:.4f} V, dac_offset={dac_offset:.6f} V/count")
    else:
        dac_ref    = APW_PSU.DAC_REF_DEFAULT
        dac_offset = APW_PSU.DAC_OFFSET_DEFAULT
        print(f"  Not enough cal points yet, using defaults: dac_ref={dac_ref:.4f} V, dac_offset={dac_offset:.6f} V/count")

    if boot_data is not None and len(boot_data) >= 5:
        boot_code = boot_data[4]
        boot_v = dac_ref + dac_offset * boot_code
        print(f"  Current DAC code : 0x{boot_code:02X}  ({boot_code} decimal)")
        print(f"  Corresponds to   : {boot_v:.4f} V  (at dac_ref={dac_ref:.4f} V)")
        print(f"  (After a full hardware power-cycle this shows the factory flash cal code.)")
    else:
        print(f"  GET_VOLTAGE failed -- using dac_ref = {dac_ref:.4f} V")

    # -----------------------------------------------------------------------
    # Step 2: Set the requested voltage with the fitted/default cal params
    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    print(f"\n--- Setting voltage to {voltage} V ---")
    APW_PSU.PSU_set_voltage(serial_port_ctrl, voltage, dac_ref, dac_offset, debug=False)
    time.sleep(0.5)

    # Read back the setpoint to confirm
    print("\n--- Setpoint readback ---")
    APW_PSU.PSU_get_voltage(serial_port_ctrl, dac_ref, dac_offset, debug=False)

    # -----------------------------------------------------------------------
    # Step 3: ADC measurement
    # -----------------------------------------------------------------------
    print("\n--- ADC measurement (let output settle ~3 s) ---")
    time.sleep(3)
    APW_PSU.PSU_measure_voltage(serial_port_ctrl, False)

    # -----------------------------------------------------------------------
    # Step 4: Prompt for multimeter reading and fine-calibrate dac_ref
    # -----------------------------------------------------------------------
    print(f"\n--- Multimeter calibration ---")
    print(f"Please measure the PSU output voltage with your multimeter.")
    try:
        raw = input("Enter measured voltage (V), or press Enter to skip: ").strip()
        if raw:
            meas_v = float(raw)
            new_pt = APW_PSU.PSU_calibrate_voltage(serial_port_ctrl, meas_v,
                                                    dac_ref, dac_offset, debug=False)
            if new_pt is not None:
                # Add point (avoid duplicates at the same DAC code — keep newest)
                code = new_pt[0]
                cal_points = [p for p in cal_points if p[0] != code]
                cal_points.append(new_pt)
                save_cal_points(cal_points)

                if len(cal_points) >= 2:
                    print("\n--- Updated multi-point fit ---")
                    new_cal = APW_PSU.PSU_fit_calibration(cal_points)
                    print(f"\n  >> To hardcode: DAC_REF_DEFAULT={new_cal['dac_ref']:.4f}, "
                          f"DAC_OFFSET_DEFAULT={new_cal['dac_offset']:.6f}")
                else:
                    print(f"  1 point saved. Run at a different voltage to build a multi-point fit.")
        else:
            print("  Skipped.")
    except (ValueError, EOFError) as e:
        print(f"  Calibration skipped: {e}")