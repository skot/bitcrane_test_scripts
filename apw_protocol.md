# Bitmain APW12 PSU Communication Protocol

The Bitmain APW12 family of power supplies is controlled and monitored over a
proprietary framed protocol carried over I2C.

---

## Physical Layer

| Parameter | Value |
|-----------|-------|
| Bus speed | 400 Hz (not kHz — four hundred Hz) |
| Logic level | 3.3 V |
| Addressing | Each byte of a packet is a separate I2C transaction |
| Direction | Host initiates all transactions; PSU responds |

The extremely low bus speed is intentional: the PSU microcontroller handles each
byte individually inside its I2C interrupt service routine.

---

## Frame Format

All packets — both host→PSU commands and PSU→host responses — use the same
layout:

```
Offset  Bytes  Field
------  -----  -----
0       1      Preamble LSB  = 0x55
1       1      Preamble MSB  = 0xAA
2       1      Length   (number of bytes from this field through the last
                        checksum byte, i.e. includes Length itself)
3       1      Command byte
4..N    N-3    Payload  (command-specific, 0 or more bytes)
N+1     1      Checksum (low byte of the arithmetic sum of all bytes
                        from Length through the last payload byte)
```

### Checksum

```
checksum = (length + command + sum(payload_bytes)) & 0xFF
```

A second `0x00` byte is sometimes appended after the checksum; the PSU ignores it.

### NAK

If the PSU rejects a frame (bad command, bad address, etc.) it writes the single
byte `0xF5` into the I2C buffer instead of a normal response frame.

### Minimum packet (no payload)

```
55 AA 04 <cmd> <chk> 00
```

Length = `0x04` (Length + Command + Checksum + 0x00 pad)

### Packet with two payload bytes

```
55 AA 06 <cmd> <p0> <p1> <chk> 00
```

Length = `0x06` (Length + Command + 2×Payload + Checksum + 0x00 pad)

---

## Command Summary

| Command | Name | Description |
|---------|------|-------------|
| `0x01` | GET_FW_VERSION | Returns 16-byte firmware version string |
| `0x02` | GET_HW_VERSION | Returns hardware version data |
| `0x03` | GET_VOLTAGE | Returns current DAC setpoint (1 byte, not a measurement) |
| `0x04` | MEASURE_VOLTAGE | ADC measurement of actual output; returns 2-byte raw value |
| `0x05` | READ_STATE | Returns PSU output-enable state (1 = ON, 0 = OFF) |
| `0x06` | READ_CAL | Reads bytes from calibration EEPROM |
| `0x81` | WATCHDOG | Keep-alive heartbeat. `0x00` = disable; non-zero = enable (~1 min timeout). |
| `0x83` | SET_VOLTAGE | Writes new DAC code to set output voltage |
| `0x86` | WRITE_CAL | Writes bytes to calibration EEPROM |

Commands with bit 7 set (≥ `0x80`) use an **echo-as-ACK** pattern: the PSU
constructs a response frame identical to the command to confirm it was accepted.

---

## Commands

### 0x01 — GET_FW_VERSION

Returns the PSU firmware version string.

**Request:**
```
55 AA 04 01 05 00
```

**Response payload:** 16-byte ASCII firmware version table.

---

### 0x02 — GET_HW_VERSION

Returns the PSU hardware version data.

**Request:**
```
55 AA 04 02 06 00
```

**Response payload:** Hardware version bytes.

---

### 0x03 — GET_VOLTAGE

Returns the current DAC setpoint register as a single byte.

**Request:**
```
55 AA 04 03 07 00
```

**Response:**
```
55 AA 06 03 <dac_code> 00 <chk> 00
```

> **Important:** This returns the *requested* DAC setpoint, not a measured
> output voltage. Use command `0x04` for an ADC-based measurement.

After a true hardware power-cycle (mains removed), the returned code is the
factory calibration value loaded from internal non-volatile memory. After any
`SET_VOLTAGE` (`0x83`) command, it reflects the last programmed setpoint.
This setpoint **persists across enable/disable cycles** until the hardware is
fully power-cycled.

---

### 0x04 — MEASURE_VOLTAGE

Triggers an ADC measurement of the actual output voltage and returns the raw
16-bit result.

**Request:**
```
55 AA 04 04 08 00
```

**Response:**
```
55 AA 06 04 <adc_lo> <adc_hi> <chk> 00
```

**ADC transfer function** (empirically determined):

```
raw     = adc_lo | (adc_hi << 8)
voltage = (raw + 0.8615) / 63.017    # volts
```

Example: raw `0x02F5` (757) → 12.03 V.

Allow 1–3 seconds of settling time after a setpoint change before reading.

---

### 0x05 — READ_STATE

Returns the PSU output-enable state

**Request:**
```
55 AA 04 05 09 00
```

**Response payload:** 2 bytes, little-endian 16-bit value.

| Value | Meaning |
|---|---|
| `0x0001` | Output ON (LATA5 high, PWM active) |
| `0x0000` | Output OFF (LATA5 low, PWM disabled) |

> **Firmware evidence:** `label_032` returns registers `0x0a8`/`0x0a9`.
> `function_017` (turn-on) sets them to `0x01`/`0x00` and drives **LATA5**
> high. `function_011` (turn-off) clears both and drives LATA5 low.
> No ADC sample, multiplication, or accumulator is involved.

---

### 0x06 — READ_CAL

Reads bytes from the PSU's internal calibration EEPROM.

**Request:**
```
55 AA 06 06 <page> <count> <chk> 00
```

