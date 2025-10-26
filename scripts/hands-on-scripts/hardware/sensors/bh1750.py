# SPDX-License-Identifier: Unlicense
"""
This script provides a simple test for the BH1750 light sensor.

It initializes the sensor on the default I2C bus and then enters an infinite
loop, printing the measured light intensity in lux every second. This is useful
for verifying that the sensor is wired correctly and functioning as expected.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/hardware/sensors/bh1750.py
"""
import time

import adafruit_bh1750
import board

i2c = board.I2C()  # uses board.SCL and board.SDA
# Use the second i2c bus
# i2c = busio.I2C(board.D1, board.D0)
# i2c = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller
sensor = adafruit_bh1750.BH1750(i2c)

while True:
    print("%.2f Lux" % sensor.lux)
    time.sleep(1)
