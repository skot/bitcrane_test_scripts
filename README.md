# Bitcrane v3 Test Scripts

A collection of Python test scripts for the Bitcrane v3 Bitcoin mining controller board. These scripts are used to test and interact with Antminer S19j Pro hashboards and associated hardware (fans, PSU, temperature sensors, LEDs).

## Requirements

- Python 3.x
- pyserial (`pip install pyserial`)

## Serial Port Configuration

All scripts communicate via USB serial ports. Update the serial port paths in each script to match your system:

```python
# macOS example
port='/dev/tty.usbmodemb310cc521'  # Control serial port
port='/dev/tty.usbmodemb310cc527'  # ASIC serial port

# Linux example
port='/dev/ttyUSB0'
port='/dev/ttyACM0'
```

## Scripts Overview

### Core Library

| File | Description |
|------|-------------|
| [bitcrane.py](bitcrane.py) | Core library with low-level functions for GPIO, fans, I2C, and ASIC communication |
| [APW_PSU.py](APW_PSU.py) | APW PSU (power supply unit) control library - voltage setting, watchdog, version queries |
| [TMP75.py](TMP75.py) | TMP75 temperature sensor interface for reading hashboard PCB temperatures |

### Test Scripts

| Script | Description | Usage |
|--------|-------------|-------|
| [fan_test.py](fan_test.py) | Set fan speeds and read tachometer RPM for FAN1 and FAN2 | `python fan_test.py <fan1_speed> <fan2_speed>` |
| [led_test.py](led_test.py) | Smoothly cycle the RGB LED through rainbow colors | `python led_test.py` |
| [psu_test.py](psu_test.py) | Test PSU communication - enable, set voltage, configure watchdog | `python psu_test.py` |
| [asic_ping.py](asic_ping.py) | Ping ASICs on a hashboard and read temperature sensors | `python asic_ping.py <hashboard_num>` |
| [i2c_test.py](i2c_test.py) | Continuously read I2C temperature sensors on a hashboard | `python i2c_test.py <hashboard_num>` |

## Usage Examples

### Fan Control

Set FAN1 to 50% and FAN2 to 75% speed, then read RPM values:
```bash
python fan_test.py 50 75
```

### LED Rainbow Cycle

Cycle the onboard LED through rainbow colors (Ctrl+C to stop):
```bash
python led_test.py
```

### ASIC Ping Test

Ping all ASICs on hashboard 0 and read temperatures:
```bash
python asic_ping.py 0
```

### I2C Temperature Reading

Continuously read temperature sensors on hashboard 1:
```bash
python i2c_test.py 1
```

### PSU Control

Enable PSU, configure watchdog, and set output voltage:
```bash
python psu_test.py
```

## Hardware Mapping

### Hashboard Numbers
- `0` - Hashboard slot 0
- `1` - Hashboard slot 1  
- `2` - Hashboard slot 2

### Fan Numbers
- `1` - FAN1
- `2` - FAN2
- `3` - FAN3
- `4` - FAN4

### GPIO Pins
| Pin | Function |
|-----|----------|
| `GPIO_HB0_RST` | Hashboard 0 Reset |
| `GPIO_HB0_PLUG` | Hashboard 0 Plug Detect |
| `GPIO_HB1_RST` | Hashboard 1 Reset |
| `GPIO_HB1_PLUG` | Hashboard 1 Plug Detect |
| `GPIO_HB2_RST` | Hashboard 2 Reset |
| `GPIO_HB2_PLUG` | Hashboard 2 Plug Detect |
| `GPIO_PSU_EN` | PSU Enable (active low) |

### Temperature Sensor I2C Addresses
| Hashboard | Sensor 0 | Sensor 1 |
|-----------|----------|----------|
| HB0 | 0x4C | 0x48 |
| HB1 | 0x4D | 0x49 |
| HB2 | 0x4E | 0x4A |

## Protocol Reference

### LED Command
```
[09 00 00 00 08 10 RR GG BB]
```
Where RR, GG, BB are RGB values (0x00-0xFF)

### Fan Speed Command
```
[07 00 ID 00 09 1X SS]
```
Where X is fan number (1-4) and SS is speed percent (0-100)

### Fan Tach Read Command
```
[06 00 ID 00 09 2X]
```
Returns 16-bit RPM value

## License

Open source hardware project.
