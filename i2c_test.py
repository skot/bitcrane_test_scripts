import serial
import TMP75
import time

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
        temperature = TMP75.read_temperature(serial_port_ctrl, 0)
        print("Temp 0: %.2f C" % temperature)
        temperature = TMP75.read_temperature(serial_port_ctrl, 1)
        print("Temp 1: %.2f C" % temperature)
        time.sleep(1)
except KeyboardInterrupt:
    print(" -> Stopping the script.")
finally:
    serial_port_ctrl.close()