import sys, os, time

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")
# A folder with sidebar scripts needs to be specified and added to the system path for them to be loaded properly
rootDirname = os.path.dirname(__file__)
leftSidebarDirname = os.path.join(rootDirname, 'leftSidebarsScripts')
sys.path.append(leftSidebarDirname)

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QPropertyAnimation, QSequentialAnimationGroup, QRect, QSize
from PyQt6.uic import loadUi
from PyQt6.QtGui import QMouseEvent
import icons_rc
from detectorSidebar import loadDetectorSidebar
from spectrographSidebar import loadSpectrographSidebar
from acquisitionSidebar import loadAcquisitionSidebar
from shutterSidebar import loadShutterSidebar
from stageSidebar import loadStageSidebar
from scanSidebar import loadScanSidebar
from daqSidebar import loadDaqSidebar
from daqSettings import loadDaqSettings
from plotSettings import loadPlotSettings
from fluigentSidebar import loadFluigentSiebar
# This is where you drop in your plugin!

from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

# Stage controller
from ctypes import WinDLL, create_string_buffer

class loadSidePanel(QWidget):
    #def __init__(self, sdk, spc, startAcquisition, plot):
    def __init__(self, sdk, spc, acquisitionQ, acquisitionFinishedQ, mainCanvasMdi, plotQ):
        super().__init__()
        self.sdk = sdk
        self.spc = spc
        self.acquisitionQ = acquisitionQ
        self.acquisitionFinishedQ = acquisitionFinishedQ
        self.mainCanvasMdi = mainCanvasMdi
        self.plotQ = plotQ
        #self.plot = plot
        #self.sdk = atmcd()  # Load the atmcd library
        self.codes = atmcd_codes
        print(f"[leftSidePanel] sdk : {self.sdk}")
        loadUi("leftSidebar.ui", self)

        ############################################################
        # Loading stage
        ############################################################
        # Path needs to be changed 
        ############################################################
        path = "./PriorSDK/x64/PriorScientificSDK.dll"

        if os.path.exists(path):
            self.SDKPrior = WinDLL(path)
            print("Prior stage DLL found at {path} and loaded.")
        else:
            raise RuntimeError("DLL could not be loaded.")
        
        self.rx = create_string_buffer(1000)
        ############################################################
        # Needs to be turned on
        ############################################################
        self.realhw = True

        # Initializing Prior SDK
        ret = self.SDKPrior.PriorScientificSDK_Initialise()
        if ret:
            print(f"[loadStageSidebar] Error initialising {ret}")
            sys.exit()
        else:

            print(f"[loadStageSidebar] Ok initialising {ret}")

        # Returning a prior SDK version information
        ret = self.SDKPrior.PriorScientificSDK_Version(self.rx)
        print(f"[loadStageSidebar] dll version api ret={ret}, version={self.rx.value.decode()}")

        # Opening a prior session
        self.sessionID = self.SDKPrior.PriorScientificSDK_OpenNewSession()
        if self.sessionID < 0:
            print(f"[loadStageSidebar] Error getting sessionID {ret}")
        else:
            print(f"[loadStageSidebar] SessionID = {self.sessionID}")

        self.sideMenuFrameVisible = False
        
        #####################################################
        # Loading sidebar widgets
        #####################################################
        # TODO : Describe in details the procedure of adding a new button, 
        # linking a new widget and adding a callback

        self.acquisitionSidebar = loadAcquisitionSidebar(sdk=self.sdk, spc=self.spc, plotQ=self.plotQ)
        acquisitionWidgetNum = self.leftStackedWidget.addWidget(self.acquisitionSidebar)

        self.detectorSidebar = loadDetectorSidebar(sdk=self.sdk)
        detectorWidgetNum = self.leftStackedWidget.addWidget(self.detectorSidebar)

        self.spectrographSidebar = loadSpectrographSidebar(spc=self.spc)
        spectrographWidgetNum = self.leftStackedWidget.addWidget(self.spectrographSidebar)

        self.shutterSidebar = loadShutterSidebar(sdk=self.sdk)
        shutterNum = self.leftStackedWidget.addWidget(self.shutterSidebar)

        self.stageSidebar = loadStageSidebar(SDKPrior=self.SDKPrior, sessionID=self.sessionID)
        stageWidgetNum = self.leftStackedWidget.addWidget(self.stageSidebar)



        self.scanSidebar = loadScanSidebar(SDKPrior=self.SDKPrior, 
                                           sessionID=self.sessionID, 
                                           stageSidebar=self.stageSidebar,
                                           acquisitionQ=self.acquisitionQ,
                                           acquisitionFinishedQ=self.acquisitionFinishedQ)
        
        scanWidgetNum = self.leftStackedWidget.addWidget(self.scanSidebar)

        self.daqSettings = loadDaqSettings()
        daqSettingstNum = self.leftStackedWidget.addWidget(self.daqSettings)

        self.daqSidebar = loadDaqSidebar(acquisitionQ=self.acquisitionQ, 
                                         daqSettings = self.daqSettings,
                                         mainCanvasMdi=self.mainCanvasMdi,
                                         sdk = self.sdk,
                                         plotQ = self.plotQ)
        
        daqSidebarNum = self.leftStackedWidget.addWidget(self.daqSidebar)

        #self.plotSettings = loadPlotSettings(mainCanvasMdi=self.mainCanvasMdi, plotQ=self.plotQ)
        #plotSettingsNum = self.leftStackedWidget.addWidget(self.plotSettings)

        self.fluigentSettings = loadFluigentSiebar()
        fluigentSettingsNum = self.leftStackedWidget.addWidget(self.fluigentSettings)
        
        #####################################################
        # Connecting buttons
        #####################################################
        self.acquisitionSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(acquisitionWidgetNum))
        self.detectorSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(detectorWidgetNum))
        self.apertureSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(spectrographWidgetNum))
        self.shutterBtn.clicked.connect(lambda: self.menuBtnClicked(shutterNum))
        self.stageMovementBtn.clicked.connect(lambda: self.menuBtnClicked(stageWidgetNum))
        self.scanSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(scanWidgetNum))
        self.daqSidebarBtn.clicked.connect(lambda: self.menuBtnClicked(daqSidebarNum, width=300))
        self.daqSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(daqSettingstNum))
        #self.plotSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(plotSettingsNum))
        self.fluigentSettingsBtn.clicked.connect(lambda: self.menuBtnClicked(fluigentSettingsNum))
        self.leftFrame.mouseReleaseEvent=self.menuBtnClicked
        
    def menuBtnClicked(self, desiredWidget, width = 300):
        print("Menu button clicked.")
        currentWidget = self.leftStackedWidget.currentIndex()
        if type(desiredWidget) == QMouseEvent:
            pass
        else:
            self.leftStackedWidget.setCurrentIndex(desiredWidget)

        # Closing animation only of user clicked on a current icon again
        if currentWidget == desiredWidget or type(desiredWidget) == QMouseEvent:
            duration = 100
            if self.sideMenuFrameVisible and self.rightFrame.width != 0:
                # Menu animation
                self.animationGroup = QSequentialAnimationGroup()
                                                            
                self.animationMenu = QPropertyAnimation(self.rightFrame, b"minimumSize")
                self.animationMenu.setDuration(duration)
                self.animationMenu.setStartValue(QSize(width,self.rightFrame.height()))
                self.animationMenu.setEndValue(QSize(0,self.rightFrame.height()))
                self.animationGroup.addAnimation(self.animationMenu)

                self.animationGroup.start()
                self.sideMenuFrameVisible = False
            else:
                self.animationGroup = QSequentialAnimationGroup()
                self.animationMenu = QPropertyAnimation(self.rightFrame, b"minimumSize")
                self.animationMenu.setDuration(duration)
                self.animationMenu.setStartValue(QSize(0,self.rightFrame.height()))
                self.animationMenu.setEndValue(QSize(width,self.rightFrame.height()))
                self.animationGroup.addAnimation(self.animationMenu)
                
                self.animationGroup.start()
                self.sideMenuFrameVisible = True
        self.rightFrame.setMinimumWidth(width)

