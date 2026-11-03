from machine import Pin, I2C
from bmp280 import BMP280

i2c = I2C(
    0,
    sda=Pin(21),
    scl=Pin(22),
    freq=100000
    )
bmp = BMP280(i2c,address=0x76)
temperatura, pressao = bmp.read()

print(f"Temperatura BMP280 : {temperatura:.1f} °C")
print(f"Pressão Atmosférica: {pressao:.2f}hPa")