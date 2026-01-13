import sys, os, time, warnings, random
import numpy as np
#os.chdir("C:/Users/adato/Documents/Programs/Andor/")
from queue import Queue

from PyQt6.QtWidgets import QWidget, QMessageBox, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import QThread, Qt
from PyQt6.uic import loadUi
import icons_rc
# Loading prior stage library
from ctypes import WinDLL, create_string_buffer

class scanThreadClass(QThread):
    def __init__(self, acquisitionQ, scanQ, SDKPrior, stageSidebar, sessionID):
        super().__init__()
        self.acquisitionQ = acquisitionQ
        self.scanQ = scanQ
        self.SDKPrior = SDKPrior
        self.stageSidebar = stageSidebar
        self.sessionID = sessionID
        print("[scanThreadClass] temperature thread initialized.")

        self.rx = create_string_buffer(1000)

    def run(self):
        while True:
            scanMessage = self.scanQ.get()
            for position in scanMessage["Positions"]:
                #if self.acquisitionQ.empty():
                #    time.sleep(0.05)
                x,y,z = position
                print(f"Scan position: x = {x}, y = {y}, z = {z}")
                self.goToPosition(x=x, y=y, z=z)
                self.acquisitionQ.put({"Filename" : f"Spec_x-{x}_y-{y}_z-{z}"})
                # This should block until all of the tasks in the queue are done.
                self.acquisitionQ.join()
    
    #####################################################
    # Utility functions for moving the stage
    #####################################################

    def cmd(self, msg, callerFunction=""):
        # This formats commands that are communicated to the microscope stage over a COM port
        ret = self.SDKPrior.PriorScientificSDK_cmd(self.sessionID, create_string_buffer(msg.encode()), self.rx)
        if ret:
            print(f"[loadScanSidebar: cmd/{callerFunction}] Api error {ret}")
        else:
            print(f"[loadScanSidebar: cmd/{callerFunction}] OK {self.rx.value.decode()}")

        #input("Press ENTER to continue...")
        return ret, self.rx.value.decode()

    def goToPosition(self, x:float, y:float, z:float):
            # Transforming back to the units of the stage.
            x = x*10
            y = y*10
            z = z*1000
            # Retrieving current position
            #try:
            #    ret, positions = self.cmd("controller.stage.position.get", callerFunction="goToPosition/stage")
            #    print(f"[goToPosition] Function stage returned {ret}, starting position {positions}")

            #    currentX,currentY = positions.split(",")
            #except:
            #    ret = self.cmd("controller.stage.position.get", callerFunction="goToPosition/stage")
            #    print(f"[goToPosition] Error: Call controller.stage.position.get {ret}. Check if controller is connected.")
            #    currentX = 0
            #    currentY = 0           

            # Starting moving X and Y axies (always first to finish)
            ret, value = self.cmd(f"controller.stage.goto-position {x} {y}", callerFunction="moveRelative")
            print(f"[goToPosition/XY] Function stage move relative returned {ret}, value {value}")

            # Wait for controller to finish action
            ret, busy = self.cmd("controller.stage.busy.get", callerFunction="goToPosition/XYbusy")
            while busy != "0":
                time.sleep(0.1)
                ret, busy = self.cmd("controller.stage.busy.get", callerFunction="goToPosition/XYbusy")
            
            if int(z) < 1000 or int(z) > -1000: 
                print(f"[goToPosition/Z] ATTEMPTING TO SET Z TO : {z}")
                # Starting moving Z axis (last)
                ret, value = self.cmd(f"controller.z.goto-position {z}", callerFunction="goToPosition")
                print(f"[goToPosition/Z] Function z move relative returned {ret}, value {value}")
            
                # Wait for controller Z to finish action
                ret, zBusy = self.cmd("controller.z.busy.get", callerFunction="goToPosition/Zbusy")
                while zBusy != "0":
                    time.sleep(0.1)
                    ret, zBusy = self.cmd("controller.z.busy.get", callerFunction="goToPosition/Zbusy")
            else:
                print(f"[goToPosition/Z] REFUSING TO SET Z TO : {z}")

            # Updating current position
            self.stageSidebar.getCurrentPosition()


