import serial
import time
import bitcrane

try:
    serial_port_ctrl = serial.Serial(
        port='/dev/tty.usbmodemb310cc521',  # Update this to your serial port
        baudrate=115200,
        timeout=1
    )
except serial.SerialException as e:
    print(f"Error opening Control serial port: {e}")
    exit(1)

def i2c_send_byte(ser, address, register, data, debug=False):
    id = 0xBC
    packet = bytes([0x09, 0x00, id, 0x00, bitcrane.PAGE_PSU, bitcrane.I2C_COMMAND_WRITE, address, register, data])
    ser.write(packet)
    size = 1
    if debug:
        print("ctrl tx: [%s]" % bitcrane.prettyHex(packet))
    data = ser.read(size+3)
    if data:
        bytes_read = len(data)
        if bytes_read > 0:
            if debug:
                print("ctrl rx: [%s]" % bitcrane.prettyHex(data))
            if data[2] != id:
                print("Error: ID mismatch. Expected %02X, got %02X" % (id, data[2]))
                return None
        else:
            print("No data received")
            return None
    else:
        print("No data received")
        return None

    return data[-size:]

#- read one byte from addr 0x4C: `08 00 01 00 04 30 4C 01`
# For reading 1 byte from I2C address 0x10:

# [08 00 XX 00 04 30 10 01]
# Where XX is whatever command ID you want to use for tracking
def i2c_read_byte(ser, address, debug=False):
    ser.reset_input_buffer()
    size = 1
    id = 0xAB
    packet = bytes([0x08, 0x00, id, 0x00, bitcrane.PAGE_PSU, bitcrane.I2C_COMMAND_READ, address, size])
    ser.write(packet)
    if debug:
        print("ctrl tx: [%s]" % bitcrane.prettyHex(packet))
    data = ser.read(size+3)
    if data:
        bytes_read = len(data)
        if bytes_read > 0:
            if debug:
                print("ctrl rx: [%s]" % bitcrane.prettyHex(data))
            if data[2] != id:
                print("Error: ID mismatch. Expected %02X, got %02X" % (id, data[2]))
                return None
        else:
            print("No data received")
            return None
    else:
        print("No data received")
        return None

    return data[-size:]

def psu_send_bytes(ser, address, register, data_bytes, debug=False):
    """
    Send a list of bytes individually via I2C, checking response for each.
    Returns True if all bytes sent successfully, False otherwise.
    """
    if debug:
        print(f"Sending bytes to PSU address 0x{address:02X}, register 0x{register:02X}: [{' '.join(f'{b:02X}' for b in data_bytes)}]")
    for i, byte in enumerate(data_bytes):
        result = i2c_send_byte(ser, address, register, byte, debug)
        if result is None:
            print(f"Error: Failed to send byte {i} (0x{byte:02X})")
            return False
    return True

def psu_read_bytes(ser, address, num_bytes, debug=False):
    """
    Read a number of bytes individually via I2C, checking response for each.
    Returns list of bytes read, or None if any read fails.
    """
    result = []
    for i in range(num_bytes):
        byte = i2c_read_byte(ser, address, debug)
        if byte is None:
            print(f"Error: Failed to read byte {i}")
            return None
        result.append(byte[0])
    return result

bitcrane.gpio_set(serial_port_ctrl, 0xAB, bitcrane.GPIO_PSU_EN, bitcrane.GPIO_LOW, True)

#send [0x55, 0xAA, 0x04, 0x02, 0x06, 0x00] to address 0x10
psu_send_bytes(serial_port_ctrl, 0x10, 0x11, [0x55, 0xAA, 0x04, 0x02, 0x06, 0x00], True)

#delay 0.1s
time.sleep(0.5)

#read back 8 bytes
data = psu_read_bytes(serial_port_ctrl, 0x10, 8, True)
if data:
    print(f"Read PSU bytes: [{' '.join(f'{b:02X}' for b in data)}]")


