#!/usr/bin/env python3
import serial
import time
import math

# Serial port configuration
SERIAL_PORT = '/dev/tty.usbmodemb310cc521'  # Adjust as needed
BAUD_RATE = 115200

def send_led_color(ser, red, green, blue):
    """
    Send LED color command via serial.
    Bytes: [09 00 00 00 08 10 RR GG BB]
    where RR, GG, BB are the RGB values (0-255)
    """
    command = bytes([0x09, 0x00, 0x00, 0x00, 0x08, 0x10, red, green, blue])
    ser.write(command)
    print(f"Sent: {' '.join(f'{b:02X}' for b in command)} (R:{red:3d} G:{green:3d} B:{blue:3d})")

def rainbow_cycle(ser, duration=10):
    """
    Cycle through rainbow colors smoothly.
    duration: time in seconds for one complete cycle
    """
    start_time = time.time()
    
    try:
        while True:
            elapsed = time.time() - start_time
            # Normalize elapsed time to 0-1 over the duration
            phase = (elapsed % duration) / duration
            
            # Use HSV to RGB conversion for smooth rainbow
            # Hue goes from 0 to 360 degrees
            hue = phase * 360
            
            # Convert HSV to RGB
            rgb = hsv_to_rgb(hue, 1.0, 1.0)
            
            send_led_color(ser, rgb[0], rgb[1], rgb[2])
            
            time.sleep(0.05)  # Update every 50ms for smooth transitions
            
    except KeyboardInterrupt:
        print("\nStopping LED cycle...")

def hsv_to_rgb(hue, saturation, value):
    """
    Convert HSV (Hue, Saturation, Value) to RGB.
    Hue: 0-360 degrees
    Saturation: 0-1
    Value: 0-1
    Returns: (r, g, b) tuple with values 0-255
    """
    h = hue / 60.0
    c = value * saturation
    x = c * (1 - abs((h % 2) - 1))
    m = value - c
    
    if h < 1:
        r, g, b = c, x, 0
    elif h < 2:
        r, g, b = x, c, 0
    elif h < 3:
        r, g, b = 0, c, x
    elif h < 4:
        r, g, b = 0, x, c
    elif h < 5:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    
    return (
        int((r + m) * 255),
        int((g + m) * 255),
        int((b + m) * 255)
    )

if __name__ == '__main__':
    try:
        # Open serial connection
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"Connected to {SERIAL_PORT} at {BAUD_RATE} baud")
        time.sleep(1)  # Wait for connection to stabilize
        
        # Start rainbow cycle (10 seconds per full cycle)
        rainbow_cycle(ser, duration=10)
        
    except serial.SerialException as e:
        print(f"Error: Could not open serial port {SERIAL_PORT}")
        print(f"Details: {e}")
        print("Please check the serial port and make sure the device is connected.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial connection closed")
