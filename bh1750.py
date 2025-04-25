# SPDX-License-Identifier: Unlicense
import time

import adafruit_bh1750
import board
import busio

# i2c = board.I2C()  # uses board.SCL and board.SDA
# Use the second i2c bus
i2c = busio.I2C(board.D1, board.D0)
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
sensor = adafruit_bh1750.BH1750(i2c)

while True:
    print("%.2f Lux" % sensor.lux)
    time.sleep(1)

