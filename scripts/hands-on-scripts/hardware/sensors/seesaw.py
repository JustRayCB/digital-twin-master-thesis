"""
This script provides a simple test for the Adafruit STEMMA Soil Sensor, which
uses the Seesaw I2C protocol.

It initializes the sensor on the default I2C bus and then enters an infinite
loop, printing the measured soil moisture and temperature every second. This
is useful for verifying that the sensor is wired correctly and functioning as
expected.

The default I2C address for this sensor is 0x36.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/hardware/sensors/seesaw.py

"""

# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import time

import board
from adafruit_seesaw.seesaw import Seesaw

i2c_bus = board.I2C()  # uses board.SCL and board.SDA
# i2c_bus = busio.I2C(board.D1, board.D0)
# i2c_bus = board.STEMMA_I2C()  # For using the built-in STEMMA QT connector on a microcontroller

ss = Seesaw(i2c_bus, addr=0x36)

while True:
    # read moisture level through capacitive touch pad
    touch = ss.moisture_read()

    # read temperature from the temperature sensor
    temp = ss.get_temp()

    print("temp: " + str(temp) + "  moisture: " + str(touch))
    time.sleep(1)
