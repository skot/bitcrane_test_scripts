import serial
import time
import APW_PSU

try:
    serial_port_ctrl = serial.Serial(
        port='/dev/tty.usbmodemb310cc521',  # Update this to your serial port
        baudrate=115200,
        timeout=1
    )
except serial.SerialException as e:
    print(f"Error opening Control serial port: {e}")
    exit(1)


APW_PSU.PSU_set_enable(serial_port_ctrl, enable=True, debug=True)
time.sleep(0.5)  # wait for PSU to power up

APW_PSU.PSU_get_hw_version(serial_port_ctrl, False)

APW_PSU.PSU_disable_watchdog(serial_port_ctrl, False)

#APW_PSU.PSU_get_voltage(serial_port_ctrl, False)

APW_PSU.PSU_set_voltage(serial_port_ctrl, 12.00, False)

APW_PSU.PSU_get_voltage(serial_port_ctrl, False)

