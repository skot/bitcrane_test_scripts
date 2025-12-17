import time
import struct
import bitcrane
from math import ceil, fabs

#interface for the TMP75 temperature sensors on the Antminer S19j Pro's 3 hashboards

TMP75_HB0_I2CADDR0 = 0x4C
TMP75_HB0_I2CADDR1 = 0x48
TMP75_HB1_I2CADDR0 = 0x4D
TMP75_HB1_I2CADDR1 = 0x49
TMP75_HB2_I2CADDR0 = 0x4E
TMP75_HB2_I2CADDR1 = 0x4A 

TMP75_TEMP_REG = 0x00       # Temperature register (read 12 bits)
TMP75_CONFIG_REG = 0x01     # Configuration register (defaults to 0x00)
TMP75_TLO_REG = 0x02        # Temperature low limit register
TMP75_THI_REG = 0x03        # Temperature high limit register

     
def prettyHex(data):
    return ' '.join(f'{byte:02X}' for byte in data)

def read_temperature(ser, chipnum=0, hashboard_num=0, debug=False):

    if hashboard_num == 0:
        if chipnum == 0:
            address = TMP75_HB0_I2CADDR0
        else:
            address = TMP75_HB0_I2CADDR1
    elif hashboard_num == 1:
        if chipnum == 0:
            address = TMP75_HB1_I2CADDR0
        else:
            address = TMP75_HB1_I2CADDR1
    elif hashboard_num == 2:
        if chipnum == 0:
            address = TMP75_HB2_I2CADDR0
        else:
            address = TMP75_HB2_I2CADDR1

    data = bitcrane.i2c_read_bytes(ser, 0xBB, address, TMP75_TEMP_REG, 2, debug)

    # convert data to signed 12 bit integer with struct
    temp = (struct.unpack('>h', data)[0] >> 4) / 16.0

    if debug:
        print("Raw Temperature = %02X %02X" % (data[0], data[1]))
        print("Temperature = %.2f" % temp)

    return temp

def read_config(ser, hashboard_num=0):

    if hashboard_num == 0:
        address = TMP75_HB0_I2CADDR0
    elif hashboard_num == 1:
        address = TMP75_HB1_I2CADDR0
    elif hashboard_num == 2:
        address = TMP75_HB2_I2CADDR0

    data = bitcrane.i2c_read_bytes(ser, 0xCC, address, TMP75_CONFIG_REG, 1)[0]

    print("Config Register = %02X" % data)

    return data
