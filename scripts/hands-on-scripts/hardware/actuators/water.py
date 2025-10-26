"""
This script provides a simple test for controlling a water pump via a relay
connected to a Raspberry Pi.

It defines a function to activate the water pump for a specified duration.
The script assumes the pump is connected to a relay that is activated by a
LOW signal on the GPIO pin.

When run as the main program, it activates the pump for a default duration of
2 seconds and then cleans up the GPIO pins.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/hardware/actuators/water.py
"""

from time import sleep

import RPi.GPIO as GPIO

# --- GPIO Setup ---
# Use Broadcom SOC channel numbering for GPIO pins.
GPIO.setmode(GPIO.BCM)
# Disable warnings about channels being already in use.
GPIO.setwarnings(False)

# --- Pin Definition ---
# Define the GPIO pin connected to the IN terminal of the relay controlling the pump.
water_pump_PIN = 24

# --- Initialize GPIO Pin ---
# Set the pump's relay pin as an output and initialize it to HIGH.
# Since the relay is active-low, a HIGH signal keeps the pump turned off.
GPIO.setup(water_pump_PIN, GPIO.OUT, initial=GPIO.HIGH)


def activate_water_pump(duration: float):
    """Activates the water pump for a specified duration.

    This function sends a LOW signal to the GPIO pin to turn the relay on,
    waits for the specified duration, and then sends a HIGH signal to turn
    the relay off.

    Parameters
    ----------
    duration : float
        The duration in seconds for which the water pump should be active.
    """
    print(f"Activating water pump for {duration} seconds...")
    GPIO.output(water_pump_PIN, GPIO.LOW)  # Activate the relay (active-low).
    sleep(duration)  # Keep the pump on for the specified duration.
    GPIO.output(water_pump_PIN, GPIO.HIGH)  # Deactivate the relay.
    print("Water pump deactivated.")


# --- Example Usage ---
if __name__ == "__main__":
    try:
        # Set the duration for which the pump will run.
        duration = 2
        activate_water_pump(duration)
    except KeyboardInterrupt:
        # This block is executed if the user presses Ctrl+C.
        print("\nWater pump control interrupted by user.")
    finally:
        # This block is always executed, ensuring that the GPIO pins are cleaned up.
        # GPIO.cleanup() resets all channels you have used back to inputs.
        print("Cleaning up GPIO pins.")
        GPIO.cleanup()
