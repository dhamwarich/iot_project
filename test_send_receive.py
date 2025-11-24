import serial
import time

try:
	ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
	ser.flush()
	print("Connected to STM32. Ready to control LED")
except:
	print("Error: Could not connect to /dev/ttyACM0. Is the USB plugged in?")
	exit()
	
try:
	while True:
		
		user_input = input("Type '1' to turn On. '0' to turn Off (or 'q' to quit): ")
		
		if user_input == 'q':
			break
			
		if user_input in ['1', '0']:
			ser.write(user_input.encode('utf-8'))
			print(f"Sent Command: {user_input}")
		else:
			print("Invalid command. Please use 1 or 0")
			
except KeyboardInterrupt:
	print("\nExiting...")
finally:
	ser.close()
