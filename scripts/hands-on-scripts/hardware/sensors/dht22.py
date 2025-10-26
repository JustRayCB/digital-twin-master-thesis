"""
This script provides a simple test for the DHT22 temperature and humidity sensor.

It initializes the sensor on a specified GPIO pin and then enters an infinite
loop, printing the measured temperature (in both Celsius and Fahrenheit) and
humidity every 2 seconds. This is useful for verifying that the sensor is
wired correctly and functioning as expected.

This script also demonstrates how to handle the `RuntimeError` that can
frequently occur when reading from DHT-series sensors.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/hardware/sensors/dht22.py
"""

import time

import adafruit_dht
import board

# Initial the dht device, with data pin connected to:
dhtDevice = adafruit_dht.DHT22(board.D17)

# you can pass DHT22 use_pulseio=False if you wouldn't like to use pulseio.
# This may be necessary on a Linux single board computer like the Raspberry Pi,
# but it will not work in CircuitPython.
# dhtDevice = adafruit_dht.DHT22(board.D4, use_pulseio=False)


while True:
    try:
        # Print the values to the serial port
        temperature_c = dhtDevice.temperature
        temperature_f = temperature_c * (9 / 5) + 32
        humidity = dhtDevice.humidity
        print(
            "Temp: {:.1f} F / {:.1f} C    Humidity: {}% ".format(
                temperature_f, temperature_c, humidity
            )
        )

    except RuntimeError as error:
        # Errors happen fairly often, DHT's are hard to read, just keep going
        print(error.args[0])
        time.sleep(2.0)
        continue
    except Exception as error:
        dhtDevice.exit()
        raise error

    time.sleep(2.0)
