import random, sys

from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *

import qwt

from queue import Queue, Empty

import time

from com_monitor import ComMonitorThread
from livedatafeed import LiveDataFeed

# utilit function
# 
def get_all_from_queue(Q):
    """ Generator to yield one after the others all items 
        currently in the queue Q, without any waiting.
    """
    try:
        while True:
            yield Q.get_nowait()
    except Empty:
        # raise StopIteration # TODO looking to work with exception
        pass
    

def get_item_from_queue(Q, timeout=0.01):
    """ Attempts to retrieve an item from the queue Q. If Q is
        empty, None is returned.
        
        Blocks for 'timeout' seconds in case the queue is empty,
        so don't use this method for speedy retrieval of multiple
        items (use get_all_from_queue for that).
    """
    try: 
        item = Q.get(True, timeout)
    except Empty: 
        return None
    
    return item

    
class PlottingDataMonitor(QMainWindow):
    
    def __init__(self, parent=None):
        super(PlottingDataMonitor, self).__init__(parent)

        self.monitor_active = False
        self.com_monitor = None
        self.livefeed = LiveDataFeed()
        self.temperature_samples = []
        self.timer = QTimer()

        # menu
        # 
        self.file_menu = self.menuBar().addMenu("&File")
        selectport_action = QAction('Select TTY &Port...', self)
        selectport_action.triggered.connect(self.on_select_port)
        self.file_menu.addAction(selectport_action)

        self.start_action = QAction('&Start monitor')
        self.start_action.triggered.connect(self.on_start)
        self.start_action.setEnabled(False)
        self.file_menu.addAction(self.start_action)

        self.stop_action = QAction('&Stop monitor')
        self.stop_action.triggered.connect(self.on_stop)
        
        # main widget
        # 
        # port
        portname_label = QLabel('tty port:')
        self.portname = QLineEdit()
        self.portname.setEnabled(False)
        self.portname.setFrame(False)
        portname_layout = QHBoxLayout()
        portname_layout.addWidget(portname_label)
        portname_layout.addWidget(self.portname, 0)
        portname_layout.addStretch(1)
        portname_groupbox = QGroupBox('Port')
        portname_groupbox.setLayout(portname_layout)
        
        # plot widget 
        self.plot = qwt.QwtPlot(self)
        self.plot.setCanvasBackground(Qt.black)
        self.plot.setAxisTitle(qwt.QwtPlot.xBottom, 'Time')
        self.plot.setAxisScale(qwt.QwtPlot.xBottom, 0, 10, 1)
        self.plot.setAxisTitle(qwt.QwtPlot.yLeft, 'Temperature')
        self.plot.setAxisScale(qwt.QwtPlot.yLeft, 0, 250, 40)
        self.plot.replot()
        
        # curve widget
        self.curve = qwt.QwtPlotCurve('')
        self.curve.setRenderHint(qwt.QwtPlotItem.RenderAntialiased)
        pen = QPen(QColor('limegreen'))
        pen.setWidth(2)
        self.curve.setPen(pen)
        self.curve.attach(self.plot)

        # dial
        #
        self.dial = QDial()
        self.dial.setNotchesVisible(True)
        self.dial.setRange(0,20)
        self.dial.setValue(10)
        self.dial.valueChanged.connect(self.on_dial_change)

        self.dial_label = QLabel('Update speed = %s (Hz)' % self.dial.value())
        self.dial_label.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        dial_layout = QVBoxLayout()
        dial_layout.addWidget(self.dial)
        dial_layout.addWidget(self.dial_label)
        
        # plot layout
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.plot)
        plot_layout.addLayout(dial_layout)

        plot_groupbox = QGroupBox('Temperature')
        plot_groupbox.setLayout(plot_layout)
        
        
        # main
        self.main_frame = QWidget()
        main_layout = QVBoxLayout()
        main_layout.addWidget(portname_groupbox)
        main_layout.addWidget(plot_groupbox)
        main_layout.addStretch(1)
        self.main_frame.setLayout(main_layout)

        self.setCentralWidget(self.main_frame)

        # status
        #
        self.status_text = QLabel('Monitor idle')
        self.statusBar().addWidget(self.status_text, 1)

    def set_actions_enable_state(self):
        if self.portname.text() == '':
            start_enable = stop_enable = False
        else:
            start_enable = not self.monitor_active
            stop_enable = self.monitor_active
        
        self.start_action.setEnabled(start_enable)
        self.stop_action.setEnabled(stop_enable)

    def read_serial_data(self):
        '''Called periodically be the update timer to read data from the
serial port.

        '''
        qdata = list(get_all_from_queue(self.data_q))
        if len(qdata) > 0:
            # print(len(qdata))
            
            data = dict(timestamp=qdata[-1][1], 
                        temperature=ord(qdata[-1][0]))
            # print(data)
            self.livefeed.add_data(data)
        else:
            print('no data')

    def update_monitor(self):
        '''Updates the state of the monitor window with new data. The
livefeed is used to dind out whether new data was received since last
update. If not, nothing is updated.

        '''
        if self.livefeed.has_new_data:
            data = self.livefeed.read_data()
            # print(data)
            self.temperature_samples.append((data['timestamp'],
                                            data['temperature']))
            if len(self.temperature_samples) > 100:
                self.temperature_samples.pop(0)
            
            xdata = [s[0] for s in self.temperature_samples]
            ydata = [s[1] for s in self.temperature_samples]
            
            avg = sum(ydata) / float(len(ydata))
                
            self.plot.setAxisScale(qwt.QwtPlot.xBottom, xdata[0],
                                   max(20, xdata[-1]))
            self.curve.setData(xdata, ydata)
            self.plot.replot()

            
    # slots
    def on_select_port(self):
        text, ok = QInputDialog.getText(self, 'Port Name', 'Enter tty:')
        if ok:
            self.portname.setText(str(text))
            self.set_actions_enable_state()

    def on_start(self):
        '''Start the monitor: com_monitor thread and the update timer'''
        if self.com_monitor is not None or self.portname.text() == '':
            return

        self.data_q = Queue()
        self.error_q = Queue()
        self.com_monitor = ComMonitorThread( self.data_q,
                                             self.error_q,
                                             self.portname.text(),
                                             38400)
        self.com_monitor.start()
        com_error = None
        try:
            com_error = self.error_q.get(True, 0.01)
        except Empty:
            pass
        if com_error is not None:
            QMessageBox.critical(self, 'ComMonitorThread error',
                                 com_error)
            self.com_monitor = None

        self.monitor_active = True
        self.set_actions_enable_state()
        
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timer)

        update_freq = self.dial.value()
        if update_freq > 0:
            self.timer.start(1000/update_freq)

        self.status_text.setText('Monitor running')

    def on_stop(self):
        '''Stop the monitor'''
        if self.com_monitor is not None:
            self.com_monitor.join(0.01)
            self.com_monitor = None

        self.monitor_actibe = False
        self.timer.stop()
        self.set_actions_enable_state()

        self.status_text.setText('Monitor idle')
        
    def on_timer(self):
        '''Executed periodically when the monitor update timer is fired.'''
        self.read_serial_data()
        self.update_monitor()

    def on_dial_change(self):
        '''When the dial is rotated, it sets the update interval of the
timer'''
        update_freq = self.dial.value()
        self.dial_label.setText('Update speed = %s (Hz)' % self.dial.value())

        if self.timer.isActive():
            update_freq = max(0.01, update_freq)
            self.timer.setInterval(1000/update_freq)
        
if __name__ == '__main__':
    app = QApplication(sys.argv)
    form = PlottingDataMonitor()
    form.show()
    app.exec_()
