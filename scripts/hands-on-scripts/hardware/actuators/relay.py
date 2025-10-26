"""
This script provides a manual test for a 4-channel relay module connected to a
Raspberry Pi.

It allows the user to interactively turn each relay on and off by selecting
the corresponding GPIO pin. This is useful for verifying the wiring and
functionality of the relay module and the connected actuators (e.g., pump,
fan, light, heater).

The script uses the RPi.GPIO library and BCM pin numbering.

To run this script, execute the following command from the root of the project:
  poetry run python dt/scripts/hands-on-scripts/hardware/actuators/relay.py
"""


import RPi.GPIO as GPIO

# --- GPIO Setup ---
# Use Broadcom SOC channel numbering for GPIO pins.
GPIO.setmode(GPIO.BCM)
# Disable warnings about channels being already in use.
GPIO.setwarnings(False)

# --- Pin Definitions ---
# Define the GPIO pins connected to the IN terminals of the 4-channel relay.
# These relays are assumed to be active-low, meaning a LOW signal turns them on.
Relay1_PIN = 24  # Connected to the pump
Relay2_PIN = 22  # Connected to the LED
Relay3_PIN = 23  # Connected to the PTC heater
Relay4_PIN = 27  # Connected to the fan

# A list of all pins for easy iteration and user selection.
pins = [Relay1_PIN, Relay2_PIN, Relay3_PIN, Relay4_PIN]

# --- Initialize GPIO Pins ---
# Set all relay pins as outputs and initialize them to HIGH.
# Since the relays are active-low, a HIGH signal keeps them turned off.
GPIO.setup(pins, GPIO.OUT, initial=GPIO.HIGH)

print("--- Relay Test Script ---")
print(f"Relay pins to test: {pins}")
print("[Press Ctrl+C to end the script]")

try:
    # Main loop to continuously test relays.
    while True:
        try:
            # Prompt the user to select a pin to test.
            p_str = input(f"Please choose a pin from the list {pins}: ")
            p = int(p_str)
            if p not in pins:
                print("Invalid pin selected. Please try again.")
                continue

            # Activate the selected relay by setting the pin to LOW.
            GPIO.output(p, GPIO.LOW)
            print(f"Pin {p} activated (relay ON).")

            # Wait for the user to press Enter to deactivate the relay.
            input("Press Enter to deactivate...")

            # Deactivate the relay by setting the pin back to HIGH.
            GPIO.output(p, GPIO.HIGH)
            print(f"Pin {p} deactivated (relay OFF).")

        except ValueError:
            print("Invalid input. Please enter a number.")
        except Exception as e:
            print(f"An error occurred: {e}")

except KeyboardInterrupt:
    # This block is executed when the user presses Ctrl+C.
    print("\nScript terminated by user.")

finally:
    # This block is always executed, ensuring that the GPIO pins are cleaned up.
    # GPIO.cleanup() resets all channels you have used back to inputs.
    print("Cleaning up GPIO pins.")
    GPIO.cleanup()
