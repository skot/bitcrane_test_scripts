import bitcrane
import struct
import time

# Command bytes confirmed by PIC16F1704 firmware disassembly (APW121215a-Good.dis)
# Dispatch table at label_037 / address 0x03f0:
PSU_CMD_GET_FW_VERSION  = 0x01  # label_028: returns 16-byte FW version table
PSU_CMD_GET_HW_VERSION  = 0x02  # label_029: returns HW version data
PSU_CMD_GET_VOLTAGE     = 0x03  # label_030: returns current DAC setpoint (1 byte)
PSU_CMD_MEASURE_VOLTAGE = 0x04  # label_031: triggers ADC, returns 2-byte result
PSU_CMD_READ_POWER      = 0x05  # label_032: returns 16-bit live power accumulator
PSU_CMD_READ_CAL        = 0x06  # label_033: reads EEPROM cal page (sub1=page, sub2=offset)
PSU_CMD_SET_VOLTAGE     = 0x83  # label_034: writes DAC, echoes new setpoint
PSU_CMD_WRITE_CAL       = 0x86  # label_035: writes EEPROM cal (inverse of READ_CAL)
PSU_CMD_WATCHDOG        = 0x81  # fallthrough/echo-ACK: host keep-alive heartbeat
                                 #   payload 0x00 = disable, non-zero = enable

# Legacy aliases kept for backward compatibility
PSU_CMD_FEED_WDT   = PSU_CMD_WATCHDOG
PSU_CMD_DISABLE_WDT = PSU_CMD_WATCHDOG

# The bosminer 0x41/0x46 calibration commands are NOT in the PIC dispatch table
# (they returned NAK 0xF5). The real per-unit calibration constants are stored
# in PROGRAM FLASH at word addresses 0x0FFA (primary) and 0x0FDA (secondary),
# written once at the factory via ICSP. They are NOT accessible via I2C.
# The EEPROM (READ_CAL 0x06 / WRITE_CAL 0x86) is a separate data store;
# on this unit all EEPROM bytes are 0xFF (blank/unprogrammed).
PSU_CAL_PAGE_DEFAULT = 0x40    # only confirmed EEPROM page that returns a data frame
PSU_CAL_OFFSET_START = 0x00    # start of calibration block within EEPROM page

# Default DAC calibration constants from bosminer binary analysis
# (IEEE 754 doubles: 0x402e000000000000 = 15.0, 0xbf88181818181818 = -0.012)
# Voltage formula: hex_dac = round((voltage - DAC_REF) / DAC_OFFSET)
#                  voltage  = DAC_REF + DAC_OFFSET * hex_dac
#
# Per-unit calibration is stored in PROGRAM FLASH (not EEPROM):
#   Primary location:   word 0x0FFA (byte addr 0x1FF4) — checked first by PIC
#   Secondary location: word 0x0FDA (byte addr 0x1FB4) — fallback
#   Format: flash word = 0x35nn where nn is the 8-bit DAC calibration code
#   Blank flash = 0x3FFF (PIC falls back to label_020 hardcoded defaults)
#
# APW121215a GOOD firmware calibration codes (from hex diff):
#   Primary  0x0FFA: DAC code 0xF8 = 248  →  15.0 − 0.012×248 = 12.024 V (design)
#   Secondary 0x0FDA: DAC code 0xF7 = 247 →  15.0 − 0.012×247 = 12.036 V (design)
#
# BAD firmware (over-voltage/corrupt):
#   Both locations have non-0x35 opcodes (0x0BCE/0x0BCF); PIC validation fails,
#   falls back to an out-of-spec setpoint (~12.5 V).
#
# The EEPROM (READ_CAL 0x06) on this unit is blank (all 0xFF).
# Calibration CANNOT be read back via I2C — it must be read via ICSP.
#
# Empirically calibrated 2026-03-05 via 8-point sweep (12.0–15.0 V, 0.5 V steps).
# Linear fit: V = dac_ref + dac_offset * dac_code   R² = 0.999999
# Max error across sweep range: 1.1 mV.
# (bosminer nominal: dac_ref=15.0, dac_offset=-0.012)
DAC_REF_DEFAULT    = 15.1084  # V
DAC_OFFSET_DEFAULT = -0.013046  # V/count

