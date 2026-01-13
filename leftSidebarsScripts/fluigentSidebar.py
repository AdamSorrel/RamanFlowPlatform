import sys, os, time

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.uic import loadUi
import icons_rc
# Loading prior stage library
from ctypes import WinDLL, create_string_buffer

from Fluigent.SDK import fgt_init, fgt_close, fgt_detect, fgt_ERROR
from Fluigent.SDK import fgt_set_pressure, fgt_get_pressure, fgt_get_pressureRange

from Fluigent.SDK import fgt_create_simulated_instr, fgt_get_pressureChannelsInfo
from Fluigent.SDK import fgt_CHANNEL_INFO

import warnings

class pressureRampThread(QThread):
    change_value = pyqtSignal()
    def __init__(self, pressureRamp):
        super().__init__()
        self.pressureRamp = pressureRamp
        print("[pressureRampThread] Activated! ")

    def run(self):
        while True:
            time.sleep(10)

            if self.pressureRamp.isChecked():

                self.change_value.emit()




class pressureThread(QThread):
    change_value = pyqtSignal(float)
    def __init__(self, channel):
        super().__init__()
        self.channel = channel
        print("[pressureThread] pressure thread initialized.")


    def run(self):
        while True:
            time.sleep(0.5)

            currentChannel = self.channel.currentText()
            currentChannel = currentChannel.split(":")[0]
            currentChannel = currentChannel.split(" ")[1]
            #print(f"[pressureThread] current channel selected: {currentChannel}")

            # Or if you are using > Python 3.11:
            with warnings.catch_warnings(action="ignore"):
                pressure = fgt_get_pressure(currentChannel)
            
                self.change_value.emit(pressure)
            #self.currentTemperature.setText(str(temperature) + " °C")
            #print(f"Function GetTemperature returned {ret} current temperature = {temperature} ", end='\r')



class loadFluigentSiebar(QWidget):
    def __init__(self):
        super().__init__()

        loadUi("leftSidebarsUIs/fluigentSidebar.ui", self)
        
        
        ######################################################
        # Connecting buttons
        ######################################################

        self.regularPressureSpinBox.valueChanged.connect(self.setPressure)
        self.activateFluidgenBtn.clicked.connect(self.activatePressureThread)

        
   
    def activatePressureThread(self):
        ######################################################
        # Detect machine
        ######################################################
        simulated = False
        # Detect all controllers
        SNs, types = fgt_detect()
        # If not devices are detected, create a simulated device.
        if len(SNs) == 0:
            # If no controller is detected, a simulated device is set up
            fgt_create_simulated_instr(instr_type = 2, # MFCS™ series instrument"
                                       serial = 1000,
                                       version = 0,
                                       config = [4,4,4,4,4,4,4,4])
            print("[fluigentSidebar] No instrument detected, a simulated instrument is set up.")
            SNs, types = fgt_detect()
            simulated = True
        
        controllerCount = len(SNs)
        print(f"[loadFluigentSidebar/activatePressureThread] Detected instruments SNs: {SNs}, types: {types}.")
        #print(f'[fluigentSidebar] Number of controllers detected: {controllerCount}')

        ## Initialize the session
        # This step is optional, if not called session will be automatically
        # created
        res = fgt_init()
        print(f"[fluigentSidebar] Fluigent pump initialized with a code {res}")

        for type, sn in zip(types, SNs):
            if simulated:
                self.fluigentDeviceCBox.addItem(f"Simulated: {type}, SN: {sn}")
            else:
                self.fluigentDeviceCBox.addItem(f"{type}: {sn}")

        channels = fgt_get_pressureChannelsInfo()

        for channel in channels:
            self.fluigentChannelsCBox.addItem(f"Channel {channel.index}: {channel.InstrType}")

        # Thread updating current pressure
        self.temperatureThread = pressureThread(self.fluigentChannelsCBox)
        self.temperatureThread.change_value.connect(self.updatePressure)
        self.temperatureThread.start()

        self.pressureRampThread = pressureRampThread(self.pressureRampCBox)
        self.pressureRampThread.change_value.connect(self.increasePressure)
        self.pressureRampThread.start()

    def increasePressure(self):
        currentChannel = self.fluigentChannelsCBox.currentText()
        currentChannel = currentChannel.split(":")[0]
        currentChannel = currentChannel.split(" ")[1]

        # Getting a pressure step from the
        increase = self.rampStepSpinBox.value()

        self.currentSetPressure = self.regularPressureSpinBox.value()
        self.desiredPressure = self.currentSetPressure + increase
        self.regularPressureSpinBox.setValue(self.desiredPressure)

        #ret = fgt_set_pressure(currentChannel, self.desiredPressure)

    def updatePressure(self, pressure):
        self.currentPressureValue.setText(f"{pressure:.1f} mbar")

    def setPressure(self):
        desiredPressure = self.regularPressureSpinBox.value()

        currentChannel = self.fluigentChannelsCBox.currentText()
        currentChannel = currentChannel.split(":")[0]
        currentChannel = currentChannel.split(" ")[1]
        
        ret = fgt_set_pressure(currentChannel, desiredPressure)
        print(f"[fluigentSidebar/setPressure] Setting regular pressure on channel {self.fluigentChannelsCBox.currentText()} to: {desiredPressure} returned {ret}")
        

if __name__ == "__main__":
    print("Not possible to load fluigentSidebar alone.")
