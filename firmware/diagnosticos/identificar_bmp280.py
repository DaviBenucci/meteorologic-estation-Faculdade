from machine import Pin, I2C

i2c = I2C (
    0,
    sda=Pin(21),
    scl=Pin(22),
    freq=100000
)
endereco = 0x76

chip_id = i2c.readfrom_mem(endereco, 0xD0, 1)

print(f"Identificador do sensor: {hex(chip_id[0])}")