import RPi.GPIO as GPIO
import time

# GPIO pin definitions
IN1 = 17  # GPIO pin connected to IN1
IN2 = 27  # GPIO pin connected to IN2
ENA = 22  # GPIO pin connected to ENA (for PWM speed control, optional)

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(ENA, GPIO.OUT)

# Set up PWM on ENA pin (motor speed)
pwm = GPIO.PWM(ENA, 1000)  # 1kHz frequency
pwm.start(0)               # Start with 0% duty cycle (motor off)

def motor_forward(speed=100):
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    pwm.ChangeDutyCycle(speed)
    print(f"Motor running forward at {speed}% speed.")

def motor_backward(speed=100):
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    pwm.ChangeDutyCycle(speed)
    print(f"Motor running backward at {speed}% speed.")

def motor_stop():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    pwm.ChangeDutyCycle(0)
    print("Motor stopped.")

try:
    # Example usage
    motor_forward(75)
    time.sleep(3)

    motor_backward(50)
    time.sleep(3)

    motor_stop()

except KeyboardInterrupt:
    pass

finally:
    pwm.stop()
    GPIO.cleanup()
    print("GPIO cleanup complete.")