# Factory calibration DAC codes burned into program flash (APW121215a-Good):
DAC_CAL_PRIMARY   = 0xF8  # = 248 → 15.1084 − 0.013046×248 = 11.873 V at calibrated ref
DAC_CAL_SECONDARY = 0xF7  # = 247 → 15.1084 − 0.013046×247 = 11.886 V at calibrated ref


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
        bitcrane.gpio_set(ser, 0xAB, bitcrane.GPIO_PSU_EN, bitcrane.GPIO_LOW, debug)
    else:
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
    
def PSU_get_fw_version(ser, debug=False):
    num_read_bytes = 8
    version_command = [PSU_CMD_GET_FW_VERSION]
    version_command = make_packet(version_command)
    print(f"Sending PSU FW version: [{' '.join(f'{b:02X}' for b in version_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, version_command, debug)

    time.sleep(0.5)

    #read back num_read_bytes bytes
    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU FW Version response: [{' '.join(f'{b:02X}' for b in data)}]")
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

def _psu_read_frame(ser, debug=False):
    """
    Three-phase framed read matching the bosminer PSU I2C protocol:
      Phase 1: read 3 bytes  -> validate preamble (55 AA) + grab length
      Phase 2: read (length-1) bytes -> cmd echo + payload + checksum

    Returns the complete raw frame as a list, or None on failure.
    0xF5 in the length byte position is the PSU NAK.
    """
    # Phase 1: preamble + length
    hdr = psu_read_bytes(ser, 0x10, 3, debug)
    if not hdr or len(hdr) < 3:
        print("  _psu_read_frame: no header")
        return None
    if hdr[0] != 0x55 or hdr[1] != 0xAA:
        print(f"  _psu_read_frame: bad preamble [{hdr[0]:02X} {hdr[1]:02X}]")
        return None
    frame_len = hdr[2]
    if frame_len == 0xF5:
        print("  _psu_read_frame: PSU returned NAK (0xF5)")
        return None
    if frame_len <= 3:
        print(f"  _psu_read_frame: length 0x{frame_len:02X} too short")
        return None

    # Phase 2: remainder of the frame (frame_len bytes after the length byte)
    rest = psu_read_bytes(ser, 0x10, frame_len, debug)
    if not rest or len(rest) < frame_len:
        print(f"  _psu_read_frame: short read (wanted {frame_len}, got {len(rest) if rest else 0})")
        return None

    frame = hdr + rest
    if debug:
        print(f"  _psu_read_frame: [{' '.join(f'{b:02X}' for b in frame)}]")
    return frame

def PSU_read_cal_raw(ser, sub1=0x40, sub2=0x20, debug=False):
    """
    Send a raw calibration memory read command to the PSU and dump the response.

    The command [55 AA 06 06 40 20 6C 00] seen in other PSU reverse-engineering
    work corresponds to make_packet([PSU_CMD_READ_CAL=0x06, 0x40, 0x20]).
    Sub-byte sub1 is believed to select the calibration memory page/block;
    sub2 may be a sub-page or offset.

    Uses a 3-phase framed read (matching bosminer) so the exact number of bytes
    is always consumed, preventing buffer pollution for subsequent commands.
    """
    cmd = make_packet([PSU_CMD_READ_CAL, sub1, sub2])
    print(f"Sending PSU cal read [sub1=0x{sub1:02X} sub2=0x{sub2:02X}]: "
          f"[{' '.join(f'{b:02X}' for b in cmd)}]")
    psu_send_bytes(ser, 0x10, 0x11, cmd, debug)
    time.sleep(0.5)

    frame = _psu_read_frame(ser, debug)
    if frame is None:
        print(f"  PSU cal read [0x{sub1:02X}, 0x{sub2:02X}]: no valid response")
        return None

    # Parse the frame
    frame_len  = frame[2]           # bytes after the length byte (incl. checksum)
    cmd_echo   = frame[3]
    # payload = everything between cmd_echo and the final checksum byte
    payload    = frame[4 : 2 + frame_len]   # frame[2+frame_len] is the checksum
    checksum   = frame[2 + frame_len]

    print(f"  Full frame ({len(frame)} bytes): [{' '.join(f'{b:02X}' for b in frame)}]")
    print(f"  len=0x{frame_len:02X} ({frame_len}), cmd_echo=0x{cmd_echo:02X}, "
          f"checksum=0x{checksum:02X}")
    print(f"  Payload ({len(payload)} bytes): [{' '.join(f'{b:02X}' for b in payload)}]")

    all_ff = all(b == 0xFF for b in payload)
    if all_ff:
        print("  (payload is all 0xFF -- EEPROM may be blank or wrong sub-address)")
    else:
        # Try to interpret non-FF payload as IEEE 754 floats and doubles
        print("  --- Attempting to decode payload ---")
        # 4-byte floats (little-endian)
        for offset in range(0, len(payload) - 3, 4):
            chunk = bytes(payload[offset:offset + 4])
            if all(b == 0xFF for b in chunk):
                continue
            val_le = struct.unpack('<f', chunk)[0]
            val_be = struct.unpack('>f', chunk)[0]
            print(f"    float32 @ [{offset}:{offset+4}]: LE={val_le:.6g}  BE={val_be:.6g}")
        # 8-byte doubles (little-endian)
        for offset in range(0, len(payload) - 7, 8):
            chunk = bytes(payload[offset:offset + 8])
            if all(b == 0xFF for b in chunk):
                continue
            val_le = struct.unpack('<d', chunk)[0]
            val_be = struct.unpack('>d', chunk)[0]
            print(f"    float64 @ [{offset}:{offset+8}]: LE={val_le:.6g}  BE={val_be:.6g}")

    return frame

def PSU_read_calibration(ser, debug=False):
    """
    Read DAC calibration constants from the PSU EEPROM.

    PIC16F1704 disassembly (label_033) confirms the correct command is
    PSU_CMD_READ_CAL (0x06) with sub1=page (0x40) and sub2=offset.

    The bosminer 0x41/0x46 commands are NOT in the PIC dispatch table and
    always return NAK (0xF5). They are removed here.

    Response layout from firmware (label_033):
      frame[0:2] = 0x55 0xAA preamble
      frame[2]   = length
      frame[3]   = cmd echo (0x06)
      frame[4]   = sub1 echo (0x40)
      frame[5..] = EEPROM data bytes (up to 33 bytes)

    The DAC calibration coefficients (dac_ref, dac_offset) live in EEPROM
    page 0x40 at unknown offsets -- the exact layout requires either factory
    documentation or brute-force mapping. Until located, defaults are used.

    Returns dict with 'dac_ref', 'dac_offset', 'max_voltage'.
    """
    result = {
        'dac_ref':    DAC_REF_DEFAULT,
        'dac_offset': DAC_OFFSET_DEFAULT,
        'max_voltage': None,
    }

    # Read EEPROM page 0x40 starting at offset 0x00 (confirmed live page)
    frame = PSU_read_cal_raw(ser, sub1=PSU_CAL_PAGE_DEFAULT,
                              sub2=PSU_CAL_OFFSET_START, debug=debug)
    if frame is None:
        print("PSU_read_calibration: no response from EEPROM read, using defaults")
        return result

    # frame layout: [0x55, 0xAA, len, 0x06, sub1_echo, data...]
    if len(frame) < 6:
        print("PSU_read_calibration: frame too short, using defaults")
        return result

    eeprom_data = frame[5:]  # strip preamble + len + cmd_echo + sub1_echo
    if all(b == 0xFF for b in eeprom_data):
        print("PSU_read_calibration: EEPROM page is blank (all 0xFF), using defaults")
        return result

    # EEPROM calibration layout is not yet fully mapped.
    # As data is discovered, decode dac_ref and dac_offset from eeprom_data here.
    print(f"PSU_read_calibration: EEPROM data ({len(eeprom_data)} bytes): "
          f"[{' '.join(f'{b:02X}' for b in eeprom_data)}]")
    print("  Calibration layout not yet mapped -- using defaults. "
          "Compare with Good vs Bad firmware constant differences to identify offsets.")

    print(f"Calibration: dac_ref={result['dac_ref']:.4f} V, "
          f"dac_offset={result['dac_offset']:.6f} V/count, "
          f"max_voltage={result['max_voltage']}")
    return result

def PSU_set_voltage_raw(ser, hex_voltage, debug=False):
    num_read_bytes = 8
    print("Setting raw hex voltage: 0x%02X" % hex_voltage)
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

def PSU_set_voltage(ser, voltage, dac_ref=DAC_REF_DEFAULT, dac_offset=DAC_OFFSET_DEFAULT, debug=False):
    """
    Set the PSU output voltage.

    Transfer function (from bosminer binary analysis):
      hex_dac = round((voltage - dac_ref) / dac_offset)
      dac_ref    default = 15.0 V   (IEEE 754: 0x402e000000000000)
      dac_offset default = -0.012   (IEEE 754: 0xbf88181818181818)

    Pass the dict returned by PSU_read_calibration() as:
      cal = PSU_read_calibration(ser)
      PSU_set_voltage(ser, 12.5, cal['dac_ref'], cal['dac_offset'])
    """
    hex_voltage = int(round((voltage - dac_ref) / dac_offset))
    hex_voltage = max(0, min(255, hex_voltage))  # clamp to 8-bit DAC range
    print(f"PSU_set_voltage: {voltage:.3f} V -> DAC code 0x{hex_voltage:02X} "
          f"(dac_ref={dac_ref:.4f}, dac_offset={dac_offset:.6f})")
    PSU_set_voltage_raw(ser, hex_voltage, debug)

def PSU_get_voltage(ser, dac_ref=DAC_REF_DEFAULT, dac_offset=DAC_OFFSET_DEFAULT, debug=False):
    """
    Read back the DAC code that was last written to the PSU (command 0x03).
    NOTE: this is NOT an ADC measurement -- the PSU echoes the setpoint DAC
    code, not the actual output voltage.  Use PSU_measure_voltage() for a
    real ADC reading, or a multimeter for ground truth.
    """
    num_read_bytes = 8
    voltage_command = [PSU_CMD_GET_VOLTAGE]
    voltage_command = make_packet(voltage_command)
    print(f"Sending PSU read voltage setpoint: [{' '.join(f'{b:02X}' for b in voltage_command)}]")
    psu_send_bytes(ser, 0x10, 0x11, voltage_command, debug)

    time.sleep(0.5)

    data = psu_read_bytes(ser, 0x10, num_read_bytes, debug)
    if data:
        print(f"Read PSU voltage setpoint response: [{' '.join(f'{b:02X}' for b in data)}]")
        # Converts the echoed DAC code back to volts -- this is the *requested*
        # voltage, not a measurement.
        setpoint_volts = dac_ref + dac_offset * data[4]
        print("Voltage setpoint = %.3f V  (DAC code 0x%02X = echoed setpoint, NOT measured)"
              % (setpoint_volts, data[4]))
        return data
    else:
        return None

def PSU_calibrate_voltage(ser, multimeter_volts,
                          dac_ref=DAC_REF_DEFAULT, dac_offset=DAC_OFFSET_DEFAULT,
                          debug=False):
    """
    Single-point empirical calibration.

    Reads the current DAC code, pairs it with your multimeter reading, and
    returns a (dac_code, voltage) tuple suitable for PSU_fit_calibration().
    Also prints the single-point corrected dac_ref for reference.

    Returns (dac_code, measured_volts) or None on failure.
    """
    data = PSU_get_voltage(ser, dac_ref, dac_offset, debug)
    if data is None:
        print("PSU_calibrate_voltage: could not read DAC code from PSU")
        return None

    dac_code = data[4]
    single_pt_ref = multimeter_volts - dac_offset * dac_code
    print(f"Calibration point: DAC code=0x{dac_code:02X} ({dac_code}), "
          f"measured={multimeter_volts:.4f} V  "
          f"(single-pt dac_ref would be {single_pt_ref:.4f} V)")
    return (dac_code, multimeter_volts)


def PSU_fit_calibration(points):
    """
    Multi-point linear regression to find dac_ref and dac_offset.

    'points' is a list of (dac_code, measured_voltage) tuples collected
    at different setpoints across the PSU's operating range.

    Fits the model:  V = dac_ref + dac_offset * dac_code
    using ordinary least squares (no numpy required).

    With 1 point: solves for dac_ref only (keeps current dac_offset).
    With 2+ points: solves for both dac_ref and dac_offset simultaneously.

    Returns dict: {'dac_ref': float, 'dac_offset': float,
                   'max_voltage': None, 'n_points': int, 'r_squared': float}

    Example:
        points = [(238, 12.00), (72, 14.17)]
        cal = PSU_fit_calibration(points)
        PSU_set_voltage(ser, 12.5, cal['dac_ref'], cal['dac_offset'])
    """
    n = len(points)
    if n == 0:
        return {'dac_ref': DAC_REF_DEFAULT, 'dac_offset': DAC_OFFSET_DEFAULT,
                'max_voltage': None, 'n_points': 0, 'r_squared': None}

    if n == 1:
        code, volts = points[0]
        ref = volts - DAC_OFFSET_DEFAULT * code
        print(f"PSU_fit_calibration: 1 point -- solving dac_ref only (dac_offset fixed at {DAC_OFFSET_DEFAULT})")
        print(f"  dac_ref = {ref:.4f} V")
        return {'dac_ref': ref, 'dac_offset': DAC_OFFSET_DEFAULT,
                'max_voltage': None, 'n_points': 1, 'r_squared': None}

    # Least-squares fit: V = a + b*x  where a=dac_ref, b=dac_offset, x=dac_code
    sum_x  = sum(p[0] for p in points)
    sum_y  = sum(p[1] for p in points)
    sum_xx = sum(p[0]*p[0] for p in points)
    sum_xy = sum(p[0]*p[1] for p in points)
    denom  = n * sum_xx - sum_x * sum_x

    if abs(denom) < 1e-10:
        print("PSU_fit_calibration: degenerate system (all DAC codes identical?) -- using single-pt fallback")
        code, volts = points[0]
        ref = volts - DAC_OFFSET_DEFAULT * code
        return {'dac_ref': ref, 'dac_offset': DAC_OFFSET_DEFAULT,
                'max_voltage': None, 'n_points': n, 'r_squared': None}

    b = (n * sum_xy - sum_x * sum_y) / denom       # dac_offset
    a = (sum_y - b * sum_x) / n                      # dac_ref

    # R² to gauge fit quality
    mean_y = sum_y / n
    ss_tot = sum((p[1] - mean_y)**2 for p in points)
    ss_res = sum((p[1] - (a + b*p[0]))**2 for p in points)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-12 else 1.0

    print(f"PSU_fit_calibration: {n}-point linear fit:")
    print(f"  dac_ref    = {a:.4f} V   (was {DAC_REF_DEFAULT:.4f} V)")
    print(f"  dac_offset = {b:.6f} V/count   (was {DAC_OFFSET_DEFAULT:.6f} V/count)")
    print(f"  R²         = {r2:.6f}")
    for code, v_meas in sorted(points):
        v_fit = a + b * code
        print(f"    DAC 0x{code:02X} ({code:3d}): measured={v_meas:.4f} V  fit={v_fit:.4f} V  err={v_meas-v_fit:+.4f} V")

    return {'dac_ref': a, 'dac_offset': b, 'max_voltage': None,
            'n_points': n, 'r_squared': r2}
    
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
        print("Measured Voltage = 0x%04X (%.2f)" % (measured_voltage, (measured_voltage+0.8615)/63.017))
        return data
    else:
        return None