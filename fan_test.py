import serial
import time
import sys

import bitcrane

# Take command line arguments for FAN1 and FAN2 speeds
if len(sys.argv) != 3:
    print("Usage: python fan_tester.py <fan1_speed> <fan2_speed>")
    print("  fan1_speed: 0-100")
    print("  fan2_speed: 0-100")
    exit(1)

try:
    fan1_speed = int(sys.argv[1])
    fan2_speed = int(sys.argv[2])
    
    if fan1_speed < 0 or fan1_speed > 100:
        print("Error: FAN1 speed must be between 0 and 100")
        exit(1)
    if fan2_speed < 0 or fan2_speed > 100:
        print("Error: FAN2 speed must be between 0 and 100")
        exit(1)
except ValueError:
    print("Error: Both fan speeds must be numbers between 0 and 100")
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


# Set fan speeds
print(f"Setting FAN1 speed to {fan1_speed}%")
bitcrane.fan_set_speed(serial_port_ctrl, 0xAB, 1, fan1_speed, debug=True)
time.sleep(0.5)

print(f"Setting FAN2 speed to {fan2_speed}%")
bitcrane.fan_set_speed(serial_port_ctrl, 0xAB, 2, fan2_speed, debug=True)
time.sleep(0.5)

# Read fan RPM 10 times, waiting 1 second between reads
print("\nReading fan RPM:")
for i in range(10):
    print(f"\n--- Read {i+1} ---")
    rpm1 = bitcrane.get_fan_rpm(serial_port_ctrl, 0xAB, 1, debug=True)
    print(f"FAN1 RPM: {rpm1}")
    rpm2 = bitcrane.get_fan_rpm(serial_port_ctrl, 0xAB, 2, debug=True)
    print(f"FAN2 RPM: {rpm2}")
    time.sleep(1)