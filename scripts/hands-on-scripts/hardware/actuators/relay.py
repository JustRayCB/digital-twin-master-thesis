import RPi.GPIO as GPIO
from time import sleep
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
Relay1_PIN = 24 # PUMP
Relay2_PIN = 22 # LED 
Relay3_PIN = 23 # PTC
Relay4_PIN = 27 # FAN 
pins = [24, 22, 23, 27]
GPIO.setup(Relay1_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(Relay2_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(Relay3_PIN, GPIO.OUT, initial=GPIO.HIGH)
GPIO.setup(Relay4_PIN, GPIO.OUT, initial=GPIO.HIGH)
print('[press ctrl+c to end the script]')
try: # Main program loop
    i = 1 
    d = dict.fromkeys(pins)
    while True:
        p = int(input(f"Please choose  a number in the following list : {pins}: "))
        GPIO.output(p, GPIO.LOW)
        print(f"Normally opened {p} pin is activated")
        s = input(f"Press Enter to deactivate")
        GPIO.output(p, GPIO.HIGH)
        print(f'Normally opened {p} pin is deactivated')
        if i < len(pins):
            d[p] = str(input(f"Which hardware components ?: ")) 
            i += 1
        # Scavenging work after the end of the program
except KeyboardInterrupt:
    print(d)
    print('Script end!')
finally:
    GPIO.cleanup()
