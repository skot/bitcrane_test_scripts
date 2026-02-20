import serial
import time
import sys
import APW_PSU

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
    print(f"Enabling PSU and setting voltage to {voltage}...")
    APW_PSU.PSU_set_enable(serial_port_ctrl, True, debug=False)
    time.sleep(0.5)  # wait for PSU to power up
    
    # it seems like 0x00 disables the watchdog, 0x01 enables it??
    APW_PSU.PSU_config_watchdog(serial_port_ctrl, 0x00, False)
    
    APW_PSU.PSU_set_voltage(serial_port_ctrl, voltage, False)

    time.sleep(0.5)

    # APW_PSU.PSU_get_hw_version(serial_port_ctrl, False)
    # APW_PSU.PSU_get_fw_version(serial_port_ctrl, False)

    #APW_PSU.PSU_set_voltage_raw(serial_port_ctrl, 0xFF, False)

    #APW_PSU.PSU_get_voltage(serial_port_ctrl, False)
    time.sleep(5)

    # this measure_voltage command is really squirrley
    APW_PSU.PSU_measure_voltage(serial_port_ctrl, False)