import sys, os

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt5.QtWidgets import QPushButton, QLabel, QWidget, QComboBox, QDoubleSpinBox
from PyQt5.uic import loadUi
import icons_rc
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

class loadBottomWidgetFunctions(QWidget):
    def __init__(self, sdk, spc, elements):
        super().__init__()
        self.sdk = sdk
        self.spc = spc
        self.elements = elements
        #self.sdk = atmcd()  # Load the atmcd library
        self.codes = atmcd_codes
        print(f"[leftSidePanel] sdk : {self.sdk}")

        #self.startBtn = self.findChild(QPushButton, "startBtn")
        self.elements.startBtn.clicked.connect(self.startAcquisition)
        #self.exposureValue = self.findChild(QDoubleSpinBox, "exposureValue")
        self.elements.exposureValue.valueChanged.connect(self.setExposureTime)

        # Finding QLabels with exposure values to fill in
        #self.exposureValue = self.findChild(QLabel, "exposureValue")
        #self.kineticValue = self.findChild(QLabel, "kineticValue")
        #self.accumulateValue = self.findChild(QLabel, "accumulateValue")
        self.readModeCBox = self.findChild(QComboBox, "readModeCBox")

        (ret, self.xpixels, self.ypixels) = self.sdk.GetDetector()
        
        print("[startAcquisition] Function GetDetector returned {} xpixels = {} ypixels = {}".format(
        ret, self.xpixels, self.ypixels))


    def setExposureTime(self):
        desiredExposureTime = self.exposureValue.value()

        print(f"[setExposureTime] attempting to set exposure time to : {desiredExposureTime}")
        
        ret = self.sdk.SetExposureTime(desiredExposureTime)
        print(f"[setExposureTime] Function SetExposureTime returned {ret} time = {desiredExposureTime}s")

        (ret, fminExposure, fAccumulate, fKinetic) = self.sdk.GetAcquisitionTimings()
        print(f"[setExposureTime] Function GetAcquisitionTimings returned {ret} exposure = {fminExposure} accumulate = {fAccumulate} kinetic = {fKinetic}")

        self.exposureValue.setText(f"{fminExposure} s")
        self.accumulateValue.setText(f"{fAccumulate} s")
        self.kineticValue.setText(f"{fKinetic} s")

    def fullVerticalBinning(self):
        print("Full vertical binning")
        imageSize = self.xpixels
        (ret, arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
        print("[startAcquisition] Function GetImages16 returned {} first pixel = {} size = {}".format(
            ret, arr[0], imageSize))

    def singleTrack(self):
        print("Single track")

    def multiTrack(self):
        print("Multi track")

    def randomTrack(self):
        print("Random track")
    
    def image(self):
        print("Image")

    def startAcquisition(self):

        self.setExposureTime()

        ret = self.sdk.PrepareAcquisition()
        print("[startAcquisition] Function PrepareAcquisition returned {}".format(ret))

        # Perform Acquisition
        ret = self.sdk.StartAcquisition()
        print("[startAcquisition] Function StartAcquisition returned {}".format(ret))

        ret = self.sdk.WaitForAcquisition()
        print("[startAcquisition] Function WaitForAcquisition returned {}".format(ret))

        readMode = self.readModeCBox.currentText()
        
        # Read mode options switch block structure
        readModeOptions = {
            "Full vertical binning": self.fullVerticalBinning,
            "Single track": self.singleTrack,
            "Multi track" : self.multiTrack,
            "Random track" : self.randomTrack,
            "Image": self.image}
        
        readModeOptions[readMode]()
        
        """
        if readMode == "Full vertical binning":
            imageSize = xpixels
            (ret, arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
            print("[startAcquisition] Function GetImages16 returned {} first pixel = {} size = {}".format(
                ret, arr[0], imageSize))
        elif readMode == "Single track":
            print("[startAcquisition] Single track")
        elif readMode == "Multi track": 
            print("[startAcquisition] Multi track")
        elif readMode == "Random track":
            print("[startAcquisition] Random track")
        elif readMode == "Image":
            print("[startAcquisition] Image")
        else:
            print("[startAcquisition] Unknown read mode {readMode}")
        """
