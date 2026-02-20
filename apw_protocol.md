# Bitmain APW12 PSU Data Protocol
The Bitmain APW12 Power Supply is controlled and monitored over a data connection. 
400*Hz** (yes, Hz) I2C connection at 3.3V. Each byte of a packet is a separate I2C transaction.

**Packet Format**

| 0      | 1      | 2   | 3   | 4        | 5        | 6      | 7      |
|--------|--------|-----|-----|----------|----------|--------|--------|
| PRE LO | PRE HI | LEN | CMD | PARAM LO | PARAM HI | CHK LO | CHK HI |

```
0. Preamble LSB
    - Always 0x55
1. Preamble MSB
    - Always 0xAA
2. Length
	- Including Length & Checksum Bytes, but not preamble.
3. Command
    - 0x01: Get PSU FW Version
    - 0x02: Get PSU HW Version
    - 0x03: Get PSU Output voltage setting
    - 0x04: Measure PSU Output voltage
    - 0x06: Calibration Memory Read
    - 0x0A: PSU Watchdog
    - 0x81: Disable PSU watchdog
    - 0x83: Set PSU output voltage
4-5. Parameter LSB & MSB
	- optional command parameter 
6. Checksum
	- simple sum of bytes (LEN + CMD + PARAM) & 0xFFFF
```

**Commands**
