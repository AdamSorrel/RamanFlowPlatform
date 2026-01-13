import sys, os, time

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QFont
from PyQt6.uic import loadUi
import icons_rc

import nidaqmx as ni

class loadDaqSettings(QWidget):
    def __init__(self):
        super().__init__()
        loadUi("leftSidebarsUIs/daqSettings.ui", self)

        self.local = ni.system.System.local()

        for device in self.local.devices:
            self.daqDevicesCBox.addItem(f"{device.name} {device.product_type}")

        self.daqDevicesCBox.currentTextChanged.connect(self.populateChannels)
        self.daqChannel1CBox.currentIndexChanged.connect(lambda: self.setChannel("Channel 1"))
        self.daqChannel2CBox.currentIndexChanged.connect(lambda: self.setChannel("Channel 2"))
        self.daqChannel3CBox.currentIndexChanged.connect(lambda: self.setChannel("Channel 3"))
        
        try:
            self.populateChannels()
        except:
            print("[loadDaqSettings] Unspecific error when trying to connect to the DAQ card. Is it connected?")
              
    def populateChannels(self):
        self.device = self.local.devices[self.daqDevicesCBox.currentIndex()]

        self.daqChannel1CBox.addItem("Inactive")
        self.daqChannel2CBox.addItem("Inactive")
        self.daqChannel3CBox.addItem("Inactive")

        for channel in self.device.ai_physical_chans:
            self.daqChannel1CBox.addItem(channel.name)
            self.daqChannel2CBox.addItem(channel.name)
            self.daqChannel3CBox.addItem(channel.name)

        if self.daqChannel1CBox.count() >= 5:
            self.daqChannel1CBox.setCurrentIndex(1)
            self.daqChannel2CBox.setCurrentIndex(3)
            self.daqChannel3CBox.setCurrentIndex(5)

    def setChannel(self, currentChannel):
        # Getting a strike through formatted font and normal font to label deactivated items.
        strikeThroughFont = QFont()
        strikeThroughFont.setStrikeOut(True)

        normalFont = QFont()
        normalFont.setStrikeOut(False)

        channels = {"Channel 1" : self.daqChannel1CBox, 
                    "Channel 2" : self.daqChannel2CBox, 
                    "Channel 3" : self.daqChannel3CBox}
        
        # Removing all previous formatting
        for chan in channels.keys():
            for index in range(0, channels[chan].count()):
                channels[chan].model().item(index).setEnabled(True)
                channels[chan].model().item(index).setFont(normalFont)

        for channel1 in channels.keys():
            #print(f"channel1 : {channel1}")
            selectedIndex = channels[channel1].currentIndex()
            #print(f"selected index : {selectedIndex}")
            # The Inactive option cannot be deactivated. 
            # Also when still loading in the current selected item index of empty combo box is -1. 
            if selectedIndex > 0:
                for channel2 in channels.keys():
                    #print(f"channel2 : {channel2}")
                    #print(f"channels[channel2] : {type(channels[channel2])}")
                    channels[channel2].model().item(selectedIndex).setEnabled(False)
                    channels[channel2].model().item(selectedIndex).setFont(strikeThroughFont)
                    channels[channel2].model().item(selectedIndex+1).setEnabled(False)
                    channels[channel2].model().item(selectedIndex+1).setFont(strikeThroughFont)


