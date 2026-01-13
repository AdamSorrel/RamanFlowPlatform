import sys, os, time, redis, json

import pandas as pd

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QMessageBox, QWidget, QFileDialog
from PyQt6.QtCore import QPropertyAnimation, QParallelAnimationGroup, QRect, QSize, QThread, pyqtSignal
from PyQt6.uic import loadUi
import win32event  # pip install pyWin32
from datetime import datetime
import icons_rc
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
from pyAndorSpectrograph.spectrograph import ATSpectrograph

class TemperatureThread(QThread):
    change_value = pyqtSignal((int,int))
    def __init__(self, sdk):
        super().__init__()
        self.sdk = sdk
        print("[TemperatureThread] temperature thread initialized.")

    def run(self):
        while True:
            time.sleep(3)
            try:
                (ret, temperature) = self.sdk.GetTemperature()
            except:
                print("[TemperatureThread] Skipping temperature reading.")
            self.change_value.emit(int(ret),int(temperature))
            #self.currentTemperature.setText(str(temperature) + " °C")
            #print(f"Function GetTemperature returned {ret} current temperature = {temperature} ", end='\r')

class ExternalTrigger(QThread):
    #change_value = pyqtSignal((int,int))
    def __init__(self, sdk, spc, plotQ, acquisitionSidebar):
        super().__init__()
        self.sdk = sdk
        self.spc = spc
        self.plotQ = plotQ
        self.acquisitionSidebar = acquisitionSidebar
        self.terminateOperation = False
        print("[ExternalTriggerThread] ExternalTriggerThread thread initialized.")

        ret, self.calibrationValues = self.spc.GetCalibration(0, 1024)
        if ret == ATSpectrograph.ATSPECTROGRAPH_SUCCESS:
            print(f"[ExternalTriggerThread] Calibration values are {self.calibrationValues[0:9]}")
        elif ret == ATSpectrograph.ATSPECTROGRAPH_P1INVALID:
            print("[ExternalTriggerThread] Retrieving X calibration error: Invalid device, spectrograph not connected")
        elif ret == ATSpectrograph.ATSPECTROGRAPH_NOT_INITIALIZED:
            print("[ExternalTriggerThread] Retrieving X calibration error: Spectrograph not initialized")
        elif ret == ATSpectrograph.ATSPECTROGRAPH_COMMUNICATION_ERROR:
            print("[ExternalTriggerThread] Retrieving X calibration error: Communication error.")
        elif ret == ATSpectrograph.ATSPECTROGRAPH_P3INVALID:
            print("[ExternalTriggerThread] Retrieving X calibration error: Invalid number of pixels")
        else:
            print("[ExternalTriggerThread] Retrieving X calibration error: Unknown issue code: {ret}")

        # Enabling keep clean cycles
        # Note: Currently only available on Newton and iKon cameras operating in FVB external trigger mode.
        ret = sdk.EnableKeepCleans(mode=1)
        if ret == atmcd_errors.Error_Codes.DRV_SUCCESS:
            print("[ExternalTriggerThread] Keep clean mode enabled.")
        elif ret == atmcd_errors.Error_Codes.DRV_NOT_INITIALIZED:
            print("[ExternalTriggerThread] Error: Keep clean not enabled. Driver not initialized.")
        elif ret == atmcd_errors.Error_Codes.DRV_NOT_AVAILABLE:
            print("[ExternalTriggerThread] Error: Keep clean not initialized. Function not available.")
        else:
            print(f"[ExternalTriggerThread] Error: Keep clean return value error : {ret} ")

        (ret, self.xpixels, self.ypixels) = sdk.GetDetector()
        print(f"[ExternalTriggerThread] Function GetDetector returned {ret} xpixels = {self.xpixels} ypixels = {self.ypixels}")

        ret = sdk.PrepareAcquisition()
        print("[ExternalTriggerThread] Function PrepareAcquisition returned {}".format(ret))

        #-------------------------------
        #   Set data ready event
        #-------------------------------
        self.event = win32event.CreateEvent(None, 0, 0, None)
        ret = sdk.SetDriverEvent(self.event.handle)
        print("[ExternalTriggerThread] Function SetDriverEvent returned {}".format(ret))

        #-------------------------------
        #   Connect to REDIS database
        #-------------------------------
        # Connecting to the REDIS database
        self.r = redis.Redis(host="192.168.222.233", 
                password="redisRacs233", 
                port=6379, 
                decode_responses=True,
                #ssl=True,
               )
        
        # Testing connection
        try: 
            self.r.ping()
            self.redisConnectedFlag = True
        except:
            self.redisConnectedFlag = False
            #raise RuntimeError

    def run(self):
        while not self.terminateOperation:
            
            print("[ExternalTriggerThread] Trigger loop is running.")
            # Perform Acquisition
            ret = self.sdk.StartAcquisition()
            print("[ExternalTriggerThread] Function StartAcquisition returned {}".format(ret))

            ret = win32event.WaitForSingleObject(self.event, win32event.INFINITE)
            print("[ExternalTriggerThread] Function WaitForSingleObject returned {}".format(ret))

            if not self.terminateOperation:
                self.imageSize = self.xpixels
                (ret, arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, self.imageSize)
                print(f"[ExternalTriggerThread] Function GetImages16 returned {ret} first pixel = {arr[0]} size = {self.imageSize}")
                print(f"[ExternalTriggerThread] data : {arr}")
                ## TODO!!!

                if self.acquisitionSidebar.saveFolderLineEdit.text() != "":
                    directory = self.acquisitionSidebar.saveFolderLineEdit.text()
                else:
                    directory = "C:\\Users\\adato\\Programs\\ramanData" #+ "\\" # Replace with desired directory

                print(f"[ExternalTriggerThread] Saving into directory: {directory}")

                #filename = f"{directory}{time.strftime('TestSpectrum_%Y-%m-%d-%H-%M-%S')}.sif"
                
                # Attempting to retrieve file time stamp from the REDIS database
                if self.redisConnectedFlag:
                    if self.r.exists("TriggerTimeTag"): 
                        # If TriggerTimeTag exists, append it to the file name
                        self.triggerTimeTagKey = self.r.get("TriggerTimeTag")
                        self.triggerTime = json.loads(self.triggerTimeTagKey)
                        filename = f"{directory}/{datetime.now().strftime('Spectrum-%Y-%m-%d_%H-%M-%S-%f')}_triggered_{self.triggerTime}.csv.gz"
                        self.r.delete(self.triggerTimeTagKey)
                else:
                    filename = f"{directory}{datetime.now().strftime('Spectrum-%Y-%m-%d_%H-%M-%S-%f')}.csv.gz"

                df1 = pd.DataFrame({"Wavelengths": self.calibrationValues, "Values": arr})
                df1.to_csv(filename, compression="gzip", sep=",")
                #ret = self.sdk.SaveAsSif(filename)
                #print("Function SaveAsSif returned {}".format(ret))

                self.plotQ.put({"data": arr, 
                                "dataX": range(0, len(arr)), 
                                "dataY": arr, 
                                "title": f"Single track spectrum", 
                                "type": "spectrum",
                                "xpixels" : self.xpixels,
                                "ypixels" : self.ypixels})

        print("[ExternalTriggerThread] Run loop terminated!!")
            
        
    def stop(self):
        print("[ExternalTriggerThread] Thread run terminating.")
        self.terminateOperation = True
        win32event.ResetEvent(self.event)
        self.sleep(1)
        self.exit()


