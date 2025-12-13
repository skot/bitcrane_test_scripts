import serial
import TMP75
import time

def reset_asic():
    # Construct the command to reset the ASIC
    command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, 0x00, 0x00])
    serial_port_ctrl.write(command)
    time.sleep(0.1)

    command = bytes([0x07, 0x00, 0x00, 0x00, 0x06, 0x00, 0x01])
    serial_port_ctrl.write(command)


def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)



# Configure the serial ports
try:
    serial_port_asic = serial.Serial(
        port='/dev/tty.usbmodemb310cc523',  # Update this to your serial port
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
        print("\nSending reset command to ASIC...")
        reset_asic()
        time.sleep(0.1)
        serial_port_asic.write(bytes([0x55, 0xAA, 0x51, 0x09, 0x00, 0xA4, 0x90, 0x00, 0xFF, 0xFF, 0x1C]))
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
        temperature = TMP75.read_temperature(serial_port_ctrl, 0)
        print("Temp 0: %.2f C" % temperature)
        temperature = TMP75.read_temperature(serial_port_ctrl, 1)
        print("Temp 1: %.2f C" % temperature)
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping the script.")
finally:
    serial_port_ctrl.close()
    serial_port_asic.close()