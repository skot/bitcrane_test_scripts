import serial
import time

PAGE_I2C = 0x05
PAGE_GPIO = 0x06
PAGE_ADC = 0x07
PAGE_FAN = 0x09

GPIO_HIGH = 0x01
GPIO_LOW = 0x00

GPIO_PWR_EN = 0x00
GPIO_5V_EN = 0x01
GPIO_ASIC_RST = 0x02
GPIO_ASIC_TRIP = 0x03

ADC_DOMAIN1 = 0x50
ADC_DOMAIN2 = 0x51
ADC_DOMAIN3 = 0x52

FAN_SPEED_CMD = 0x10
FAN_TACH_CMD = 0x20

def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def prettyHex9(data):
    """
    Convert a list of 8-bit bytes to 9-bit values and format as hex strings.
    Every two bytes are combined into one 9-bit value:
    - First byte: Lower 8 bits (bits 0-7)
    - Second byte: Bit 8 (only LSB is used, 0 or 1)
    
    Args:
        data: List of u8 bytes (pairs represent 9-bit values)
    
    Returns:
        String with formatted 9-bit hex values like "1FA 0F0 042"
    """
    result = []
    for i in range(0, len(data), 2):
        if i + 1 < len(data):
            lower_byte = data[i]
            upper_byte = data[i + 1] & 0x01  # Only bit 8 is used
            value = (upper_byte << 8) | lower_byte
            result.append(f'{value:03X}')
    return ' '.join(result)

def fan_set_speed(ser, id, speed_percent, debug=False):
    packet_len = 7
    packet = bytes([packet_len, 0x00, id, 0x00, PAGE_FAN, FAN_SPEED_CMD, speed_percent])

    if debug:
        print("ctrl fan tx: [%s]" % prettyHex(packet))

    ser.write(packet)

    # wait for the response
    rxdata = ser.read(4)
    if rxdata:
        bytes_read = len(rxdata)
        if bytes_read > 0:
            if debug:
                print("ctrl fan rx: [%s]" % prettyHex(rxdata))
            if rxdata[2] != id:
                print("Error: ID mismatch. Expected %02X, got %02X" % (id, rxdata[2]))
                return
        else:
            print("No data received")
            return
    else:
        print("No data received")
    return

def get_fan_rpm(ser, id, debug=False):
    packet_len = 6
    packet = bytes([packet_len, 0x00, id, 0x00, PAGE_FAN, FAN_TACH_CMD])

    if debug:
        print("ctrl fan rpm tx: [%s]" % prettyHex(packet))

    ser.write(packet)

    # wait for the response
    rxdata = ser.read(5)
    if rxdata:
        bytes_read = len(rxdata)
        if bytes_read > 0:
            if debug:
                print("ctrl fan rpm rx: [%s]" % prettyHex(rxdata))
            if rxdata[2] != id:
                print("Error: ID mismatch. Expected %02X, got %02X" % (id, rxdata[2]))
                return
            rpm = (rxdata[4] << 8) | rxdata[3]
            return rpm
        else:
            print("No data received")
            return
    else:
        print("No data received")
    return

def gpio_set(ser, id, gpio, value, debug=False):
    packet_len = 7
    packet = bytes([packet_len, 0x00, id, 0x00, PAGE_GPIO, gpio, value])

    if debug:
        print("ctrl gpio tx: [%s]" % prettyHex(packet))

    ser.write(packet)

    # wait for the response
    rxdata = ser.read(4)
    if rxdata:
        bytes_read = len(rxdata)
        if bytes_read > 0:
            if debug:
                print("ctrl gpio rx: [%s]" % prettyHex(rxdata))
            if rxdata[2] != id:
                print("Error: ID mismatch. Expected %02X, got %02X" % (id, rxdata[2]))
                return
        else:
            print("No data received")
            return
    else:
        print("No data received")
    return

#asic_write takes an list of u16 values and writes them as u8 bytes to the serial port
# Data is sent/received as pairs of bytes:
# - **First byte**: Lower 8 bits of the 9-bit word (bits 0-7)
# - **Second byte**: Bit 8 (only LSB is used, can be 0 or 1)
def asic_write(ser, data, debug=False):
    ser.reset_input_buffer()
    packet = []
    for value in data:
        lower_byte = value & 0xFF
        upper_byte = (value >> 8) & 0x01  # Only bit 8 is used
        packet.append(lower_byte)
        packet.append(upper_byte)

    if debug:
        print("asic tx: [%s]" % prettyHex(packet))
        print("asic tx9: [%s]" % prettyHex9(packet))

    ser.write(packet)
    return

def asic_read(ser, length, debug=False):
    expected_bytes = length * 2  # Each u16 is sent as 2 bytes
    rxdata = ser.read(expected_bytes)

    if len(rxdata) != expected_bytes:
        print(f"Error: Expected {expected_bytes} bytes, got {len(rxdata)} bytes")
        if debug:
            print("      asic rx: [%s]" % prettyHex9(rxdata))
        return []
    
    if debug:
        print("asic rx: [%s]" % prettyHex9(rxdata))

    data = []
    for i in range(0, len(rxdata), 2):
        lower_byte = rxdata[i]
        upper_byte = rxdata[i + 1] & 0x01  # Only bit 8 is used
        value = (upper_byte << 8) | lower_byte
        data.append(value)

    return data