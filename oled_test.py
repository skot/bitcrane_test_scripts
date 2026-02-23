import serial
import time
import sys

import bitcrane

# Take command line argument for display string
if len(sys.argv) != 2:
    print("Usage: python oled_test.py <string>")
    print("  string: Text to display (max 32 chars)")
    print("  Note: If string contains a space, it will be split - value before last space")
    print("        appears in large font on top, text after appears in small font on bottom")
    exit(1)

display_string = sys.argv[1]

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


# Display the string on the OLED
bitcrane.display(serial_port_ctrl, display_string, debug=True)

# Close the serial port
serial_port_ctrl.close()