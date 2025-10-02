from gpiozero import DistanceSensor
from time import sleep

# Create DistanceSensor object (echo, trigger)
# Adjust GPIO pins if needed (BCM numbering)
sensor = DistanceSensor(echo=23, trigger=24)

try:
    while True:
        distance = sensor.distance * 100  # meters to cm
        print(f"Distance: {distance:.1f} cm")
        sleep(0.5)
except KeyboardInterrupt:
    print("Measurement stopped by user")