| Argument | Description |
|----------|-------------|
| `page`   | Memory page selector. `0x40` is the only confirmed live page (returns a full data frame). Other values (`0x00`, `0x20`, `0x60`) return short frames. |
| `count`  | Number of EEPROM bytes to return. Maximum 33 (`0x21`) bytes per transaction. |

**Response:**
```
55 AA <len> 06 <page_echo> <data...> <chk> 00
```

> **Note:** The calibration EEPROM on factory-new or untrimmed units is entirely
> blank (all `0xFF`). Per-unit DAC calibration constants are stored in a
> separate write-once non-volatile area programmed during factory test and are
> not accessible via this command.

---

### 0x81 — WATCHDOG

Keep-alive heartbeat. The PSU monitors receipt of this command and shuts off
if it stops arriving.

**Request:**
```
55 AA 06 81 00 00 87 00    # disable watchdog
55 AA 06 81 0E 00 95 00    # enable watchdog
```

| Payload byte | Meaning |
|---|---|
| `0x00` | Disable watchdog — PSU stays on indefinitely |
| non-zero | Enable watchdog — PSU shuts off if heartbeat stops |

With the watchdog enabled the host must send this command periodically or the
PSU will shut off. Empirically, payloads `0x01` and `0x02` both produce a
~1-minute timeout, so **the payload value does not appear to scale the timeout
period** — it is likely a simple enable flag only. The value `0x0E` is
commonly used in production software; the resulting timeout is consistent with
the ~1-minute figure.

**Always disable the watchdog first** when testing or developing host software.

---

### 0x83 — SET_VOLTAGE

Sets the PSU output voltage by programming the internal DAC.

**Request:**
```
55 AA 06 83 <dac_code> 00 <chk> 00
```

**Response (echo-ACK):**
```
55 AA 06 83 <dac_code> 00 <chk> 00
```

The DAC is 8-bit. Valid codes are 0–255. Higher DAC code = lower output voltage.

See [DAC Calibration](#dac-calibration) for the transfer function and constants.

---

### 0x86 — WRITE_CAL

Writes data into the PSU's internal non-volatile calibration storage (the
inverse of `0x06`). Uses the same page/offset argument structure.

**Request:**
```
55 AA 06 86 <page> <data...> <chk> 00
```

The firmware implements this as a **program flash self-write** on the
PIC16F1704 microcontroller:

1. Erases the target 32-word flash row.
2. Copies existing row contents into RAM, merges in the new data.
3. Writes the full row back using the PIC's write-latch-and-commit sequence.

This is the mechanism Bitmain's factory test fixture uses to program per-unit
DAC calibration constants over I2C — an alternative to ICSP programming.
The `0x06` / `0x86` pair provides read/write access to the same calibration
flash region.

> **Caution:** This command writes to program flash. Incorrect use can corrupt
> firmware or calibration data. Do not use without understanding the target
> address and row layout.

---

## DAC Calibration

### Transfer function

```python
dac_code = round((target_voltage - dac_ref) / dac_offset)
voltage  = dac_ref + dac_offset * dac_code
```

### Constants (empirical, 8-point sweep 12.0–15.0 V, 2026-03-05)

| Constant | Value |
|---|---|
| `dac_ref` | **15.1084 V** |
| `dac_offset` | **−0.013046 V/count** |
| R² of linear fit | 0.999999 |
| Max error across 12–15 V | ≤ 1.1 mV |

### Sweep data

| DAC code | Measured (V) | Fit (V) | Error (mV) |
|---|---|---|---|
| 0x08 (8) | 15.003 | 15.004 | −1.0 |
| 0x2F (47) | 14.496 | 14.495 | +0.8 |
| 0x48 (72) | 14.170 | 14.169 | +0.9 |
| 0x55 (85) | 13.999 | 14.000 | −0.5 |
| 0x7B (123) | 13.503 | 13.504 | −0.7 |
| 0xA2 (162) | 12.996 | 12.995 | +1.1 |
| 0xC8 (200) | 12.499 | 12.499 | −0.2 |
| 0xEE (238) | 12.003 | 12.003 | −0.4 |

The PSU output is highly linear across its full operating range.

### Calibrating a new unit

1. Enable the PSU and disable the watchdog (`0x81` with payload `0x00`).
2. Read `GET_VOLTAGE` (`0x03`) before issuing any `SET_VOLTAGE` — after a cold
   power-cycle this returns the factory DAC code, which can bootstrap an
   initial single-point calibration.
3. Step through voltages across the operating range (e.g. 12.0–15.0 V in
   0.5 V increments), measuring actual output with a multimeter at each step.
4. Record `(dac_code, measured_voltage)` pairs and fit the linear model
   `V = dac_ref + dac_offset × code` using ordinary least squares.
   Two points is sufficient; more improves accuracy.
5. Use the fitted constants for all subsequent `SET_VOLTAGE` calls.

---

## Example Session

Enable PSU, disable watchdog, set 12.5 V, read back setpoint, measure ADC:

```
→  55 AA 06 81 00 00 87 00      # WATCHDOG: disable
←  55 AA 06 81 00 00 87 00      # echo = ACK

→  55 AA 06 83 C8 00 51 01      # SET_VOLTAGE: DAC 0xC8 (200) → 12.499 V
←  55 AA 06 83 C8 00 51 01      # echo = ACK

→  55 AA 04 03 07 00            # GET_VOLTAGE (setpoint readback)
←  55 AA 06 03 C8 00 D1 00      # DAC code 0xC8 (200) confirmed

→  55 AA 04 04 08 00            # MEASURE_VOLTAGE (ADC)
←  55 AA 06 04 14 03 21 00      # raw 0x0314 (788) → 12.52 V
```
