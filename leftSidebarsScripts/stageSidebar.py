import sys, os, time

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QWidget, QMessageBox
from PyQt6.uic import loadUi
import icons_rc
# Loading prior stage library
from ctypes import WinDLL, create_string_buffer


class loadStageSidebar(QWidget):
    def __init__(self, SDKPrior, sessionID):
        super().__init__()
        # Retrieving session opened in the leftSidePanel class.
        self.SDKPrior = SDKPrior
        self.sessionID = sessionID
        # Creating string buffer
        self.rx = create_string_buffer(1000)
        ############################################################
        # Needs to be turned on
        ############################################################
        self.realhw = True

        loadUi("leftSidebarsUIs/stageSidebar.ui", self)
        """
        ############################################################
        # Path needs to be changed 
        ############################################################
        path = "./PriorSDK/x64/PriorScientificSDK.dll"

        if os.path.exists(path):
            self.SDKPrior = WinDLL(path)
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
        """
        # Checking a Prior session (only a ping)
        ret = self.SDKPrior.PriorScientificSDK_cmd(self.sessionID, create_string_buffer(b"dll.apitest 33 goodresponse"), self.rx)
        print(f"[loadStageSidebar] api response {ret}, rx = {self.rx.value.decode()}")
        #input("Press ENTER to continue...")

        ret = self.SDKPrior.PriorScientificSDK_cmd(self.sessionID, create_string_buffer(b"dll.apitest -300 stillgoodresponse"), self.rx)
        print(f"[loadStageSidebar] api response {ret}, rx = {self.rx.value.decode()}")
        #input("Press ENTER to continue...")

        if self.realhw:
            print("[loadStageSidebar] Connecting...")
            # substitute 3 with your com port Id
            self.cmd("controller.connect 3")

            # get current XY position in default units of microns
            self.cmd("controller.stage.position.get")

            # Set stage step size 
            self.cmd("controller.stage.ss.set 10")

            self.getControllerModel()
            self.getSerialNumber()

            self.getCurrentPosition()

        ######################################################
        # Connecting buttons
        ######################################################
        self.goToPositionHelpBtn.clicked.connect(self.goToPositionHelp)
        self.setZeroPositionBtn.clicked.connect(self.setCurrentPositionToZero)
        self.refreshPositionBtn.clicked.connect(self.getCurrentPosition)
        self.goToPositionBtn.clicked.connect(self.goToPosition)
        # Move by increment field
        self.decrementXBtn.clicked.connect(self.moveRelativeMinusX)
        self.incrementXBtn.clicked.connect(self.moveRelativeX)
        self.decrementYBtn.clicked.connect(self.moveRelativeMinusY)
        self.incrementYBtn.clicked.connect(self.moveRelativeY)
        self.decrementZBtn.clicked.connect(self.moveRelativeMinusZ)
        self.incrementZBtn.clicked.connect(self.moveRelativeZ)

    def cmd(self, msg, callerFunction=""):
        #print(msg)
        ret = self.SDKPrior.PriorScientificSDK_cmd(self.sessionID, create_string_buffer(msg.encode()), self.rx)
        if ret:
            print(f"[loadStageSidebar: cmd/{callerFunction}] Api error {ret}")
        else:
            print(f"[loadStageSidebar: cmd/{callerFunction}] OK {self.rx.value.decode()}")

        #input("Press ENTER to continue...")
        return ret, self.rx.value.decode()
    
    def getControllerModel(self):
        ret, model = self.cmd("controller.model.get", callerFunction="getControllerModel")
        print(f"[getControllerModel] Function returned {ret}, model: {model}")
        # Dislplaying model number in the UI
        self.modelNumberValue.setText(model)

    def getSerialNumber(self):
        ret, serialNumber = self.cmd("controller.serialnumber.get", callerFunction="getSerialNumber")
        print(f"[getSerialNumber] Function returned {ret}, serial number: {serialNumber}")
        # Dislplaying serial number in the UI
        self.serialNumberValue.setText(serialNumber)

    def goToPosition(self, externalX=None, externalY=None, externalZ=None):
        # Retrieving current position
        try:
            ret, positions = self.cmd("controller.stage.position.get", callerFunction="goToPosition/stage")
            print(f"[goToPosition] Function stage returned {ret}, starting position {positions}")

            currentX,currentY = positions.split(",")
        except:
            ret = self.cmd("controller.stage.position.get", callerFunction="goToPosition/stage")
            print(f"[goToPosition] Error: Call controller.stage.position.get {ret}. Check if controller is connected.")
            currentX, currentY = None

        if externalX:
            x = externalX
        if self.goToPositionX.text() == "":
            # If provided empty, it is substituted by current position
            x = currentX
            print(f"[goToPosition] No value X provided. Using current X:{x}")
        else:
            x = self.goToPositionX.text()
            try:
                x = float(x)
                x = int(10*x)
            except:
                print(f"[goToPosition] X is not a valid number : X:{x}")

        if externalY:
            y = externalY
        if self.goToPositionY.text() == "":
            # If provided empty, it is substituted by current position
            y = currentY
            print(f"[goToPosition] No value Y provided. Using current Y:{y}")
        else:
            y = self.goToPositionY.text()
            try:
                y = float(y)
                y = int(10*y)
            except:
                print(f"[goToPosition] Y is not a valid number : Y:{y}")

        try:
            ret, currentZ = self.cmd("controller.z.position.get", callerFunction="goToPosition/z")
        except:
            ret = self.cmd("controller.z.position.get", callerFunction="goToPosition/z")
            print(f"[goToPosition] Error: Call controller.z.position.get returned {ret}. Check if controller is connected.")
            currentZ = None

        if externalZ:
            z = externalZ
        if self.goToPositionZ.text() == "":
            # If provided empty, it is substituted by current position
            z = currentZ
            print(f"[goToPosition] No value Z provided. Using current Z:{z}")
        else:
            z = self.goToPositionZ.text()
            try:
                z = float(z)
                z = int(z*1000)
            except:
                print(f"[goToPosition] Z is not a valid number : Z:{z}")

        # Finished checking input here. We should have x = float, y = float and z = float

        # Starting moving X and Y axies (always first to finish)
        ret, value = self.cmd(f"controller.stage.goto-position {x} {y}", callerFunction="moveRelative")
        print(f"[goToPosition/XY] Function stage move relative returned {ret}, value {value}")

        # Wait for controller to finish action
        ret, busy = self.cmd("controller.stage.busy.get", callerFunction="goToPosition/XYbusy")
        while busy != "0":
            time.sleep(0.2)
            ret, busy = self.cmd("controller.stage.busy.get", callerFunction="goToPosition/XYbusy")
        
        if int(z) < 1000 or int(z) > -1000: 
            print(f"[goToPosition/Z] ATTEMPTING TO SET Z TO : {z}")
            # Starting moving Z axis (last)
            ret, value = self.cmd(f"controller.z.goto-position {z}", callerFunction="goToPosition")
            print(f"[goToPosition/Z] Function z move relative returned {ret}, value {value}")
        
            # Wait for controller Z to finish action
            ret, zBusy = self.cmd("controller.z.busy.get", callerFunction="goToPosition/Zbusy")
            while zBusy != "0":
                time.sleep(0.2)
                ret, zBusy = self.cmd("controller.z.busy.get", callerFunction="goToPosition/Zbusy")
        else:
            print(f"[goToPosition/Z] REFUSING TO SET Z TO : {z}")

        # Updating current position
        self.getCurrentPosition()


    def moveRelativeX(self):
        x = int(self.incrementX.text())
        # To transform to micro meters, needs to be multiplied by 10
        x = x*10    # For some reason the unit is in 0.1 of micro meter. Which might be the smallest increment. 


        # Retrieving current position
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[moveRelativeX] Function stage returned {ret}, starting position {positions}")

        # Starting moving X and Y axies (always first to finish)
        ret, value = self.cmd(f"controller.stage.move-relative {x} {0}", callerFunction="moveRelative")
        print(f"[moveRelativeX] Function stage move relative returned {ret}, value {value}")
        
        # Wait for controller to finish action
        ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeX")
        while busy != "0":
            time.sleep(0.2)
            ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeX")
        
        # Updating current position
        self.getCurrentPosition()
    
    def moveRelativeMinusX(self):
        # Negative value of the X field
        x = -int(self.incrementX.text())
        # To transform to micro meters, needs to be multiplied by 10
        x = x*10
        
        # Retrieving current position
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[moveRelativeMinusX] Function stage returned {ret}, starting position {positions}")

        # Starting moving X and Y axies (always first to finish)
        ret, value = self.cmd(f"controller.stage.move-relative {x} {0}", callerFunction="moveRelative")
        print(f"[moveRelativeMinusX] Function stage move relative returned {ret}, value {value}")
        
        # Wait for controller to finish action
        ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeMinusX")
        while busy != "0":
            time.sleep(0.2)
            ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeMinusX")
        
        # Updating current position
        self.getCurrentPosition()
    
    def moveRelativeY(self):
        # If Y is not supplied externally, read the stage value
        y = int(self.incrementY.text())
        # To transform to micro meters, needs to be multiplied by 10
        y = y*10
        # Retrieving current position
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[moveRelativeY] Function stage returned {ret}, starting position {positions}")

        # Starting moving X and Y axies (always first to finish)
        ret, value = self.cmd(f"controller.stage.move-relative {0} {y}", callerFunction="moveRelativeY")
        print(f"[moveRelativeY] Function stage move relative returned {ret}, value {value}")
        
        # Wait for controller to finish action
        ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeY")
        while busy != "0":
            time.sleep(0.2)
            ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeY")
        
        # Updating current position
        self.getCurrentPosition()

    def moveRelativeMinusY(self):
        # Negative value of the Y field
        y = -int(self.incrementY.text())
        # To transform to micro meters, needs to be multiplied by 10
        y = y*10

        # Retrieving current position
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[moveRelativeMinusY] Function stage returned {ret}, starting position {positions}")

        # Starting moving X and Y axies (always first to finish)
        ret, value = self.cmd(f"controller.stage.move-relative {0} {y}", callerFunction="moveRelativeMinusY")
        print(f"[moveRelativeMinusY] Function stage move relative returned {ret}, value {value}")
        
        # Wait for controller to finish action
        ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeMinusY")
        while busy != "0":
            time.sleep(0.2)
            ret, busy = self.cmd("controller.stage.busy.get", callerFunction="moveRelativeMinusY")
        
        # Updating current position
        self.getCurrentPosition()

    def moveRelativeZ(self):
        z = int(self.incrementZ.text())
        # To transform to micro meters, needs to be multiplied by 1000
        z = z*1000

        # Retrieving current position
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[moveRelativeZ] Function stage returned {ret}, starting position {positions}")

        # Starting moving Z axis (last)
        ret, value = self.cmd(f"controller.z.move-relative {z}", callerFunction="moveRelative")
        print(f"[moveRelative/Z] Function z move relative returned {ret}, value {value}")
        
        # Wait for controller Z to finish action
        ret, zBusy = self.cmd("self.controller.z.busy.get", callerFunction="moveRelative")
        while zBusy != "0":
            time.sleep(0.2)
            ret, zBusy = self.cmd("self.controller.z.busy.get", callerFunction="moveRelative")
        
        # Updating current position
        self.getCurrentPosition()
    
    def moveRelativeMinusZ(self):
        # Negative value of the Z field
        z = -int(self.incrementZ.text())
        # To transform to micro meters, needs to be multiplied by 1000
        z = z*1000
        
        # Retrieving current position
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[moveRelativeZ] Function stage returned {ret}, starting position {positions}")

        # Starting moving Z axis (last)
        ret, value = self.cmd(f"controller.z.move-relative {z}", callerFunction="moveRelative")
        print(f"[moveRelative/Z] Function z move relative returned {ret}, value {value}")
        
        # Wait for controller Z to finish action
        ret, zBusy = self.cmd("self.controller.z.busy.get", callerFunction="moveRelative")
        while zBusy != "0":
            time.sleep(0.2)
            ret, zBusy = self.cmd("self.controller.z.busy.get", callerFunction="moveRelative")
        
        # Updating current position
        self.getCurrentPosition()

    def getCurrentPosition(self):
        # By default, units for stage position are integer representation of microns.
        ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
        print(f"[getCurrentPosition] Function stage returned {ret}, current position {positions}")
        
        try:
            x, y = positions.split(",")
            self.currentXPos.setText(x[:-1] + "." + x[-1:] + " μm")
            self.currentYPos.setText(y[:-1] + "." + y[-1:] + " μm")
            #self.currentXPos.setText(x + " μm")
            #self.currentYPos.setText(y + " μm")

            ret, zPosition = self.cmd("controller.z.position.get", callerFunction="getCurrentPosition/z")
            print(f"[getCurrentPosition] Function Z returned {ret}, current position {zPosition}")

            # Z position appears to not be reported in nanometers 
            zPosition = zPosition[:-3]+"."+zPosition[-3:]

            self.currentZPos.setText(zPosition + " μm")
        except:
            ret = self.cmd("controller.z.position.get", callerFunction="getCurrentPosition/z")
            print(f"[getCurrentPosition] Retrieving current position error. Check if controller is available. Command controller.z.position.get returned {ret}.")

    def setCurrentPositionToZero(self):
        ret, value= self.cmd("controller.stage.position.set 0 0", callerFunction="setCurrentPositionToZero/stage")
        print(f"[setCurrentPositionToZero] Function stage returned {ret}, value {value}.")

        ret, value= self.cmd("controller.z.position.set 0", callerFunction="setCurrentPositionToZero/z")
        print(f"[setCurrentPositionToZero] Function Z returned {ret}, value {value}.")

        self.getCurrentPosition()

    def controllerDisconnect(self):
        ret, value= self.cmd("controller.disconnect", callerFunction="controllerDisconnect")
    
        print(f"[setCurrentPositionToZero] Function returned {ret}, value {value}.")
        return value
    
    """
    Deprecated:

    def openShutter(self):
        ret,value = self.cmd("controller.ttl.out.set 1")
        print(f"[loadStageSidebar/openShutter] Function returned {ret}, value {value}.")

    def closeShutter(self):
        ret,value = self.cmd("controller.ttl.out.set 0")
        print(f"[loadStageSidebar/closeShutter] Function returned {ret}, value {value}.")
    """ 

    ############################################################################
    # Help functions
    ############################################################################

    def goToPositionHelp(self):
        msg = QMessageBox()
        msg.setWindowTitle("Go to position help")
        msg.setText("""
        This moves the stage to a specified absolute position.
        Fill in the desired values and initiate the movement by
        pressing the button 'Go'. You can leave one or more fields
        empty if you do not wish to move to that direction.

        For example, if you want to only move to an absolute
        position on the X axis, leave the Y and Z axis fields empty.
        """)

        msg.setIcon(QMessageBox.Information)

        x = msg.exec_()

if __name__ == "__main__":
    print("Not possible to load stageSidebar alone.")
