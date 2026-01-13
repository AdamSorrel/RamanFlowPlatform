import sys, os, time

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QWidget
from PyQt6.uic import loadUi
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

class loadDetectorSidebar(QWidget):
    def __init__(self, sdk):
        super().__init__()
        self.sdk = sdk
        #self.sdk = atmcd()  # Load the atmcd library
        self.codes = atmcd_codes
        print(f"[detectorSidebar] sdk : {self.sdk}")
        loadUi("leftSidebarsUIs/detectorSidebar.ui", self)

        # Setting exposure values
        (ret, fminExposure, fAccumulate, fKinetic) = self.sdk.GetAcquisitionTimings()
        print(f"[loadAcquisitionSidebar] Function GetAcquisitionTimings returned {ret} exposure = {fminExposure} accumulate = {fAccumulate} kinetic = {fKinetic}")
        self.exposureTimingValue.setText(f"{fminExposure} s")
        self.accumulateTimingValue.setText(f"{fAccumulate} s")
        self.kineticTimingValue.setText(f"{fKinetic} s")

        # Readout rates
        VSSpeeds = []

        self.getAmplifiers()
        # Try/except catches errors when trying to set non-existent values while not connected to the detector
        # TODO: This should be dealt with using an if statement
        try:
            self.setAmplifier()
        except:
            print(f"[loadDetectorSidebar] Function setAmplifier failed.")

        # Sets also 
        self.getADChannels()
        # Try/except catches errors when trying to set non-existent values while not connected to the detector
        try:
            self.setADChannel()
        except:
            print(f"[loadDetectorSidebar] Function setADChannel failed.")

        # Get current channel
        currentChannel = self.ADChannelsCBox.currentText()
        # Get horizontal shift speedss
        try:
            self.getHSSpeeds(int(currentChannel))
        except:
            print(f"[loadDetectorSidebar] Function getHSSpeeds failed.")
        # Get vertical shift speedss
        self.getVSSpeeds()
        # Amplifiers
        self.getAmplifiers()
        # Try/except catches errors when trying to set non-existent values while not connected to the detector
        try:
            self.setAmplifier()
        except:
            print(f"[loadDetectorSidebar] Function setAmplifier failed.")
        # Preamp gains
        self.getPreampGains()
        # Cosmic ray filter
        self.getCosmicRayFilterStatus()
        
        
        # Connecting callbacks of comboboxes
        self.ADChannelsCBox.currentTextChanged.connect(self.setADChannel)
        self.horizontalCBox.currentTextChanged.connect(self.setHSSpeed)
        self.verticalCBox.currentTextChanged.connect(self.setVSSpeeds)
        self.preampGainsCBox.currentTextChanged.connect(self.setPreampGain)
        self.cosmicRayFilter.toggled.connect(self.setCosmicRayFilter)

    def getADChannels(self):
            HSSpeeds = []
            (ret, ADchannel) = self.sdk.GetNumberADChannels()
            print("[loadDetectorSidebar] Function GetNumberADChannels returned {} number of available channels {}".format(ret, ADchannel))
            for channel in range(0, ADchannel):
                # Adding channels into the UI CBox 
                self.ADChannelsCBox.addItem(f"{channel}")
                (ret, speed) = self.sdk.GetNumberHSSpeeds(channel, 0)
                print("[loadDetectorSidebar]\tFunction GetNumberHSSpeeds {} number of available speeds {}".format(ret, speed))
                for x in range(0, speed):
                    (ret, speed) = self.sdk.GetHSSpeed(channel, 0, x)
                    HSSpeeds.append(speed)
            print("[loadDetectorSidebar]\t\tAvailable HSSpeeds in MHz {} ".format(HSSpeeds))

    def setADChannel(self):
        desiredChannel = self.ADChannelsCBox.currentText()
        print(f"[setADChannel] Attempting to set {desiredChannel} as AD channel.")     
        ret = self.sdk.SetADChannel(int(desiredChannel))
        print(f"[setADChannel] Function returned {ret}")
        # Updating HS speeds
        self.getHSSpeeds(int(desiredChannel))

        self.updateAcquisitionTiming()

    def getHSSpeeds(self, channel):
        (ret, speed) = self.sdk.GetNumberHSSpeeds(channel, 0)
        print("[getHSSpeeds]\tFunction GetNumberHSSpeeds {} number of available speeds {}".format(ret, speed))
        # Clearing old values from combo box before adding new ones
        self.horizontalCBox.clear()
        for x in range(0, speed):
            (ret, speed) = self.sdk.GetHSSpeed(channel, 0, x)
            self.horizontalCBox.addItem(f"{speed:.2f} MHz")

    def setHSSpeed(self, channel):
        desiredHSSpeed = self.horizontalCBox.currentText() 
        desiredHSSpeedIndex = self.horizontalCBox.currentIndex() 
        currentAMP = self.amplifierModesCBox.currentText()
        currentAMPindex = self.amplifierModesCBox.currentIndex() 
        print(f"[setHSSpeeds] Attempting to set {desiredHSSpeed} index:{desiredHSSpeedIndex} as horizontal shift speed on amplifier {currentAMP} index:{currentAMPindex}")
        ret = self.sdk.SetHSSpeed(typ=currentAMPindex, index=desiredHSSpeedIndex)
        print(f"[setHSSpeeds] returned {ret}.")
        # Retrieving fastest recommneded VSSpeeds to publish them in the UI
        # Returns the fastest speed which does not require the Vertical Clock Voltage to be adjusted.
        (ret, index, speed) = self.sdk.GetFastestRecommendedVSSpeed()
        print("[setVSSpeeds] Recommended VSSpeed {} index {}".format(speed, index))
        self.recommendedValue.setText(f"{speed:.2f} μs/pixel")

        self.updateAcquisitionTiming()
    
    def getVSSpeeds(self):
        VSSpeeds = []
        (ret, speed) = self.sdk.GetNumberVSSpeeds()
        print("[getVSSpeeds]\t\tFunction GetNumberVSSpeeds {} number of available speeds {}".format(ret, speed))
        self.verticalCBox.clear()
        for i, x in enumerate(range(0, speed)):
            (ret, speed) = self.sdk.GetVSSpeed(x)
            self.verticalCBox.addItem(f"{i} - {speed:.2f} μs" )
            VSSpeeds.append(speed)
        print("[getVSSpeeds]Available VSSpeeds in us {}".format(VSSpeeds))
        # Retrieving fastest recommneded VSSpeeds to publish them in the UI
        # Returns the fastest speed which does not require the Vertical Clock Voltage to be adjusted.
        (ret, index, speed) = self.sdk.GetFastestRecommendedVSSpeed()
        print("[getVSSpeeds] Recommended VSSpeed {} index {}".format(speed, index))
        self.recommendedValue.setText(f"{speed:.2f} μs/pixel")
    
    def setVSSpeeds(self):
        desiredVSSpeed = self.verticalCBox.currentText()
        index = int(desiredVSSpeed.split(" - ")[0])
        print(f"[setVSSpeeds] Attempting to set {desiredVSSpeed} a VSSpeed with index {index}")
        ret = self.sdk.SetVSSpeed(index)
        print(f"[setVSSpeeds] Function SetVSSpeed returned {ret}.")
        # Retrieving fastest recommneded VSSpeeds to publish them in the UI
        # Returns the fastest speed which does not require the Vertical Clock Voltage to be adjusted.
        (ret, index, speed) = self.sdk.GetFastestRecommendedVSSpeed()
        print("[setVSSpeeds] Recommended VSSpeed {} index {}".format(speed, index))
        self.recommendedValue.setText(f"{speed:.2f} μs/pixel")

        self.updateAcquisitionTiming()
    
    def getAmplifiers(self):
        amp_modes=[]
        (ret, amps) = self.sdk.GetNumberAmp()
        print("[getAmplifiers] Function GetNumberAmp returned {} number of amplifiers {}".format(ret, amps))
        self.amplifierModesCBox.clear()
        for x in range(0, amps):
            (ret, name) = self.sdk.GetAmpDesc(x, 21)
            (ret, speed) = self.sdk.GetAmpMaxSpeed(x)
            self.amplifierModesCBox.addItem(f"{x} - {name}\nMax H.shift speed:{speed}")
            amp_modes.append(name)

        print("[getAmplifiers] Available amplifier modes {}".format(amp_modes))

    def setAmplifier(self):
        desiredAmplifier = self.amplifierModesCBox.currentText()
        print(f"[setAmplifier] Attempting to set {desiredAmplifier} as amplifier.")
        amplifierTyp = int(desiredAmplifier.split(" - ")[0])
        ret = self.sdk.SetOutputAmplifier(amplifierTyp)            
        print(f"[setAmplifier] Function returned {ret}")
        
        self.updateAcquisitionTiming()

    def getPreampGains(self):
        preampGains = []
        #IsPreAmpGainAvailable
        (ret, noGains) = self.sdk.GetNumberPreAmpGains()
        print(f"[getPreampGains] Function GetNumberPreAmpGains returned {ret}. There are {noGains} available preamps ")
        self.preampGainsCBox.clear()
        for gain in range(0, noGains):
            (ret, gain) = self.sdk.GetPreAmpGain(gain)
            preampGains.append(gain)
            self.preampGainsCBox.addItem(f"{gain}")
        
        print(f"[getPreampGains] Available preamplifiers: {preampGains}.")

    def setPreampGain(self):
        desiredPreampIndex = self.preampGainsCBox.currentIndex()
        desiredPreamp = self.preampGainsCBox.currentText()
        print(f"[setPreampGain] Attempting to set {desiredPreamp}, index {desiredPreampIndex} as preamp.")
        ret = self.sdk.SetPreAmpGain(desiredPreampIndex)
        print(f"[setPreampGain] Function SetPreAmpGain returned {ret}.")
        
        # Retrieving value of a current preamp gain
        (ret, index, name) = self.sdk.GetCurrentPreAmpGain(30)
        self.preampGainValue.setText(name.decode('ascii'))
        print(f"[currentPreAmpGain] Current preAmpGain index : {index}, name: {name}")

    def getCosmicRayFilterStatus(self):
        (ret, mode) = self.sdk.GetFilterMode()
        print(f"[getCosmicRayFilterStatus] Function GetFilterMode returned {ret}. Current mode filter mode : {mode}.")
        if mode == "0":
            self.cosmicRayFilter.setChecked(False)
        elif mode == "2":
            self.cosmicRayFilter.setChecked(True)
        else:
            print(f"[getCosmicRayFilterStatus] Filter status returned an invalid value : {mode}.")

    def setCosmicRayFilter(self):
        if self.cosmicRayFilter.isChecked():
            print(f"[setCosmicRayFilter] attempting to turn cosmic ray filter ON.")
            ret = self.sdk.SetFilterMode(2)
            print(f"[setCosmicRayFilter] function SetFilterMode returned {ret}")
        else:
            print(f"[setCosmicRayFilter] attempting to turn cosmic ray filter OFF.")
            ret = self.sdk.SetFilterMode(0)
            print(f"[setCosmicRayFilter] function SetFilterMode returned {ret}")


    def updateAcquisitionTiming(self):
        # Updating acquisition timings
        (ret, fminExposure, fAccumulate, fKinetic) = self.sdk.GetAcquisitionTimings()
        print(f"[updateAcquisitionTiming] Function GetAcquisitionTimings returned {ret} exposure = {fminExposure} accumulate = {fAccumulate} kinetic = {fKinetic}")

        self.exposureTimingValue.setText(f"{fminExposure} s")
        self.accumulateTimingValue.setText(f"{fAccumulate} s")
        self.kineticTimingValue.setText(f"{fKinetic} s")
