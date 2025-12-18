import bitcrane
import time

PSU_CMD_GET_HW_VERSION = 0x02
PSU_CMD_GET_FW_VERSION = 0x01
PSU_CMD_SET_VOLTAGE = 0x83
PSU_CMD_GET_VOLTAGE = 0x03
PSU_CMD_MEASURE_VOLTAGE = 0x04
PSU_CMD_DISABLE_WDT = 0x81
PSU_CMD_FEED_WDT = 0x0A
PSU_CMD_READ_CAL = 0x06


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

## add 0x55, 0xAA header and 16-bit checksum to a command packet
def make_packet(bytes_list):
    bytes_list = [len(bytes_list) + 3] + bytes_list # add the length (everything but the 55 AA header)
    #make the checksum by summing all the bytes and storing as 16-bit little-endian value
    checksum = sum(bytes_list) & 0xFFFF
    bytes_list.append(checksum & 0xFF)        #low byte
    bytes_list.append((checksum >> 8) & 0xFF) #high byte
    return [0x55, 0xAA] + bytes_list

def PSU_set_enable(ser, enable=True, debug=False):
    if enable:
        print("Enabling PSU...")
        bitcrane.gpio_set(ser, 0xAB, bitcrane.GPIO_PSU_EN, bitcrane.GPIO_LOW, debug)
    else:
        print("Disabling PSU...")
        bitcrane.gpio_set(ser, 0xAB, bitcrane.GPIO_PSU_EN, bitcrane.GPIO_HIGH, debug)

def PSU_get_hw_version(ser, debug=False):
    num_read_bytes = 8
    version_command = [PSU_CMD_GET_HW_VERSION]
    version_command = make_packet(version_command)
    print(f"Sending PSU HW version: [{' '.join(f'{b:02X}' for b in version_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, version_command, debug)

    time.sleep(0.5)

    #read back num_read_bytes bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU HW Version response: [{' '.join(f'{b:02X}' for b in data)}]")
        return data
    else:
        return None
    
    
def PSU_config_watchdog(ser, value, debug=False):
    num_read_bytes = 8
    watchdog_command = [PSU_CMD_DISABLE_WDT, value, 0x00]
    watchdog_command = make_packet(watchdog_command)
    print(f"Sending PSU config watchdog: [{' '.join(f'{b:02X}' for b in watchdog_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, watchdog_command, debug)

    time.sleep(0.5)

    #read back num_read_bytes bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU watchdog config response: [{' '.join(f'{b:02X}' for b in data)}]")
        return data
    else:
        return None
    
def PSU_set_voltage(ser, voltage, debug=False):
    num_read_bytes = 8
    hex_voltage = int((voltage - 15.092)/-0.013)
    print("voltage: %.2f V -> hex: 0x%02X" % (voltage, hex_voltage))
    set_voltage_command = [PSU_CMD_SET_VOLTAGE, hex_voltage, 0x00]
    set_voltage_command = make_packet(set_voltage_command)
    print(f"Sending PSU set voltage: [{' '.join(f'{b:02X}' for b in set_voltage_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, set_voltage_command, debug)

    time.sleep(0.5)

    #read back num_read_bytes bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU set voltage response: [{' '.join(f'{b:02X}' for b in data)}]")
        return data
    else:
        return None
    
def PSU_get_voltage(ser, debug=False):
    num_read_bytes = 8
    voltage_command = [PSU_CMD_GET_VOLTAGE]
    voltage_command = make_packet(voltage_command)
    print(f"Sending PSU read voltage: [{' '.join(f'{b:02X}' for b in voltage_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, voltage_command, debug)

    time.sleep(0.5)

    #read back num_read_bytes bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU voltage response: [{' '.join(f'{b:02X}' for b in data)}]")
        print("Read Voltage = %.3f V" % (15.092 - (data[4] * 0.013)))
        return data
    else:
        return None
    
def PSU_measure_voltage(ser, debug=False):
    num_read_bytes = 8
    measure_voltage_command = [PSU_CMD_MEASURE_VOLTAGE]
    measure_voltage_command = make_packet(measure_voltage_command)
    print(f"Sending PSU measure voltage: [{' '.join(f'{b:02X}' for b in measure_voltage_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, measure_voltage_command, debug)

    time.sleep(0.5)

    #read back num_read_bytes bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU measured voltage response: [{' '.join(f'{b:02X}' for b in data)}]")
        measured_voltage = (data[5] << 8 | data[4])
        print("Measured Voltage = 0x%04X (%d)" % (measured_voltage, measured_voltage))
        return data
    else:
        return None