import serial
import time

PAGE_I2C = 0x05
I2C_COMMAND_WRITE = 0x20
I2C_COMMAND_READ = 0x30
I2C_COMMAND_READWRITE = 0x40

PAGE_GPIO = 0x06
GPIO_HIGH = 0x01
GPIO_LOW = 0x00
GPIO_HB0_RST = 0x00
GPIO_HB0_PLUG = 0x01
GPIO_HB1_RST = 0x10
GPIO_HB1_PLUG = 0x11
GPIO_HB2_RST = 0x20
GPIO_HB2_PLUG = 0x21

PAGE_FAN = 0x09
FAN1_SPEED_CMD = 0x11
FAN1_TACH_CMD = 0x21
FAN2_SPEED_CMD = 0x12
FAN2_TACH_CMD = 0x22
FAN3_SPEED_CMD = 0x13
FAN3_TACH_CMD = 0x23
FAN4_SPEED_CMD = 0x14
FAN4_TACH_CMD = 0x24


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

def fan_set_speed(ser, id, fan_num, speed_percent, debug=False):
    packet_len = 7
    if fan_num == 1:
        fan_speed_command = FAN1_SPEED_CMD
    elif fan_num == 2:
        fan_speed_command = FAN2_SPEED_CMD
    elif fan_num == 3:
        fan_speed_command = FAN3_SPEED_CMD
    elif fan_num == 4:
        fan_speed_command = FAN4_SPEED_CMD
    else:
        raise ValueError("Invalid fan number. Must be 1-4.")
    packet = bytes([packet_len, 0x00, id, 0x00, PAGE_FAN, fan_speed_command, speed_percent])

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

def get_fan_rpm(ser, id, fan_num, debug=False):
    packet_len = 6
    if fan_num == 1:
        fan_tach_command = FAN1_TACH_CMD
    elif fan_num == 2:
        fan_tach_command = FAN2_TACH_CMD
    elif fan_num == 3:
        fan_tach_command = FAN3_TACH_CMD
    elif fan_num == 4:
        fan_tach_command = FAN4_TACH_CMD
    else:
        raise ValueError("Invalid fan number. Must be 1-4.")
    packet = bytes([packet_len, 0x00, id, 0x00, PAGE_FAN, fan_tach_command])

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

def i2c_send_bytes(ser, address, register, data, debug=False):
     packet = bytes([0x09, 0x00, 0x01, 0x00, PAGE_I2C, I2C_COMMAND_WRITE, address, register, data])
     ser.write(packet)
     if debug:
        print("ctrl tx: [%s]" % prettyHex(packet))

def i2c_read_bytes(ser, id, address, register, size, debug=False):
    ser.reset_input_buffer()
    packet = bytes([0x09, 0x00, id, 0x00, PAGE_I2C, I2C_COMMAND_READWRITE, address, register, size])
    ser.write(packet)
    if debug:
        print("ctrl tx: [%s]" % prettyHex(packet))
    data = ser.read(size+3)
    if data:
        bytes_read = len(data)
        if bytes_read > 0:
            if debug:
                print("ctrl rx: [%s]" % prettyHex(data))
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
    

def reset_asic(ser, hashboard_num, debug=False):
    if hashboard_num == 0:
        rst_pin = GPIO_HB0_RST
    elif hashboard_num == 1:
        rst_pin = GPIO_HB1_RST
    elif hashboard_num == 2:
        rst_pin = GPIO_HB2_RST
    else:
        raise ValueError("Invalid hashboard number. Must be 0-2.")
    
    # Construct the command to reset the ASIC
    command = bytes([0x07, 0x00, 0x00, 0x00, PAGE_GPIO, rst_pin, GPIO_LOW])
    if debug:
        print("reset_asic tx: [%s]" % prettyHex(command))
    ser.write(command)
    time.sleep(0.1)

    command = bytes([0x07, 0x00, 0x00, 0x00, PAGE_GPIO, rst_pin, GPIO_HIGH])
    if debug:
        print("reset_asic tx: [%s]" % prettyHex(command))
    ser.write(command)
