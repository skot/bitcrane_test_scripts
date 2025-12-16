import serial
import TMP75
import time
import sys
import bitcrane

#takes a S19j Pro hashboard number as an argument and pings all the ASICs and reads the PCB temperatures

def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

# Take command line argument for hashboard number
if len(sys.argv) != 2:
    print("Usage: python ping_looper.py <hashboard_num>")
    print("  hashboard_num: Hashboard number to ping")
    exit(1)

try:
    hashboard_num = int(sys.argv[1])
except ValueError:
    print("Error: hashboard_num must be a number")
    exit(1)

# Configure the serial ports
try:
    serial_port_asic = serial.Serial(
        port='/dev/tty.usbmodemb310cc527',  # Update this to your serial port
        baudrate=115200,
        timeout=2
    )
except serial.SerialException as e:
    print(f"Error opening ASIC serial port: {e}")
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
    

led_color = 0
try:
    while True:
        print(f"\n{'='*50}")
        print(f"Hashboard {hashboard_num}")
        print(f"{'='*50}")
        print("Sending reset command to ASIC...")
        bitcrane.reset_asic(serial_port_ctrl, hashboard_num, True)
        time.sleep(0.1)
        serial_port_asic.write(bytes([0x55, 0xAA, 0x51, 0x09, 0x00, 0xA4, 0x90, 0x00, 0xFF, 0xFF, 0x1C])) #55 AA 51 09 00 A4 90 00 FF FF 1C
        time.sleep(0.1)

        #clear the rx buffer
        serial_port_asic.reset_input_buffer()

        serial_port_asic.write(bytes([0x55, 0xAA, 0x52, 0x05, 0x00, 0x00, 0x0A]))
        print("Sent ping..")
        # wait for the response for 2 seconds
        rx_count = 0
        while True:
            response = serial_port_asic.read(11)
            if response:
                rx_count += 1
                print("response %02d: %s" % (rx_count, prettyHex(response)))
            else:
                print()
                break

        time.sleep(0.1)
        print("\nReading board temps...")
        temperature = TMP75.read_temperature(serial_port_ctrl, 0, hashboard_num)
        print("Temp 0: %.2f C" % temperature)
        temperature = TMP75.read_temperature(serial_port_ctrl, 1, hashboard_num)
        print("Temp 1: %.2f C" % temperature)
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping the script.")
finally:
    serial_port_ctrl.close()
    serial_port_asic.close()