class loadAcquisitionSidebar(QWidget):
    def __init__(self, sdk, spc, plotQ):
        super().__init__()
        self.sdk = sdk
        self.spc = spc
        self.plotQ = plotQ
        #self.sdk = atmcd()  # Load the atmcd library
        self.codes = atmcd_codes
        self.errors = atmcd_errors
        print(f"[loadAcquisitionSidebar] sdk : {self.sdk}")
        loadUi("leftSidebarsUIs/acquisitionSidebar.ui", self)

        (ret, iSerialNumber) = self.sdk.GetCameraSerialNumber()
        print(f"[loadAcquisitionSidebar] GetCameraSerialNumber returned {ret} Serial No: {iSerialNumber}")
        
        ret = self.sdk.CoolerON()
        print("[loadAcquisitionSidebar] Function CoolerON returned {}".format(ret))
        
        self.setTemperatureFunction() 
        self.temperatureThread = TemperatureThread(self.sdk)
        self.temperatureThread.change_value.connect(self.updateTemperature)
        self.temperatureThread.start()
        
        # Establishing a thread for external trigger mode, but not starting it yet. 
        # It is only started upon selection of that option.
        self.externalTriggerThread = ExternalTrigger(sdk=self.sdk, spc=self.spc, plotQ=self.plotQ, acquisitionSidebar=self)
        self.externalTriggerThread.Priority(6)

        (ret, iSerialNumber) = self.sdk.GetCameraSerialNumber()
        if int(iSerialNumber) == 19302:
            # Nikon 1 camera is having troubles cooling down to -70°C so setting default to -60°C 
            # Otherwise it complains and beeps.
            print("[LoadAcquisitionSidebar] Setting default temperature to -60°C")
            self.setTemperature.setValue(-60) 

        # Updating cbox values when changed
        self.setTemperature.valueChanged.connect(self.setTemperatureFunction)
        self.acquisitionModeCBox.currentTextChanged.connect(self.setAcquisitionModeFunction) 
        self.readModeCBox.currentTextChanged.connect(self.setReadModeFunction)   
        self.triggerModeCBox.currentTextChanged.connect(self.setTriggerModeFunction)
        self.setAcquisitionModeFunction()
        self.setReadModeFunction()
        self.setTriggerModeFunction()

        # Disabling not-implemented options
        # Read mode Random Track
        self.readModeCBox.model().item(3).setEnabled(False)
        # Acquisition mode 
        # Accumulate
        self.acquisitionModeCBox.model().item(1).setEnabled(False)
        # Kinetic series
        self.acquisitionModeCBox.model().item(2).setEnabled(True)
        # Run til abort
        self.acquisitionModeCBox.model().item(3).setEnabled(False)
        # Fast kinetics
        self.acquisitionModeCBox.model().item(4).setEnabled(False)
        # Trigger Mode 
        # External
        self.triggerModeCBox.model().item(1).setEnabled(True)
        # External start
        self.triggerModeCBox.model().item(2).setEnabled(False)
        # External exposure
        self.triggerModeCBox.model().item(3).setEnabled(True)
        # External FVB EM
        self.triggerModeCBox.model().item(4).setEnabled(False)
        # Software trigger
        self.triggerModeCBox.model().item(5).setEnabled(False)
        # External charge shifting
        self.triggerModeCBox.model().item(6).setEnabled(False)

        # Updating Multitrack QSPinBoxes
        self.numberOfTracksValue.valueChanged.connect(self.setMultiTrack)
        self.heightValue.valueChanged.connect(self.setMultiTrack)
        self.offsetValue.valueChanged.connect(self.setMultiTrack)
        # Connecting multitrack help button with a callback
        self.multiTrackHelpBtn.clicked.connect(self.multiTrackHelp)
        
        # Updating values from Single Track QSpinBoxes
        self.singleTrackCentre.valueChanged.connect(self.setSingleTrack)
        self.singleTrackHeight.valueChanged.connect(self.setSingleTrack)
        # Connecting single track help button with a callback
        self.singleTrackHelpBtn.clicked.connect(self.singleTrackHelp)

        # Connecting trigger voltage spin box
        self.triggerVoltageSpinBox.valueChanged.connect(self.triggerVoltageSet)
        # Setting trigger voltage range
        ret, self.minVoltage, self.maxVoltage = self.sdk.GetTriggerLevelRange()
        print(f"[loadAcquisitionSidebar] GetTriggerVoltage range returned {ret}, minium: {self.minVoltage}, maximum {self.maxVoltage}")
        self.triggerVoltageSpinBox.setMaximum(float(self.maxVoltage))
        self.triggerVoltageSpinBox.setMinimum(float(self.minVoltage))

        # Connecting the trigger edge combo box
        self.triggerEdgeCBox.currentTextChanged.connect(self.triggerEdgeSet)

        # Connecting the setFastTriggerMode 
        self.setFastTriggerMode.clicked.connect(self.fastTriggerModeSet)

        # Connecting callback to save folder button
        self.saveFolderBtn.clicked.connect(self.findSaveFolder)
        # Last used folder.
        self.lastFolder = '.'
        self.saveFolder = self.saveFolderLineEdit.textChanged.connect(self.checkSaveFolder)


    def findSaveFolder(self):
        # Function to spawn a QFileDialogue to search for a folder to save data into.
        self.saveFolder = QFileDialog.getExistingDirectory(caption="Output data folder", directory=self.lastFolder)
        self.lastFolder = self.saveFolder

        # Update a folder line edit value 
        self.saveFolderLineEdit.setText(self.saveFolder)
        
        self.checkSaveFolder()

    def checkSaveFolder(self):
        self.saveFolder = self.saveFolderLineEdit.text()
        # Checking if folder exists
        if os.path.exists(self.saveFolder) or self.saveFolder == "":
            self.invalidFolderLabel.setText("")
        else:
            self.invalidFolderLabel.setText("<font color='#FF3333'><b>Invalid folder!</b></font>")
    
    def fastTriggerModeSet(self):
        if self.setFastTriggerMode.isChecked():
            ret = self.sdk.SetFastExtTrigger(1)
            print(f"[loadAcquisitionSidebar/fastTriggerModeSet] Trigger voltage returned {ret} fast external trigger enabled.")
        else:
            ret = self.sdk.SetFastExtTrigger(0)
            print(f"[loadAcquisitionSidebar/fastTriggerModeSet] Trigger voltage returned {ret} fast external trigger disaled.")

    def triggerVoltageSet(self):
        print(f"Attempting to set the trigger voltage to: {float(self.triggerVoltageSpinBox.value())}")
        ret = self.sdk.SetTriggerLevel(float(self.triggerVoltageSpinBox.value()))
        print(f"[loadAcquisitionSidebar/triggerVoltageSet] Trigger voltage returned {ret}, set to {float(self.triggerVoltageSpinBox.value())}")

    def triggerEdgeSet(self):
        selectedIndex = int(self.triggerEdgeCBox.currentIndex())
        ret = self.sdk.SetTriggerInvert(selectedIndex)
        print(f"[loadAcquisitionSidebar/triggerEdgeSet] Selected trigger edge returned {ret}, value {selectedIndex}.")

    def setSingleTrack(self):
        # Setting single track values
        ret = self.sdk.SetSingleTrack(centre=self.singleTrackCentre.value(), height=self.singleTrackHeight.value())
        print(f"[setSingleTrack] Returned {ret}")

        if ret == self.errors.Error_Codes.DRV_P1INVALID:
            # Center row invalid.
            self.singleTrackCentreLabel.setText("<font color='red'><b>Centre</b></font>")
        elif ret == self.errors.Error_Codes.DRV_P2INVALID:
            # Track height invalid.
            self.singleTrackHeightLabel.setText("<font color='red'><b>Height</b></font>")
        else:
            # Returning titles to normal
            self.singleTrackCentreLabel.setText("Centre")
            self.singleTrackHeightLabel.setText("Height")

    def setMultiTrack(self):
        # Setting multitrack values
        ret, bottom, gap =self.sdk.SetMultiTrack(number=self.numberOfTracksValue.value(), height=self.heightValue.value(), offset=self.offsetValue.value())
        self.bottomRowValue.setText(str(bottom))
        self.gapValue.setText(str(gap))
        print(f"[setMultiTrack] Returned {ret}")

        # Displaying invalid values.
        if ret == self.errors.Error_Codes.DRV_P1INVALID:
            # Number of tracks invalid.
            self.numberOfTracksLabel.setText("<font color='red'><b>Number of tracks</b></font>")
        elif ret == self.errors.Error_Codes.DRV_P2INVALID:
            # Track height invalid.
            self.heightLabel.setText("<font color='red'><b>Height</b></font>")
        elif ret == self.errors.Error_Codes.DRV_P3INVALID:
            # Offset invalid.
            self.heightLabel.setText("<font color='red'><b>Offset</b></font>")
        else:
            # Returning titles to normal
            self.numberOfTracksLabel.setText("Number of tracks")
            self.heightLabel.setText("Height")
            self.heightLabel.setText("Offset")

    def setTemperatureFunction(self):
        # Configure the acquisition
        setTemperature = int(f"{self.setTemperature.value():03d}")
        ret = self.sdk.SetTemperature(setTemperature)
        print(f"[setTemperatureFunction] Returned {ret} target temperature {setTemperature}")

    def updateTemperature(self, ret, temperature):
        #print(f"[updateTemperature] return value : {ret}")
        #print(f"Temperature stabilized code : {atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED}")
        #self.currentTemperature.setText(str(temperature) + " °C")
        if ret == atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
            #print("[updateTemperature] Temperature stabilized")
            self.currentTemperature.setText("<font color='green'><b>" + str(temperature) + " °C</b></font>")
        elif ret == atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
            self.currentTemperature.setText("<font color='orange'><b>" + str(temperature) + " °C</b></font>")
        else:
            self.currentTemperature.setText("<font color='red'><b>" + str(temperature) + " °C</b></font>")
        #print(f"[updateTemperature] Current temperature = {temperature} ")

    def setAcquisitionModeFunction(self):
        modes = {"Single scan" : self.codes.Acquisition_Mode.SINGLE_SCAN,
                 "Accumulate" : self.codes.Acquisition_Mode.ACCUMULATE,
                 "Kinetic series" : self.codes.Acquisition_Mode.KINETICS,
                 "Run til abort" : self.codes.Acquisition_Mode.RUN_TILL_ABORT,
                 "Fast kinetics" : self.codes.Acquisition_Mode.FAST_KINETICS}
        
        desiredMode = modes[self.acquisitionModeCBox.currentText()]
        print(f"[setAcquisitionModeFunction] Current acquisition mode : {desiredMode}")

        if self.acquisitionModeCBox.currentText() == "Kinetic series":
            self.kineticsAnimation()
        elif self.acquisitionModeCBox.currentText() == "Fast kinetics":
            self.fastKineticsAnimation()
        else:
            self.closeAllAcquisitionWindowsAnimation()

        if self.acquisitionModeCBox.currentText() == "Single scan":
            ret = self.sdk.SetAcquisitionMode(desiredMode)
            print("[setAcquisitionModeFunction] Function SetAcquisitionMode returned {} mode = Single Scan".format(ret))
        else:
            print(f"[setAcquisitionModeFunction] selected {self.acquisitionModeCBox.currentText()}, code {modes[self.acquisitionModeCBox.currentText()]}, but that is not yet implemented. Putting insted Single scan.")
            ret = self.sdk.SetAcquisitionMode(modes["Single scan"])
            print("[setReadModeFunction] returned {} mode = Image".format(ret))

    def setReadModeFunction(self):
        modes = {"Full vertical binning" : self.codes.Read_Mode.FULL_VERTICAL_BINNING,
                 "Single track" : self.codes.Read_Mode.SINGLE_TRACK,
                 "Multi track" : self.codes.Read_Mode.MULTI_TRACK,
                 "Random track" : self.codes.Read_Mode.RANDOM_TRACK,
                 "Image" : self.codes.Read_Mode.IMAGE}
        
        desiredMode = modes[self.readModeCBox.currentText()]

        if self.readModeCBox.currentText() == "Multi track":
            self.multitrackAnimation()
        elif self.readModeCBox.currentText() == "Single track":
            self.singleTrackAnimation()
        else:
            self.closeAllWindowsAnimation()
            

        print(f"[setReadModeFunction] Current trigger mode : {desiredMode}")
        
        ret = self.sdk.SetReadMode(desiredMode)
        print("[setReadModeFunction] returned {} mode = Image".format(ret))

    
    def setTriggerModeFunction(self):
        modes = {"Internal" : self.codes.Trigger_Mode.INTERNAL,
                 "External" : self.codes.Trigger_Mode.EXTERNAL,
                 "External start" : self.codes.Trigger_Mode.EXTERNAL_START,
                 "Externally driven exposure" : self.codes.Trigger_Mode.EXTERNAL_EXPOSURE_BULB,
                 "External FVB EM" : self.codes.Trigger_Mode.EXTERNAL_FVB_EM,
                 "Software trigger" : self.codes.Trigger_Mode.SOFTWARE_TRIGGER,
                 "External charge shifting" : self.codes.Trigger_Mode.EXTERNAL_CHARGE_SHIFTING}
        
        currentMode = modes[self.triggerModeCBox.currentText()]
        print(f"[setTriggerModeFunction] Current trigger mode : {currentMode}")
        """"
        Setting trigger mode. All options except INTERNAL are disabled for now. Delete the if/else structure to enable everything. 
        """
        if self.triggerModeCBox.currentText() == "Internal":
            ret = self.sdk.SetTriggerMode(modes[self.triggerModeCBox.currentText()])
            print("[setTriggerModeFunction] Function SetTriggerMode returned {} mode = Internal".format(ret))
            if self.externalTriggerThread.isRunning():
                print("[setTriggerModeFunction] External trigger thread is running. Exiting.")
                self.externalTriggerThread.stop()
            self.triggerAnimation()

            
        elif self.triggerModeCBox.currentText() == "External":
            ret = self.sdk.SetTriggerMode(modes[self.triggerModeCBox.currentText()])
            print("[setTriggerModeFunction] Function SetTriggerMode returned {} mode = External".format(ret))
            if not self.externalTriggerThread.isRunning():
                self.externalTriggerThread.start()
                print("[setTriggerModeFunction] Initializing external trigger thread.")
            self.triggerAnimation()
        elif self.triggerModeCBox.currentText() == "Externally driven exposure":
            ret = self.sdk.SetTriggerMode(modes[self.triggerModeCBox.currentText()])
            print("[setTriggerModeFunction] Function SetTriggerMode returned {} mode = Externally driven exposure".format(ret))
            self.triggerAnimation()
        else:
            print(f"[setTriggerModeFunction] selected {self.triggerModeCBox.currentText()}, code {modes[self.triggerModeCBox.currentText()]}, but that is not yet implemented. Putting insted Internal.")
            ret = self.sdk.SetTriggerMode(modes["Internal"])
            print("[setTriggerModeFunction] returned {} mode = Internal".format(ret))
            self.triggerAnimation()

    def fastKineticsAnimation(self):
        #print(f"[multitrackAnimation] multiTrackFrame maximumSize: {self.multitrackFrame.maximumSize()}.")
        #print(f"[multitrackAnimation] multiTrackFrame maximumSize width: {self.multitrackFrame.maximumHeight()}.")
        if self.acquisitionModeCBox.currentText() == "Fast kinetics":
            print("Fast kinetics selected")
            duration = 500
            # Opening multitrack animation
            self.fastKineticsAnimationSequence = QPropertyAnimation(self.fastKineticsFrame, b"maximumSize")
            self.fastKineticsAnimationSequence.setDuration(duration)
            self.fastKineticsAnimationSequence.setStartValue(self.fastKineticsFrame.maximumSize())
            self.fastKineticsAnimationSequence.setEndValue(QSize(1000,1000))
            if self.kineticsFrame.maximumHeight() != 0:
                self.kineticsFrame.setMaximumHeight(0)
                #self.singleTrackAnimSequence = QPropertyAnimation(self.singleTrackFrame, b"maximumSize")
                #self.singleTrackAnimSequence.setDuration(duration)
                #self.singleTrackAnimSequence.setStartValue(self.singleTrackFrame.maximumSize())
                #self.singleTrackAnimSequence.setEndValue(QSize(1000,0))
                #self.animationGroup.addAnimation(self.singleTrackAnimSequence)
            #self.animationMenu.start()
            self.fastKineticsAnimationSequence.start()
        else:
            print("Something else selected")
            duration = 250
            self.animationMenu = QPropertyAnimation(self.fastKineticsFrame, b"maximumSize")
            self.animationMenu.setDuration(duration)
            self.animationMenu.setStartValue(self.fastKineticsFrame.maximumSize())
            self.animationMenu.setEndValue(QSize(1000,0))
            self.animationMenu.start()

    def kineticsAnimation(self):
        #print(f"[multitrackAnimation] multiTrackFrame maximumSize: {self.multitrackFrame.maximumSize()}.")
        #print(f"[multitrackAnimation] multiTrackFrame maximumSize width: {self.multitrackFrame.maximumHeight()}.")
        if self.acquisitionModeCBox.currentText() == "Kinetic series":
            print("Kinetic series selected")
            duration = 500
            # Opening multitrack animation
            self.fastKineticsAnimationSequence = QPropertyAnimation(self.kineticsFrame, b"maximumSize")
            self.fastKineticsAnimationSequence.setDuration(duration)
            self.fastKineticsAnimationSequence.setStartValue(self.kineticsFrame.maximumSize())
            self.fastKineticsAnimationSequence.setEndValue(QSize(1000,1000))
            if self.fastKineticsFrame.maximumHeight() != 0:
                self.fastKineticsFrame.setMaximumHeight(0)
                #self.singleTrackAnimSequence = QPropertyAnimation(self.singleTrackFrame, b"maximumSize")
                #self.singleTrackAnimSequence.setDuration(duration)
                #self.singleTrackAnimSequence.setStartValue(self.singleTrackFrame.maximumSize())
                #self.singleTrackAnimSequence.setEndValue(QSize(1000,0))
                #self.animationGroup.addAnimation(self.singleTrackAnimSequence)
            #self.animationMenu.start()
            self.fastKineticsAnimationSequence.start()
        else:
            print("Something else selected")
            duration = 250
            self.animationMenu = QPropertyAnimation(self.kineticsFrame, b"maximumSize")
            self.animationMenu.setDuration(duration)
            self.animationMenu.setStartValue(self.kineticsFrame.maximumSize())
            self.animationMenu.setEndValue(QSize(1000,0))
            self.animationMenu.start()
    
    def triggerAnimation(self):
        if self.triggerModeCBox.currentText() == "External":
            print("[loadAcquisitionSidebar/triggerAnimation] External trigger selected")
            duration = 500
            # Opening multitrack animation
            self.triggerAnimationSequence = QPropertyAnimation(self.externalTriggerFrame, b"maximumSize")
            self.triggerAnimationSequence.setDuration(duration)
            self.triggerAnimationSequence.setStartValue(self.externalTriggerFrame.maximumSize())
            self.triggerAnimationSequence.setEndValue(QSize(1000,1000))
            if self.externalTriggerFrame.maximumHeight() != 0:
                self.externalTriggerFrame.setMaximumHeight(0)
            self.triggerAnimationSequence.start()
            duration = 500
            # Opening multitrack animation
            self.triggerEdgeAnimationSequence = QPropertyAnimation(self.trigerEdgeFrame, b"maximumSize")
            self.triggerEdgeAnimationSequence.setDuration(duration)
            self.triggerEdgeAnimationSequence.setStartValue(self.trigerEdgeFrame.maximumSize())
            self.triggerEdgeAnimationSequence.setEndValue(QSize(1000,1000))
            if self.trigerEdgeFrame.maximumHeight() != 0:
                self.trigerEdgeFrame.setMaximumHeight(0)
            self.triggerEdgeAnimationSequence.start()

        elif self.triggerModeCBox.currentText() == "Externally driven exposure":
            print("[loadAcquisitionSidebar/triggerAnimation] External trigger selected")
            duration = 500
            # Opening multitrack animation
            self.triggerAnimationSequence = QPropertyAnimation(self.externalTriggerFrame, b"maximumSize")
            self.triggerAnimationSequence.setDuration(duration)
            self.triggerAnimationSequence.setStartValue(self.externalTriggerFrame.maximumSize())
            self.triggerAnimationSequence.setEndValue(QSize(1000,1000))
            if self.externalTriggerFrame.maximumHeight() != 0:
                self.externalTriggerFrame.setMaximumHeight(0)
            self.triggerAnimationSequence.start()

            self.closingTriggerEdge = QPropertyAnimation(self.trigerEdgeFrame, b"maximumSize")
            self.closingTriggerEdge.setDuration(duration)
            self.closingTriggerEdge.setStartValue(self.trigerEdgeFrame.maximumSize())
            self.closingTriggerEdge.setEndValue(QSize(1000,0))
            self.closingTriggerEdge.start()
        else:
            print("Something else selected")
            duration = 250
            self.animationMenu1 = QPropertyAnimation(self.trigerEdgeFrame, b"maximumSize")
            self.animationMenu1.setDuration(duration)
            self.animationMenu1.setStartValue(self.trigerEdgeFrame.maximumSize())
            self.animationMenu1.setEndValue(QSize(1000,0))
            self.animationMenu1.start()

            self.animationMenu2 = QPropertyAnimation(self.externalTriggerFrame, b"maximumSize")
            self.animationMenu2.setDuration(duration)
            self.animationMenu2.setStartValue(self.externalTriggerFrame.maximumSize())
            self.animationMenu2.setEndValue(QSize(1000,0))
            self.animationMenu2.start()

    def closeAllAcquisitionWindowsAnimation(self):
        duration = 500
        self.animationGroup = QParallelAnimationGroup()
        if self.fastKineticsFrame.maximumHeight() != 0:
            self.fastKineticsAnimSequence = QPropertyAnimation(self.fastKineticsFrame, b"maximumSize")
            self.fastKineticsAnimSequence.setDuration(duration)
            self.fastKineticsAnimSequence.setStartValue(self.fastKineticsFrame.maximumSize())
            self.fastKineticsAnimSequence.setEndValue(QSize(1000,0))
            self.animationGroup.addAnimation(self.fastKineticsAnimSequence)
        elif self.kineticsFrame.maximumHeight() != 0:
            self.kineticsAnimSequence = QPropertyAnimation(self.kineticsFrame, b"maximumSize")
            self.kineticsAnimSequence.setDuration(duration)
            self.kineticsAnimSequence.setStartValue(self.kineticsFrame.maximumSize())
            self.kineticsAnimSequence.setEndValue(QSize(1000,0))
            self.animationGroup.addAnimation(self.kineticsAnimSequence)
        else:
            print("Nothing selected")

        self.animationGroup.start()


    def multitrackAnimation(self):
        #print(f"[multitrackAnimation] multiTrackFrame maximumSize: {self.multitrackFrame.maximumSize()}.")
        #print(f"[multitrackAnimation] multiTrackFrame maximumSize width: {self.multitrackFrame.maximumHeight()}.")
        if self.readModeCBox.currentText() == "Multi track":
            print("Multitrack selected")
            duration = 500
            # Opening multitrack animation
            self.multiTrackAnimSequence = QPropertyAnimation(self.multitrackFrame, b"maximumSize")
            self.multiTrackAnimSequence.setDuration(duration)
            self.multiTrackAnimSequence.setStartValue(self.multitrackFrame.maximumSize())
            self.multiTrackAnimSequence.setEndValue(QSize(1000,1000))
            if self.singleTrackFrame.maximumHeight() != 0:
                self.singleTrackFrame.setMaximumHeight(0)
                #self.singleTrackAnimSequence = QPropertyAnimation(self.singleTrackFrame, b"maximumSize")
                #self.singleTrackAnimSequence.setDuration(duration)
                #self.singleTrackAnimSequence.setStartValue(self.singleTrackFrame.maximumSize())
                #self.singleTrackAnimSequence.setEndValue(QSize(1000,0))
                #self.animationGroup.addAnimation(self.singleTrackAnimSequence)
            #self.animationMenu.start()
            self.multiTrackAnimSequence.start()
        else:
            print("Something else selected")
            duration = 250
            self.animationMenu = QPropertyAnimation(self.multitrackFrame, b"maximumSize")
            self.animationMenu.setDuration(duration)
            self.animationMenu.setStartValue(self.multitrackFrame.maximumSize())
            self.animationMenu.setEndValue(QSize(1000,0))
            self.animationMenu.start()

    def singleTrackAnimation(self):
        print(f"[singleTrackAnimation] singleTrackFrame maximumSize: {self.singleTrackFrame.maximumSize()}.")
        duration = 500
        if self.readModeCBox.currentText() == "Single track":
            self.animationGroup = QParallelAnimationGroup()
            self.singleTrackAnimaSequence = QPropertyAnimation(self.singleTrackFrame, b"maximumSize")
            self.singleTrackAnimaSequence.setDuration(duration)
            self.singleTrackAnimaSequence.setStartValue(self.singleTrackFrame.maximumSize())
            self.singleTrackAnimaSequence.setEndValue(QSize(1000,1000))
            self.animationGroup.addAnimation(self.singleTrackAnimaSequence)
            if self.multitrackFrame.maximumHeight() != 0:
                self.multitrackFrame.setMaximumHeight(0)
                #self.multiTrackAnimSequence = QPropertyAnimation(self.multitrackFrame, b"maximumSize")
                #self.multiTrackAnimSequence.setDuration(duration)
                #self.multiTrackAnimSequence.setStartValue(self.multitrackFrame.maximumSize())
                #self.multiTrackAnimSequence.setEndValue(QSize(1000,0))
                #self.animationGroup.addAnimation(self.multiTrackAnimSequence)
            self.animationGroup.start()
        else:
            self.singleTrackAnimaSequence = QPropertyAnimation(self.singleTrackFrame, b"maximumSize")
            self.singleTrackAnimaSequence.setDuration(duration)
            self.singleTrackAnimaSequence.setStartValue(self.singleTrackFrame.maximumSize())
            self.singleTrackAnimaSequence.setEndValue(QSize(1000,0))
            self.singleTrackAnimaSequence.start()

    def closeAllWindowsAnimation(self):
        duration = 500
        self.animationGroup = QParallelAnimationGroup()
        if self.multitrackFrame.maximumHeight() != 0:
            self.multiTrackAnimSequence = QPropertyAnimation(self.multitrackFrame, b"maximumSize")
            self.multiTrackAnimSequence.setDuration(duration)
            self.multiTrackAnimSequence.setStartValue(self.multitrackFrame.maximumSize())
            self.multiTrackAnimSequence.setEndValue(QSize(1000,0))
            self.animationGroup.addAnimation(self.multiTrackAnimSequence)
        elif self.singleTrackFrame.maximumHeight() != 0:
            self.singleTrackAnimSequence = QPropertyAnimation(self.singleTrackFrame, b"maximumSize")
            self.singleTrackAnimSequence.setDuration(duration)
            self.singleTrackAnimSequence.setStartValue(self.singleTrackFrame.maximumSize())
            self.singleTrackAnimSequence.setEndValue(QSize(1000,0))
            self.animationGroup.addAnimation(self.singleTrackAnimSequence)
        else:
            print("Nothing selected")

        self.animationGroup.start()

    ############################################################################
    # Help functions
    ############################################################################

    def multiTrackHelp(self):
        msg = QMessageBox()
        msg.setWindowTitle("Multi track help")
        msg.setText("""
        This field will set the multi-Track parameters. The tracks are automatically 
        spread evenly over the detector. The first pixels row of the first track is 
        returned as "bottom". The number of rows between each track is returned 
        via gap. This parameter can also be 0.

        If any of the input values are invalid, the appropriate title will be 
        highlighted. 
        """)

        msg.setIcon(QMessageBox.information)

        x = msg.exec_()

    def singleTrackHelp(self):
        msg = QMessageBox()
        msg.setWindowTitle("Single track help")
        msg.setText("""
        This field will set the single track parameters. Centre denotes the centre 
        row of the measured track on the detector and height refers to the height
        or width of the measured track.

        If any of the input values are invalid, the appropriate title will be 
        highlighted. 
        """)

        msg.setIcon(QMessageBox.information)

        x = msg.exec_()
