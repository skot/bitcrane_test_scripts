import bitcrane
import time

#send a single byte to a register over I2C
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

#read a single byte over I2C
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
        print(f"Sending bytes to PSU: [{' '.join(f'{b:02X}' for b in data_bytes)}]")
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

#-----
def make_packet(bytes_list):
    #make the checksum by summing all the bytes and storing as 16-bit little-endian value
    checksum = sum(bytes_list) & 0xFFFF
    bytes_list.append(checksum & 0xFF)        #low byte
    bytes_list.append((checksum >> 8) & 0xFF) #high byte
    return [0x55, 0xAA] + bytes_list

def PSU_set_enable(ser, enable=True, debug=False):
    if enable:
        bitcrane.gpio_set(ser, 0xAB, bitcrane.GPIO_PSU_EN, bitcrane.GPIO_LOW, debug)
    else:
        bitcrane.gpio_set(ser, 0xAB, bitcrane.GPIO_PSU_EN, bitcrane.GPIO_HIGH, debug)

def PSU_get_hw_version(ser, debug=False):
    version_command = [0x04, 0x02]
    version_command = make_packet(version_command)
    print(f"Sending PSU HW version: [{' '.join(f'{b:02X}' for b in version_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, version_command, debug)

    time.sleep(0.5)

    #read back 8 bytes
    data = psu_read_bytes(ser, 0x10, 8, debug)
    if data:
        print(f"Read PSU HW Version response: [{' '.join(f'{b:02X}' for b in data)}]")
        return data
    else:
        return None
    
    
def PSU_disable_watchdog(ser, debug=False):
    num_read_bytes = 8
    watchdog_command = [0x06, 0x81, 0x01, 0x00]
    watchdog_command = make_packet(watchdog_command)
    print(f"Sending PSU disable watchdog: [{' '.join(f'{b:02X}' for b in watchdog_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, watchdog_command, debug)

    time.sleep(0.5)

    #read back 8 bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU watchdog disable response: [{' '.join(f'{b:02X}' for b in data)}]")
        return data
    else:
        return None
    
def PSU_set_voltage(ser, voltage, debug=False):
    num_read_bytes = 8
    hex_voltage = int((voltage - 15.092)/-0.013)
    print("voltage: %.2f V -> hex: 0x%02X" % (voltage, hex_voltage))
    set_voltage_command = [0x06, 0x83, hex_voltage, 0x00]
    set_voltage_command = make_packet(set_voltage_command)
    print(f"Sending PSU set voltage: [{' '.join(f'{b:02X}' for b in set_voltage_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, set_voltage_command, debug)

    time.sleep(0.5)

    #read back 8 bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU set voltage response: [{' '.join(f'{b:02X}' for b in data)}]")
        return data
    else:
        return None
    
def PSU_get_voltage(ser, debug=False):
    num_read_bytes = 8
    voltage_command = [0x04, 0x03]
    voltage_command = make_packet(voltage_command)
    print(f"Sending PSU read voltage: [{' '.join(f'{b:02X}' for b in voltage_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, voltage_command, debug)

    time.sleep(0.5)

    #read back 8 bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU voltage response: [{' '.join(f'{b:02X}' for b in data)}]")
        print("Voltage = %.2f V" % (15.092 - (data[4] * 0.013)))
        return data
    else:
        return None