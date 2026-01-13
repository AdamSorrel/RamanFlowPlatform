import serial, time, sys, glob

from PyQt6.QtWidgets import QWidget
from PyQt6.uic import loadUi

class loadShutterSidebar(QWidget):
    def __init__(self, sdk):
        super().__init__()
        self.sdk = sdk
        loadUi("leftSidebarsUIs/shutterSidebar.ui", self)

        self.openShutterBtn.clicked.connect(self.openShutter)
        self.closeShutterBtn.clicked.connect(self.closeShutter)
        self.autoShutterBtn.clicked.connect(self.shutterAuto)

        self.sdk.SetShutterEx(typ=1, mode=0, closingtime=5, openingtime=5, extmode=0)

    def openShutter(self):
        ret = self.sdk.SetShutterEx(typ=1, mode=0, closingtime=5, openingtime=5, extmode=1)
        print(f"[loadShutterSidebar] SetShutterEx returned: {ret} Shutter is open.")

    def closeShutter(self):
        ret = self.sdk.SetShutterEx(typ=1, mode=0, closingtime=5, openingtime=5, extmode=2)
        print(f"[loadShutterSidebar] SetShutterEx returned: {ret} Shutter is closed.")

    def shutterAuto(self):
        ret = self.sdk.SetShutterEx(typ=1, mode=0, closingtime=5, openingtime=5, extmode=0)
        print(f"[loadShutterSidebar] SetShutterEx returned: {ret} Shutter is in the automatic mode.")
        
    
    def exit(self):
        return 1