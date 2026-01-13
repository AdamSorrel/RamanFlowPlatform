import time

# Main pyQt import classes
from PyQt6.QtWidgets import (QMainWindow, QWidget, QPushButton, QLabel, QLineEdit,
                            QApplication, QComboBox, QVBoxLayout, QDoubleSpinBox, QSpinBox)
# pyQt core function (non graphical back end)
from PyQt6.QtCore import QThread, QMutex, pyqtSignal
# This loads the designer .ui file
from PyQt6.uic import loadUi
# Loads icons TODO: How to actually do that!
import icons_rc


class pressureThread(QThread):
    change_value = pyqtSignal(float)
    illustrious_signal_made_by_user = pyqtSignal(float)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
    
    def run(self):
        while True:
            time.sleep(0.5)
            pressure = fgt_get_pressure(currentChannel)
            #print(f"[pressureThread] current pressure: {pressure}")
            # This is communicating the retrieved pressure to the main class (loadTemplate in this case)
            self.change_value.emit(float(pressure))

class loadTemplate(QWidget):
    #def __init__(self, acquisitionQ, daqSettings, mainCanvasMdi, sdk, plotQ):.
    def __init__(self):
        super().__init__()
        #self.acqiusitionQ = acquisitionQ
        #self.daqSettings = daqSettings
        loadUi("leftSidebarsUIs/template.ui", self)

        # Thread updating current pressure
        # Load thread
        self.temperatureThread = pressureThread(self.fluigentChannelsCBox)
        # Connect signal emited by the thread to a function in the loadTemplate class
        self.temperatureThread.change_value.connect(self.updatePressure)
        self.temperatureThread.illustrious_signal_made_by_user.connect(self.illustiousFunction)
        # You have to always start a thread otherwise nothing works.
        self.temperatureThread.start()

        def updatePressure(self, pressure):
            self.currentPressureValue.setText(f"{pressure:.1f} mbar")