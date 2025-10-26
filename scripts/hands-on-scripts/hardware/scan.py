"""
This script scans the I2C bus for connected devices and prints their addresses.

It repeatedly scans the I2C bus every 2 seconds and prints a list of hexadecimal
addresses for all detected devices. This is useful for debugging I2C communication
and verifying that devices are correctly connected and recognized by the system.

To run this script, execute the following command from the root of the project:
  poetry run python scripts/hands-on-scripts/hardware/scan.py
"""

import time

import board

# --- I2C Bus Initialization ---

# To use the default I2C bus on most boards (e.g., Raspberry Pi).
# This should be the correct configuration for this project.
i2c = board.I2C()  # uses board.SCL and board.SDA

# --- Alternative I2C Configurations (for other hardware) ---
# Uncomment the one that matches your hardware setup if the default does not work.

# For using the built-in STEMMA QT connector on a microcontroller:
# i2c = board.STEMMA_I2C()

# To create an I2C bus on specific, non-default pins:
# import busio
# i2c = busio.I2C(board.SCL1, board.SDA1)  # Example for QT Py RP2040 STEMMA connector
# i2c = busio.I2C(board.GP1, board.GP0)    # Example for Pi Pico RP2040

# --- I2C Bus Scanning ---

# Attempt to lock the I2C bus before scanning. This is a required step before
# communicating on the bus to prevent conflicts with other I2C clients.
while not i2c.try_lock():
    pass

try:
    # Loop indefinitely to continuously scan for I2C devices.
    while True:
        print(
            "I2C addresses found:",
            [hex(device_address) for device_address in i2c.scan()],
        )
        time.sleep(2)  # Wait for 2 seconds before the next scan.

finally:
    # Ensure the I2C bus is unlocked when the script is terminated
    # (e.g., by pressing Ctrl+C). This is crucial to allow other programs
    # to use the I2C bus afterward.
    i2c.unlock()
