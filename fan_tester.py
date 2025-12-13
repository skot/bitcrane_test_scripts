import serial
import time
import sys

import bitaxeraw

#take command line argument for fan speed. return help if not provided
if len(sys.argv) != 2:
    print("Usage: python fan_tester.py <fan_speed>")
    print("Fan speed must be between 0 and 100")
    exit(1)

fan_speed = int(sys.argv[1])
if fan_speed < 0 or fan_speed > 100:
    print("Fan speed must be between 0 and 100")
    exit(1)

# Configure the serial ports
try:
    serial_port_ctrl = serial.Serial(
        port='/dev/tty.usbmodemb310cc521',  # Update this to your control serial port. usually it's the first one
        baudrate=115200,
        timeout=5
    )
except serial.SerialException as e:
    print(f"Error opening Control serial port: {e}")
    exit(1)

def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)


#set the fan speed
print("Setting fan speed to %d%%" % fan_speed)
bitaxeraw.fan_set_speed(serial_port_ctrl, 0xAB, fan_speed, debug=True)
time.sleep(1)

#read the fan rpm 3 times, waiting 1 second between reads
for i in range(10):
    rpm = bitaxeraw.get_fan_rpm(serial_port_ctrl, 0xAB, debug=True)
    print("Fan RPM: %d" % rpm)
    time.sleep(1)