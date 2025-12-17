import serial
import TMP75
import time
import sys

# Take command line argument for hashboard number
if len(sys.argv) != 2:
    print("Usage: python i2c_test.py <hashboard_num>")
    print("  hashboard_num: Hashboard number to ping")
    exit(1)

try:
    hashboard_num = int(sys.argv[1])
except ValueError:
    print("Error: hashboard_num must be a number")
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

try:
    while True:
        print("\nReading board temps...")
        temperature = TMP75.read_temperature(serial_port_ctrl, 0, hashboard_num, True)
        print("Temp 0: %.2f C" % temperature)
        temperature = TMP75.read_temperature(serial_port_ctrl, 1, hashboard_num, True)
        print("Temp 1: %.2f C" % temperature)
        time.sleep(1)
except KeyboardInterrupt:
    print(" -> Stopping the script.")
finally:
    serial_port_ctrl.close()