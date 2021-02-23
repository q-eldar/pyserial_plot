from queue import Queue, Empty
import threading
import time
import serial

class ComMonitorThread(threading.Thread):
    def __init__(self, data_q, error_q, port_num, port_baud,
                 port_stopbits=serial.STOPBITS_ONE,
                 port_parity=serial.PARITY_NONE, port_timeout=0.01):
        threading.Thread.__init__(self)

        self.serial_port = None
        self.serial_arg = dict(port=port_num,
                               baudrate=port_baud,
                               stopbits=port_stopbits,
                               parity=port_parity,
                               timeout=port_timeout)
        self.data_q = data_q
        self.error_q = error_q

        self.alive = threading.Event()
        self.alive.set()

    def run(self):
        try:
            if self.serial_port:
                self.serial_port.close()
            self.serial_port = serial.Serial(**self.serial_arg)
        except serial.SerialException as e:
            self.error_q.put(str(e))
            return

        time.time()

        while self.alive.isSet():
            data = self.serial_port.read(1)
            # print(data)
            data += self.serial_port.read(self.serial_port.inWaiting())

            if len(data) > 0:
                timestamp = time.time()
                temp = (data, timestamp)
                self.data_q.put((data, timestamp))

        # clean up
        if self.serial_port:
            self.serial_port.close()


    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)

if __name__ == '__main__':
    data_q = Queue()
    error_q = Queue()
    com = ComMonitorThread( data_q,
                            error_q,
                            '/dev/pts/5',
                            38400)
    com.start()
    
    while True:
        try:
            item = data_q.get_nowait()
            print(item)
        except Empty:
            print('no item')
            pass
        time.sleep(0.5)
