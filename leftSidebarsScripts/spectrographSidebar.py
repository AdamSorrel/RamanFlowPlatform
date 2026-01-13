import sys, os, time

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QWidget
from PyQt6.uic import loadUi
# Spectrograph libraries (grating, filters, etc.)
from pyAndorSpectrograph.spectrograph import ATSpectrograph

class loadSpectrographSidebar(QWidget):
    def __init__(self, spc):
        super().__init__()
        self.spc = spc
        loadUi("leftSidebarsUIs/spectrographSidebar.ui", self)

        # This really supports only one device being connected at the time. 
        # More can be supported by implementing counter/selector changing the index variable  
        index = 0
        (ret, serial) = self.spc.GetSerialNumber(index, 64)
        self.serialNumber.setText(f"{serial}")
        print("[loadSpectrographSidebar] Function GetSerialNumber returned {}".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
        
        (ret, FocalLength, AngularDeviation, FocalTilt) = self.spc.EepromGetOpticalParams(index)
        print("[loadSpectrographSidebar] Function EepromGetOpticalParams {}".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
        self.focalLength.setText(f"{FocalLength:.3f}")
        self.angularDeviation.setText(f"{AngularDeviation:.3f}")
        self.focalTilt.setText(f"{FocalTilt:.3f}")

        """
        Grating setup
        1. Checking if grating is present.
        2. If grating is present, checking if turret is present.
        3. Checking number of available gratings.
        4. Populating grating comboBox with available gratings.
        5. Checking current grating.
        6. Populating UI grating informations with data about current grating.
        """
        (shm, present) = self.spc.IsGratingPresent(0)
        print(f"[loadSpectrographSidebar] Function GratingIsPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        if present > 0 :
            print("Grating is present.")
        print("[loadSpectrographSidebar]\tTurret IS present")
        
        (ret, turret) = self.spc.GetTurret(0)
        print("[loadSpectrographSidebar] Function GetTurret returned {}".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
        print("[loadSpectrographSidebar]\tTurret: {}".format(turret))

        (ret, gratings) = self.spc.GetNumberGratings(0)
        print(f"[loadSpectrographSidebar] Function GetNumberGratings returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")
        print(f"[loadSpectrographSidebar] Function GetNumberGratings codes {ret}")
        print(f"[loadSpectrographSidebar]\tNumber of gratings: {gratings}") 

        # Retrieving grating information
        for gratingNum in range(1,gratings+1):
            (ret, lines, blaze, home, offset) = self.spc.GetGratingInfo(0, gratingNum, 64)

            self.gratingCBox.addItem(f"{gratingNum} - {lines:.0f} lines/mm")
            """
            print("Function GetGratingInfo returned {} ".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
            print(f"\tGrating no {gratingNum}")
            print(f"\tLines/mm: {lines}")           
            print(f"\tBlaze: {blaze}")
            print(f"\tHome: {home}")
            print(f"\tOffset: {offset}")
            """
    
        (ret, grat) = self.spc.GetGrating(0)
        print(f"[loadSpectrographSidebar]\tFunction GetGrating returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")
        print(f"[loadSpectrographSidebar]\tGrating no: {grat}")
        # Setting grating index combo box to the current grating.
        self.gratingCBox.setCurrentIndex(grat-1)
        try:
            self.setGrating()
        except:
            print("[loadSpectrographSidebar] Grating not available.")
        # Setting current grating comboBox value
        self.gratingCBox.setCurrentIndex(grat-1)
        # Linking callback function to updte UI grating info whenever grating comboBox is changed.
        self.gratingCBox.currentTextChanged.connect(self.setGrating)
        
        # Getting current detector offset

        """
        Description:
            Sets the detector offset. Use this function if the system has 4 ports and a detector offset value of a specific entrance and exit port combination is required.
            DIRECT, DIRECT = 0, 0
            DIRECT, SIDE = 0, 1
            SIDE, DIRECT = 1, 0
            SIDE, SIDE = 1, 1
        """
        (ret, offset) = spc.GetDetectorOffset(0, entrancePort=1, exitPort=0)
        print("[loadSpectrographSidebar] Function GetDetectorOffset returned {}".format(spc.GetFunctionReturnDescription(ret, 64)[1]))
        print("[loadSpectrographSidebar] \tDetector grating offset {}".format(offset))
        self.detectorOffsetValue.setText(str(offset))
        self.detectorOffsetValue.returnPressed.connect(self.setDetectorOffset)
        
        # Getting current grating offset
        (ret, offset) = spc.GetGratingOffset(device=0, Grating=grat)
        print("[loadSpectrographSidebar] Function GetGratingOffset returned {}".format(spc.GetFunctionReturnDescription(ret, 64)[1]))
        print("[loadSpectrographSidebar] \tGrating offset {}".format(offset))
        # Updating current grating offset
        self.gratingOffset.setText(str(offset))
        # Linking a callback function which is activated upon pressing enter
        self.gratingOffset.returnPressed.connect(self.setGratingOffset)

        # Linking a callback function to the Filter combo box
        self.desiredFilterCBox.currentTextChanged.connect(self.setFilter)

        """
        Wavelength setup
        """
        (shm, present) = spc.IsWavelengthPresent(0)
        print(f"[loadSpectrographSidebar] Function IsWavelengthPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")
        if present > 0:
            (shm, wave) = spc.GetWavelength(0)
            print(f"[loadSpectrographSidebar] Function GetWavelength returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Wavelength: {wave}")
            self.wavelengthSetValue.setText(f"{wave: .1f}")

            # Retrieving current grating (0 -> number of machine)
            (ret, grat) = self.spc.GetGrating(0)

            (shm, min, max) = self.spc.GetWavelengthLimits(0, grat)
            print(f"[loadSpectrographSidebar] Function GetWavelengthLimits returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Wavelength Min: {min} Wavelength Max: {max}")

            self.wavelengthMinimum.setText(str(min)+" nm")
            self.wavelengthMaximum.setText(str(max)+" nm")

            # Checking if wavelength is at zero order
            #atZeroOrder - pointer to flag:: 0 - wavelength is NOT at zero order / 1 - wavelength IS at zero order
            ret, atZeroOrder = self.spc.AtZeroOrder(device=0)
            print(f"[loadSpectrographSidebar] Function AtZeroOrder returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")
            atZeroOrder = 1
            if atZeroOrder == 1:
                print(f"[loadSpectrographSidebar] Wavelength IS at zero order.")
                self.zeroOrderValue.setText("True")
            else:
                print(f"[loadSpectrographSidebar] Wavelength is NOT at zero order.")
                self.zeroOrderValue.setText("False")

        # Linking a callback function which is activated upon pressing enter
        self.wavelengthSetValue.returnPressed.connect(self.setWavelength)

        """
        Slit setup
        
        slit - index of the slit, must be one of the following, INPUT_SIDE / INPUT_DIRECT / OUTPUT_SIDE / OUTPUT_DIRECT
        """ 
        (shm, present) = self.spc.IsSlitPresent(0, 1)
        print(f"[loadSpectrographSidebar] Function IsSlitPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")
        if present > 0:
            ret, width = self.spc.GetSlitWidth(0, 1)
            # Reading current slit width and setting that as a UI presented value
            self.slitWidthValue.setText(str(width))

        # Linking a callback function with is activated upon pressing enter
        self.slitWidthValue.returnPressed.connect(self.setSlitWidth)

        """
        Rest of the checks
        """

        (shm, present) = spc.IsAccessoryPresent(0)
        print(f"[loadSpectrographSidebar] Function IsAccessoryPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, present) = spc.IsSlitPresent(0, 1)
        print(f"[loadSpectrographSidebar] Function IsSlitPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, present) = spc.IsFilterPresent(0)
        print(f"[loadSpectrographSidebar] Function IsFilterPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, present) = spc.IsFlipperMirrorPresent(0, 1)
        print(f"[loadSpectrographSidebar] Function IsFlipperMirrorPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, present) = spc.IsFocusMirrorPresent(0)
        print(f"[loadSpectrographSidebar] Function IsFocusMirrorPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, present) = spc.IsIrisPresent(0, 1)
        print(f"[loadSpectrographSidebar] Function IsIrisPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, info) = spc.GetFilterInfo(0, 1, 64)
        print(f"[loadSpectrographSidebar] Function GetFilterInfo returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Info: {info}")

        self.currentFilterValue.setText(str(info))

        (shm, info) = spc.IsShutterModePossible(0, 1)
        print(f"[loadSpectrographSidebar] Function IsShutterModePossible returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Info: {info}")

        (shm, present) = spc.IsShutterPresent(0)
        print(f"[loadSpectrographSidebar] Function IsShutterPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")

        (shm, present) = spc.IsSlitPresent(0, 3)
        print(f"[loadSpectrographSidebar] Function IsSlitPresent returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} present: {present}")
        
        (shm, pos) = spc.GetFlipperMirrorMaxPosition(0, 1)
        print(f"[loadSpectrographSidebar] Function GetFlipperMirrorMaxPosition returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Pos: {pos}")

    def setFilter(self):
        desiredFilter = int(self.desiredFilterCBox.currentText())

        self.spc.SetFilter(0, desiredFilter)

        (shm, filter) = self.spc.GetFilter(0)
        print(f"[loadSpectrographSidebar/setFilter] Function GetFilter returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Filter: {filter}")

        (shm, info) = self.spc.GetFilterInfo(0, filter, 64)
        print(f"[loadSpectrographSidebar/setFilter] Function GetFilterInfo returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Filter info: {info}")

        self.currentFilterValue.setText(str(info))

    def setSlitWidth(self):
        desiredSlitWidth = int(self.slitWidthValue.text())
        print(f"[setSlitWidth] attempting to set slit width to : {desiredSlitWidth}")

        ret = self.spc.SetSlitWidth(0, 1, desiredSlitWidth)
        print(f"[setSlitWidth] Function SetSlitWidth returned : {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")


    def setDetectorOffset(self):
        desiredOffset = int(self.detectorOffsetValue.text())

        print(f"[setDetectorOffset] attempting to set detector offset to : {desiredOffset}")
        ret = self.spc.SetDetectorOffset(device=0, offset=desiredOffset, entrancePort=1, exitPort=0)
        print(f"[setDetectorOffset] SetDetectorOffset returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")
        # Getting current detector offset to check
        (ret, offset) = self.spc.GetDetectorOffset(device=0, entrancePort=1, exitPort=0)
        print(f"[setDetectorOffset] GetDetectorOffset returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}; Current detector offset: {offset}")

    def setGratingOffset(self):
        desiredOffset = int(self.gratingOffset.text())

        print(f"[setGratingOffset] attempting to set grating offset to : {desiredOffset}")
        (ret, grat) = self.spc.GetGrating(0)
        print(f"[setGratingOffset] GetGrating returned: {self.spc.GetFunctionReturnDescription(ret, 64)[1]}; Grating no: {grat}")
        ret = self.spc.SetGratingOffset(device=0, Grating=grat, offset=desiredOffset)
        print(f"[setGratingOffset] SetGratingOffset returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")
        # Getting current grating offset to check
        (ret, offset) = self.spc.GetGratingOffset(device=0, Grating=grat)
        print(f"[setGratingOffset] GetGratingOffset returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}; Current grating offset: {offset}")

    def setGrating(self):
        gratingText = self.gratingCBox.currentText()

        gratingNumber = gratingText.split(" - ")[0]
        # Callback function for the gratingCBox
        print(f"[setGrating] Setting grating to: {gratingNumber}. ")
        # SetGrating(self, device, grating)
        if gratingNumber != "":
            shm = self.spc.SetGrating(0, int(gratingNumber))
            print(f"[setGrating] Function SetGrating returned {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")

        # Retrieving current grating (0 -> number of machine)
        (ret, grat) = self.spc.GetGrating(0)
        print(f"[setGrating] Function GetGrating returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")
        print(f"[setGrating] \tGrating no: {grat}")
        (ret, lines, blaze, home, offset) = self.spc.GetGratingInfo(0, grat, 64)
        print(f"[setGrating] Function GetGratingInfo returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")

        # Setting grating labels
        self.linesPerMM.setText(f"{lines:.0f}")
        self.blaze.setText(str(blaze))
        self.gratingHome.setText(str(home))

    def setWavelength(self):
        desiredWavelength = float(self.wavelengthSetValue.text())

        print(f"[spectrographSidebar/setWavelength] Setting wavelength to {desiredWavelength} ###################################")

        shm = self.spc.SetWavelength(0, desiredWavelength)
        print(f"[setWavelength] Function SetWavelength returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")

        # Retrieving current grating (0 -> number of machine)
        (ret, grat) = self.spc.GetGrating(0)

        (shm, min, max) = self.spc.GetWavelengthLimits(0, grat)
        print(f"[setWavelength] Function GetWavelengthLimits returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Wavelength Min: {min} Wavelength Max: {max}")

        self.wavelengthMinimum.setText(str(min)+" nm")
        self.wavelengthMaximum.setText(str(max)+" nm")

        # Checking if wavelength is at zero order
        #atZeroOrder - pointer to flag:: 0 - wavelength is NOT at zero order / 1 - wavelength IS at zero order
        ret, atZeroOrder = self.spc.AtZeroOrder(device=0)
        print(f"[setWavelength] Function AtZeroOrder returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")
        print(f"[setWavelength] Function AtZeroOrder returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")
        if atZeroOrder == 1:
            #print(f"[setWavelength] Wavelength IS at zero order.")
            self.zeroOrderValue.setText("True")
        else:
            #print(f"[setWavelength] Wavelength is NOT at zero order.")
            self.zeroOrderValue.setText("False")
        