class loadScanSidebar(QWidget):
    def __init__(self, SDKPrior, sessionID, stageSidebar, acquisitionQ, acquisitionFinishedQ):
        super().__init__()
        # Retrieving session opened in the leftSidePanel class.
        self.SDKPrior = SDKPrior
        self.sessionID = sessionID
        self.stageSidebar = stageSidebar
        self.acquisitionQ = acquisitionQ
        self.acquisitionFinishedQ = acquisitionFinishedQ
        # Creating string buffer to communicate with the stage
        self.rx = create_string_buffer(1000)
        ############################################################
        # Needs to be turned on - For now doesnt do anything (why?)
        ############################################################
        self.realhw = True

        loadUi("leftSidebarsUIs/scanSidebar.ui", self)

        ######################################################
        # Connecting buttons
        ######################################################
        self.gridScanHelpBtn.clicked.connect(self.gridScanHelp)

        # These are to calculate the number of steps to display in the UI
        self.gridXStepNumber.textChanged.connect(self.updateNumberOfSteps)
        self.gridYStepNumber.textChanged.connect(self.updateNumberOfSteps)
        self.gridZStepNumber.textChanged.connect(self.updateNumberOfSteps)
        # Implementing a delete key to delete content of cells in a table
        self.startingPositionsQTable.keyPressEvent = self.deletePressEvent
        # Add location button
        self.addCurrentLocationBtn.clicked.connect(self.addCurrentLocation)
        self.additionalRowBtn.clicked.connect(self.addRowToTable)
        # A button starting the acquisition sequence.
        self.startScanSequenceBtn.clicked.connect(self.startScan)

        self.scanQ = Queue(maxsize = 1)
        self.scanThread = scanThreadClass(acquisitionQ=self.acquisitionQ, 
                                          scanQ=self.scanQ, 
                                          SDKPrior=self.SDKPrior, 
                                          stageSidebar=self.stageSidebar,
                                          sessionID=self.sessionID)
        self.scanThread.start()
    
    def cmd(self, msg, callerFunction=""):
        # This formats commands that are communicated to the microscope stage over a COM port
        ret = self.SDKPrior.PriorScientificSDK_cmd(self.sessionID, create_string_buffer(msg.encode()), self.rx)
        if ret:
            print(f"[loadScanSidebar: cmd/{callerFunction}] Api error {ret}")
        else:
            print(f"[loadScanSidebar: cmd/{callerFunction}] OK {self.rx.value.decode()}")

        #input("Press ENTER to continue...")
        return ret, self.rx.value.decode()

    def startScan(self):
        # For now there is just one scanning mode. Perhaps more will be added 
        # in the future, in which case they will be selectable here.
        self.scanPositions = self.spiralSequence()
        
        try:
            self.scanQ.put({"Positions":self.scanPositions})
        except:
            print("[loadScanSidebar/startScan] Scan queue is full. Perhaps previous scan is not finished yet. Try again later.")
    
    def spiralSequence(self):

        X = self.gridXStepNumber.value()
        Y = self.gridYStepNumber.value()
        Z = self.gridZStepNumber.value()

        print(f"[loadScanSidebar/spiralSequence]Number of steps: x = {X}, y = {Y}, z = {Z}")

        deltaX = self.gridXStepSize.value()
        deltaY = self.gridYStepSize.value()
        deltaZ = self.gridZStepSize.value()

        print(f"[loadScanSidebar/spiralSequence]Step size : δx = {deltaX}, δy = {deltaY}, δz = {deltaZ}")

        positionsList = self.readTable()

        print(f"[loadScanSidebar/spiralSequence] Starting positions: {positionsList}")


        if len(positionsList) == 0:
            Xstart, Ystart, Zstart = self.retrieveCurrentPosition()
            positionsList = [[Xstart, Ystart, Zstart]]

        
        output = []

        for Xstart, Ystart, Zstart in positionsList:
            outputLocal = []
            # Calculating the last value
            Zend = Zstart+((Z-1)*deltaZ)
            for zCurrent in np.linspace(Zstart, Zend, Z):
                # The pattern is just repeated for all values of Z. 
                x = y = 0
                dx = 0
                dy = -1
                n = 0
                for i in range(max(X, Y)**2):
                    if (-X/2 < x <= X/2) and (-Y/2 < y <= Y/2):
                        #print (x, y)
                        # DO STUFF...
                        Xcurrent = float(Xstart + x*deltaX)
                        Ycurrent = float(Ystart + y*deltaY)
                        outputLocal.append((Xcurrent, Ycurrent, zCurrent))
                        #print(f"{n} Xcurrent = {Xcurrent:.4f}, Ycurrent = {Ycurrent:.4f}")
                        n += 1
                    if x == y or (x < 0 and x == -y) or (x > 0 and x == 1-y):
                        dx, dy = -dy, dx
                    x, y = x+dx, y+dy
                
            # Check if user wants local output shuffled.
            if self.randomizeLocalOrderCheckBox.isChecked():
                random.shuffle(outputLocal)

            output = output + outputLocal

        if self.randomizeGlobalOrderCheckBox.isChecked():
            random.shuffle(output)
        print(f"[loadScanSidebar/spiralSequence] Output of spiralSequence: {output}")
        return output
    
    ####################################################
    # UI utility functions
    ####################################################
    
    def updateNumberOfSteps(self):
        try:
            xSteps = int(self.gridXStepNumber.text())
            self.gridXLabel.setText("X") # Value is correct, removing highlight.
        except:
            if self.gridXStepNumber.text() == "":
                # User didn't provide any value. This is allowed. Using neutral 1
                xSteps = 1
                self.gridXLabel.setText("X") # Value is correct, removing highlight.
            else:
                #print(f"[updateNumberOfSteps] X type is {type(xSteps)}, X value is:{xSteps}.")
                xSteps = 1 # Wrong value provided highlight name and use 1 as neutral value
                self.gridXLabel.setText("<font color='red'>X</font>")
                print(f"[updateNumberOfSteps] Wrong value for X steps provided. Ignoring value and using 1 instead.")

        try:
            ySteps = int(self.gridYStepNumber.text())
            self.gridYLabel.setText("Y") # Value is correct, removing highlight.

        except:
            if self.gridYStepNumber.text() == "":
                # User didn't provide any value. This is allowed. Using neutral 1
                ySteps = 1
                self.gridYLabel.setText("Y") # Value is correct, removing highlight.
            else:
                ySteps = 1 # Wrong value provided highlight name and use 1 as neutral value
                self.gridYLabel.setText("<font color='red'>Y</font>")
                print(f"[updateNumberOfSteps] Wrong value for Y steps provided. Ignoring value and using 1 instead.")

        try:
            zSteps = int(self.gridZStepNumber.text())
            self.gridZLabel.setText("Z") # Value is correct, removing highlight.

        except:
            if self.gridZStepNumber.text() == "":
                # User didn't provide any value. This is allowed. Using neutral 1
                zSteps = 1
                self.gridZLabel.setText("Z") # Value is correct, removing highlight.
            else:
                zSteps = 1 # Wrong value provided highlight name and use 1 as neutral value
                self.gridZLabel.setText("<font color='red'>Z</font>")
                print(f"[updateNumberOfSteps] Wrong value for Z steps provided. Ignoring value and using 1 instead.")

        # Zero value doesn't make sense in this case. Using 1 instead
        if xSteps == 0:
            self.gridXLabel.setText("<font color='red'>X</font>")
            xSteps = 1
        if ySteps == 0:
            self.gridYLabel.setText("<font color='red'>Y</font>")
            ySteps = 1
        if zSteps == 0:
            self.gridZLabel.setText("<font color='red'>Z</font>")
            zSteps = 1

        self.numberOfSteps.setText(str(xSteps*ySteps*zSteps))

        print(f"[updateNumberOfSteps] number of steps X: {xSteps}, Y: {ySteps}, Z: {zSteps}.")

    def readTable(self):
        row_count = self.startingPositionsQTable.rowCount()
        column_count = self.startingPositionsQTable.columnCount()
        startingPositions = []

        for row in range(row_count):
            position = []
            for column in range(column_count):
                item = self.startingPositionsQTable.item(row, column)
                if item is not None:
                    position.append(float(item.text()))
                    #print(f"Row {row}, Column {column}: {item.text()}")
                else:
                    continue
                    #print(f"Row {row}, Column {column}: Empty")
            if len(position) > 0:
                startingPositions.append(position)

        return startingPositions

    def retrieveCurrentPosition(self):
        # Retrieving X and Y position (Z is retrieved separately below)
        try:
            # Retrieving current position
            ret, positions = self.cmd("controller.stage.position.get", callerFunction="getCurrentPosition/stage")
            #print(f"[loadScanSidebar/spiralSequence] Function stage returned {ret}, starting position {positions}")

            if ret == -10004:
                warnings.warn("[loadScanSidebar/spiralSequence] Stage is unavailable. Mock operation initiated with the pseudo starting position x=0, y=0, z=0.", UserWarning)   
                currentX, currentY, Zstart = 0,0,0
            else:
                print(f"[loadScanSidebar/spiralSequence] Get current position returned {ret} value : {positions}")
                currentX, currentY = positions.split(",")
                # Xstart and currentY come as a string and without any decimal point, which are the last two digits.
                currentX = float(currentX)/10
                currentY = float(currentY)/10
                #currentX = float(currentX)
                #currentY = float(currentY)
        except:
            ret = self.cmd("controller.stage.position.get", callerFunction="goToPosition/stage")
            print(f"[goToPosition] Error: Call controller.stage.position.get {ret}. Check if controller is connected.")
            currentX, currentY = None
        
        # Retrieving Z position
        try:
            ret, currentZ = self.cmd("controller.z.position.get", callerFunction="goToPosition/z")
            # Zstart comes as a string and is without any decimal point (which are the two last digits)
            currentZ = float(currentZ)/1000
        except:
            ret = self.cmd("controller.z.position.get", callerFunction="goToPosition/z")
            print(f"[goToPosition] Error: Call controller.z.position.get returned {ret}. Check if controller is connected.")
            currentZ = None

        return currentX, currentY, currentZ
    
    def deletePressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            self.deleteSelectedItems()
        else:
            super(QTableWidget, self.startingPositionsQTable).keyPressEvent(event)

    def deleteSelectedItems(self):
        selectedItems = self.startingPositionsQTable.selectedItems()
        for item in selectedItems:
            self.startingPositionsQTable.takeItem(item.row(), item.column())

    def addCurrentLocation(self):
        # Retrieving current location of the stage
        currentX, currentY, currentZ = self.retrieveCurrentPosition()

        # Retrieving the shape of the table
        row_count = self.startingPositionsQTable.rowCount()
        column_count = self.startingPositionsQTable.columnCount()
        # Iterating over rows, we first check if a row is full of None values
        # We also need to check if the values are not just empty strings "". This will happen after user has deleted items.
        for row in range(row_count):
            if all(self.startingPositionsQTable.item(row, col) is None for col in range(column_count)):
                #if all(self.table.item(row, col) is "" for col in range(column_count)):
                for col, position in zip(range(column_count), [currentX, currentY, currentZ]):
                    self.startingPositionsQTable.setItem(row, col, QTableWidgetItem(str(position)))
                break
    
    def addRowToTable(self):
        row_count = self.startingPositionsQTable.rowCount()
        self.startingPositionsQTable.insertRow(row_count)
            
    ############################################################################
    # Help functions
    ############################################################################

    def gridScanHelp(self):
        msg = QMessageBox()
        msg.setWindowTitle("Grid scan help")
        msg.setText("""
        Grid scan will start at the current position and proceed to scan through 
        an X, Y using the user provided step size and number of steps to construct
        a grid. If a number of Z steps and their size is provided, the procedure is
        subsequently repeated for each Z step. Positive and negative values of step 
        sizes are permissible and will determine the direction of stepping (positive 
        Z upwards, negative downwards).
        If no value is provided, there will be no stepping in that direction. 
        For example, not providing Z step values will result in reading in a 
        current plane.  Not providing X step information will yield a plane scan 
        following the YZ axis. Finally, not providing Y and Z step information will 
        yield line read along the X axis.
        """)

        msg.setIcon(QMessageBox.Information)

        x = msg.exec_()
