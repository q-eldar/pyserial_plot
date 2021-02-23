import serial
import random, time, math
import struct

port = "/dev/pts/4"
ser = serial.Serial(port, 38400)

incycle = 0

while True:
    t = int(random.randint(60, 80) * (1 + math.sin(incycle)))
    x = ser.write(chr(t).encode())
    time.sleep(0.02)
    
    incycle += 0.01
    if incycle >= 2 * math.pi:
        incycle = 0


ser.close()
