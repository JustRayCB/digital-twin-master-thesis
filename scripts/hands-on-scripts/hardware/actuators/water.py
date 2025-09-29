from time import sleep

import RPi.GPIO as GPIO

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

water_pump_PIN = 24  # Water Pump

GPIO.setup(water_pump_PIN, GPIO.OUT, initial=GPIO.HIGH)


# Water Pump Control
def activate_water_pump(duration):
    GPIO.output(water_pump_PIN, GPIO.LOW)  # Activate the water pump
    print("Water pump activated.")
    sleep(duration)  # Keep the pump on for the specified duration
    GPIO.output(water_pump_PIN, GPIO.HIGH)  # Deactivate the water pump
    print("Water pump deactivated.")


# Example usage
if __name__ == "__main__":
    try:
        duration = 2 
        activate_water_pump(duration)
    except KeyboardInterrupt:
        print("Water pump control interrupted.")
    finally:
        GPIO.cleanup()  # Clean up GPIO settings
        print("GPIO cleanup done.")
