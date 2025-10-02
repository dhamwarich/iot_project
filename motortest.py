from gpiozero import Motor
from time import sleep

# Define the GPIO pins connected to IN1 and IN2 of the motor driver
motor = Motor(22, 27)
motor2 = Motor(16, 20)

print("Motor forward")
motor.forward()
motor2.forward()
sleep(5)

print("Motor backward")
motor.backward()
motor2.backward()
sleep(5)

print("Motor stop")
motor.stop()
motor2.stop()
