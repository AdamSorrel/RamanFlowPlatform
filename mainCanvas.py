import sys, os, time, random

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QDoubleSpinBox, QSpinBox, 
                             QLabel, QMainWindow, QComboBox, QLineEdit, QTabWidget)
from PyQt6.uic import loadUi
from PyQt6.QtCore import QThread, pyqtSignal, QRect
import icons_rc
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from queue import Queue
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import math
import matplotlib.lines as lines

import pyqtgraph as pg

# Wiener smoothing
from scipy.signal import wiener
# Baseline correction
import pybaselines as pb   

###################################################
# Main plot
###################################################

class mainPlotSubWindow(QMainWindow):
    # This class handles the UI side of plot subwindow. It contains all buttons 
    # and it also spawns (is the parent of) the plot thread and the canvas widget, to which it passes button handles 
    # for updating plots (e.g. smoothing or baseline correction)
    def __init__(self, q, type):
        self.q = q
        self.type = type
        super().__init__()
        """
        if type == "raw":
            print("[mainPlotSubWindow] Spawning a raw data plot window.")
            # Spawning main plot sub window
            self.plot = mainPlotCanvas(self.q)
            self.setCentralWidget(self.plot)
            self.show()

            ################################################
            # Starting an acquisition thread.
            # Thread updating current pressure
            self.q = q
            self.plotThread = mainPlotThread(q=self.q, ax1=self.plot.ax1, ax2=self.plot.ax2, fig=self.plot.fig)
            self.plotThread.start()

        elif type == "smoothed":
        """

        self.tab = QTabWidget()

        self.lineTabWidget = QWidget()
        self.lineTabWidgetLayout = QVBoxLayout()
        self.lineTabWidget.setLayout(self.lineTabWidgetLayout)

        self.imageTabWidget = QWidget()
        self.imageTabWidgetLayout = QVBoxLayout()
        self.imageTabWidget.setLayout(self.imageTabWidgetLayout)

        self.tab.addTab(self.lineTabWidget, "Line plot")
        self.tab.addTab(self.imageTabWidget, "Image plot")


        self.tabLayout = QVBoxLayout()
        self.tabLayout.addWidget(self.tab)

        self.tabContainer = QWidget()
        self.tabContainer.setLayout(self.tabLayout)
        
        self.tab.setStyleSheet("background: #1E2529; border-radius: 0px")
        self.tabContainer.setStyleSheet("background: #2F3133; border-radius: 0px; border: 0px; margin: 0px; padding: 0px")

        self.setCentralWidget(self.tabContainer)

        print("[mainPlotSubWindow] Spawnin plot window.")
        # General smoothing tooTlbar.
        self.toolbar = QToolBar()
        toggleView = self.toolbar.toggleViewAction()
        toggleView.setText("Hide toolbar")
        self.toolbar.addWidget(QLabel("Smoothing:"))
        self.smoothingSpinBox = QSpinBox()
        self.smoothingSpinBox.setRange(0, 999)
        self.toolbar.addWidget(self.smoothingSpinBox)
        self.toolbar.addSeparator()
        self.baselineCorrectionCBox = QComboBox()
        self.baselineCorrectionCBox.addItems(["No baseline correction", "Polynomial correction", "PSspline airPLS"])
        self.toolbar.addWidget(self.baselineCorrectionCBox)
        self.toolbar.setVisible(True)
        #self.addToolBar(self.toolbar)
        self.lineTabWidgetLayout.addWidget(self.toolbar)

        # Polynomial baseline subtraction 
        self.polyToolbar = QToolBar()
        self.polyOrderLabel = QLabel("Polynomial order")
        self.polyToolbar.addWidget(self.polyOrderLabel)
        self.PolyOrderSpinBox = QSpinBox()
        self.PolyOrderSpinBox.setRange(0, 99)
        self.polyToolbar.addWidget(self.PolyOrderSpinBox)
        self.polyToolbar.addSeparator()
        self.exitCriteriaLineEditLabel = QLabel()
        self.exitCriteriaLineEditLabel.setText("Exit criteria")
        self.polyToolbar.addWidget(self.exitCriteriaLineEditLabel)
        self.exitCriteriaLineEdit = QLineEdit()
        self.exitCriteriaLineEdit.setInputMask("0e-0")
        self.exitCriteriaLineEdit.setText("1e-3")
        self.polyToolbar.addWidget(self.exitCriteriaLineEdit)
        # Making the toolbar invisible by default.
        self.polyToolbar.setVisible(False)
        #self.addToolBar(self.polyToolbar)
        self.lineTabWidgetLayout.addWidget(self.polyToolbar)

        # PSSpline airPLS
        self.airplsToolbar = QToolBar()
        self.airplsSmoothingLabel = QLabel()
        self.airplsSmoothingLabel.setText("Smoothing")
        self.airplsToolbar.addWidget(self.airplsSmoothingLabel)
        self.airplsSmoothingVal = QLineEdit()
        self.airplsSmoothingVal.setInputMask("0e0")
        self.airplsSmoothingVal.setText("1e3")
        self.airplsToolbar.addWidget(self.airplsSmoothingVal)
        self.airplsToolbar.addSeparator()
        self.knotsSpinBoxLabel = QLabel()
        self.knotsSpinBoxLabel.setText("Knots n.")
        self.airplsToolbar.addWidget(self.knotsSpinBoxLabel)
        self.knotsSpinBox = QSpinBox()
        self.knotsSpinBox.setRange(2,999)
        self.knotsSpinBox.setValue(100)
        self.airplsToolbar.addWidget(self.knotsSpinBox)
        self.splineSpinBoxLabel = QLabel()
        self.splineSpinBoxLabel.setText("Spline degree")
        self.airplsToolbar.addWidget(self.splineSpinBoxLabel)
        self.splineSpinBox = QSpinBox()
        self.splineSpinBox.setRange(1,999)
        self.splineSpinBox.setValue(3)
        self.airplsToolbar.addWidget(self.splineSpinBox)
        self.diffOrderSpinBoxLabel = QLabel()
        self.diffOrderSpinBoxLabel.setText("Differential order")
        self.airplsToolbar.addWidget(self.diffOrderSpinBoxLabel)
        self.diffOrderSpinBox = QSpinBox()
        self.diffOrderSpinBox.setRange(1,99)
        self.diffOrderSpinBox.setValue(2)
        self.airplsToolbar.addWidget(self.diffOrderSpinBox)
        self.maxIterSpinBoxLabel = QLabel()
        self.maxIterSpinBoxLabel.setText("Max. iter.")
        self.airplsToolbar.addWidget(self.maxIterSpinBoxLabel)
        self.maxIterSpinBox = QSpinBox()
        self.maxIterSpinBox.setRange(1,9999)
        self.maxIterSpinBox.setValue(50)
        self.airplsToolbar.addWidget(self.maxIterSpinBox)
        self.exitCriteriaPSPLineEditLabel = QLabel()
        self.exitCriteriaPSPLineEditLabel.setText("Exit criteria")
        self.airplsToolbar.addWidget(self.exitCriteriaPSPLineEditLabel)
        self.exitCriteriaPSPLineEdit = QLineEdit()
        self.exitCriteriaPSPLineEdit.setInputMask("0e-0")
        self.exitCriteriaPSPLineEdit.setText("1e-3")
        self.airplsToolbar.addWidget(self.exitCriteriaPSPLineEdit)
        # Making the toolbar invisible by default.
        self.airplsToolbar.setVisible(False)
        #self.addToolBar(self.airplsToolbar)
        self.lineTabWidgetLayout.addWidget(self.airplsToolbar)

        
        #self.show()

        ################################################
        self.q = q
        #self.plotThread = mainPlotThread(q=self.q, plot=self.plot, ax1=self.plot.ax1, ax2=self.plot.ax2, fig=self.plot.fig)
        #self.plotThread = mainPlotThread(q=self.q, plot=self.plot, parent=self)
        #self.plotThread.start()
        #else:
        #    print("[mainPlotSubWindow] Unrecognized plot type")

        self.plotThread = spectrumPlotThread(q= self.q, parent=self)
        self.plotThread.update.connect(self.plotData)
        #self.plotThread.update.connect(self.updatePlot)
        self.plotThread.start()

        # General graphics rules (background color, plot line color, etc.)
        self.backgroundColor = "#1E2529"
        self.plotColor = "#2F3133"
        #self.plotColor = "#1E2529"
        self.lineColor = "#3399ff"
        self.lineColor2 = "#ff7f0e"
        
        #--------------------------------------
        # Preparing spectrum plot
        #--------------------------------------
        #self.plot = mainPlotCanvas(self.q)
        self.plotSpectrumCanvas = pg.GraphicsLayoutWidget()
        self.plotSpectrumCanvas.setBackground(self.backgroundColor)
        #self.setCentralWidget(self.plotSpectrumCanvas)
        self.lineTabWidgetLayout.addWidget(self.plotSpectrumCanvas)

        self.subPlot1 = self.plotSpectrumCanvas.addPlot(row=0, col=0)
        self.subPlot2 = self.plotSpectrumCanvas.addPlot(row=1, col=0)

        #self.subPlot1.setLabel("bottom", "Raman shift", "cm<sup>-1</sup>")
        #self.subPlot2.setLabel("bottom", "Raman shift", "cm<sup>-1</sup>")
        self.subPlot1.setLabel("bottom", "Wavelength", "nm")
        self.subPlot2.setLabel("bottom", "Wavelength", "nm")

        self.subPlot1.setLabel("left", "Intensity", "")
        self.subPlot2.setLabel("left", "Intensity", "")

        self.axRight1 = self.subPlot1.getAxis("right")
        self.axRight2 = self.subPlot2.getAxis("right")

        self.axBottom1 = self.subPlot1.getAxis("bottom")
        self.axBottom2 = self.subPlot2.getAxis("bottom")
        # Disabling automatic unit scaling (kilo, mega, ...) of x axis
        self.axBottom1.enableAutoSIPrefix(enable=False)
        self.axBottom2.enableAutoSIPrefix(enable=False)

        self.subPlotPen1 = pg.mkPen(color=self.lineColor, width=2)
        self.subPlotPen2 = pg.mkPen(color=self.lineColor, width=2)
        self.subPlotPen3 = pg.mkPen(color=self.lineColor2, width=1)
        
        self.subPlot1DataHandle = self.subPlot1.plot(pen=self.subPlotPen1)
        self.subPlot1DataHandle2 = self.subPlot1.plot(pen=self.subPlotPen3)
        
        self.subPlot2DataHandle = self.subPlot2.plot(pen=self.subPlotPen2)


        ########################################################
        # Plugging callbacks to buttons from the parent window.
        ########################################################
        self.smoothingSpinBox.valueChanged.connect(self.updatePlot)

        self.PolyOrderSpinBox.valueChanged.connect(self.updatePlot)
        self.exitCriteriaLineEdit.editingFinished.connect(self.updatePlot)

        self.airplsSmoothingVal.editingFinished.connect(self.updatePlot)
        self.knotsSpinBox.valueChanged.connect(self.updatePlot)
        self.splineSpinBox.valueChanged.connect(self.updatePlot)
        self.diffOrderSpinBox.valueChanged.connect(self.updatePlot)
        self.maxIterSpinBox.valueChanged.connect(self.updatePlot)
        self.exitCriteriaPSPLineEdit.editingFinished.connect(self.updatePlot)

        self.baselineCorrectionCBox.currentTextChanged.connect(self.switchToolbar)

        #-----------------------------------------
        # Preparing image plot
        #-----------------------------------------

        # Interpret image data as row-major instead of col-major
        pg.setConfigOptions(imageAxisOrder='row-major')
        # Replacing the central image plot with a plot item to have support for axis ranges
        self.imagePlotItem = pg.PlotItem()
        self.plotImageCanvas = pg.ImageView(view=self.imagePlotItem)
        self.imageTabWidgetLayout.addWidget(self.plotImageCanvas)

        # Adjusting colours of different elements
        # Image view 
        self.imagePlotItem.getViewBox().setBackgroundColor("#000000")
        # Histogram view
        self.plotImageHistogram = self.plotImageCanvas.getHistogramWidget()
        self.plotImageHistogram.setBackground(self.backgroundColor)
        # ROI plot
        self.plotImageROIplot = self.plotImageCanvas.getRoiPlot()
        self.plotImageROIplot.setBackground(self.backgroundColor)

        self.imageView = self.plotImageCanvas.getView()

    def plotData(self,data):
        self.data = data

        if self.data["type"] == "image":
            self.tab.setCurrentIndex(1)

            print(f"INCOMING DATA SHAPE: {np.shape(data['data'])}")
            print(f"ndim: {data['data'].ndim}")

            #if np.shape(data["data"])[1] == 1:
            if data["data"].ndim == 1:
                print(f"[mainPlotSubWindow/plotData] Data arrived 1D, reshaping to 2D using xpixels: {data['xpixels']} and ypixels: {data['ypixels']}")
                data["data"] = np.reshape(a=data["data"], newshape=(data["ypixels"], data["xpixels"]))

            self.plotImageCanvas.setImage(data["data"], xvals=data["dataX"],)

        elif self.data["type"] == "spectrum":

            self.tab.setCurrentIndex(0)

            print(f"[mainCanvas/run] Receiving spectral data.")
            self.subPlot1.clear()
            self.subPlot1DataHandle.setData(self.data["dataX"], self.data["dataY"])
            self.subPlot1.addItem(self.subPlot1DataHandle)

            # Updating title
            self.subPlot1.setLabel("top", self.data["title"])
            self.updatePlot()

        else:
            # Something is wrong. Printing message.
            print(f"[mainPlotThread] Error occured. Wrong data type.")

    def updatePlot(self):       

        print("[plotSettings] Updating plot")
        newSmoothingValue = self.smoothingSpinBox.value()
        print(f"[loadPlotSettings] Value of smoothing is updated to {newSmoothingValue}.")

        #if self.plotType == "spectrum":
        if self.data["type"] == "image":
            # This is where we should process image data.
            print("[] Image plotting is not yet implemented.")

        
        if newSmoothingValue == 0 or newSmoothingValue == 1:
            #self.ax2.set_title("Processed data, no smoothing")
            self.subPlot2.setLabel("top", "Processed data, no smoothing")
            
            dataX = self.data["dataX"]
            dataY = self.data["dataY"]

        else:
            self.subPlot2.setLabel("top", f"Processed data, smoothing window: {newSmoothingValue}")
            dataY = self.smooth(self.data["dataY"], newSmoothingValue)
            # Removing boundary conditions.
            dataY = dataY[int(newSmoothingValue/2):-int(newSmoothingValue/2)]
            dataX = self.data["dataX"][int(newSmoothingValue/2):-int(newSmoothingValue/2)]

        baseline_fitter = pb.Baseline(dataX, check_finite=False)

        # Updating baseline correction
        if self.baselineCorrectionCBox.currentText() == "Polynomial correction":
            print(f"[updatePlot] Implementing modified polynomial order: {self.PolyOrderSpinBox.value()}, exit criteria : {float(self.exitCriteriaLineEdit.text())}.")
            background = baseline_fitter.modpoly(dataY, 
                                                 poly_order = self.PolyOrderSpinBox.value(), 
                                                 tol = float(self.exitCriteriaLineEdit.text()))[0]
            
            dataY = dataY - background

            # Plotting baseline correction 
            self.subPlot1DataHandle2.setData(dataX, background)
            self.subPlot1.addItem(self.subPlot1DataHandle2)

        elif self.baselineCorrectionCBox.currentText() == "PSspline airPLS":
            print("[updatePlot] Implementing PSSpline AIRPLS.")
            background = baseline_fitter.pspline_airpls(dataY, 
                                                        lam = float(self.airplsSmoothingVal.text()),
                                                        num_knots = self.knotsSpinBox.value(),
                                                        spline_degree = self.splineSpinBox.value(),
                                                        max_iter = self.maxIterSpinBox.value(),
                                                        diff_order = self.diffOrderSpinBox.value(),
                                                        tol = float(self.exitCriteriaPSPLineEdit.text()))[0]
            
            dataY = dataY - background

            # Plotting baseline correction 
            self.subPlot1DataHandle2.setData(dataX, background)
            self.subPlot1.addItem(self.subPlot1DataHandle2)

        else:
            # Clearing baseline from the plot by clearing it and replotting data.
            self.subPlot1.clear()
            self.subPlot1DataHandle.setData(self.data["dataX"], self.data["dataY"])
            self.subPlot1.addItem(self.subPlot1DataHandle)

        # Plotting
        self.subPlot2.clear()
        self.subPlot2DataHandle.setData(dataX, dataY)
        self.subPlot2.addItem(self.subPlot2DataHandle)

    def smooth(self, y, box_pts):
        box = np.ones(box_pts) / box_pts
        y_smooth = np.convolve(y, box, mode="same")
        
        return y_smooth

    def switchToolbar(self):
        baselineMethod = self.baselineCorrectionCBox.currentText()

        if baselineMethod == "No baseline correction":
            self.polyToolbar.setVisible(False)
            self.airplsToolbar.setVisible(False)
        elif baselineMethod == "Polynomial correction":
            self.polyToolbar.setVisible(True)
            self.airplsToolbar.setVisible(False)
        elif baselineMethod == "PSspline airPLS":
            self.polyToolbar.setVisible(False)
            self.airplsToolbar.setVisible(True)
        else:
            print(f"[mainCanvas/switchToolbar] Smoothing method not recognized : {baselineMethod}")
        
        # Running a plot update to enact the current selection
        self.updatePlot()

    def stop(self):
        self.self.plotThread.stop()


class spectrumPlotThread(QThread):
    # This thread handles updating plots when data is send from the acquisition thread. 
    # It also contains plot processing functions such as Weiner smoothing and baseline correction
    update = pyqtSignal(dict)

    def __init__(self, q, parent):
        super().__init__()
        print("[spectrumPlotThread] Thread initialized.")
        self.q = q
        self.parent = parent

    def run(self):
        while True:
            self.messageDict = self.q.get()

            #print(f"[spectrumPlotThread] {self.messageDict}")

            self.update.emit(self.messageDict)

    def stop(self):
        try:
            self.task.close()
        except:
            print("[windowThread/stop] No task to close.")
        
        print("[windowThread/stop] Called the stop function.")
        print("[windowThread/stop] Requesting interruption of the wait function.")
        self.windowThread.requestInterruption()
        self.delayQueue.put("Stop")
        time.sleep(0.1)
        self.exit()
        #self.quit()
        time.sleep(0.1) 
        

class mainPlotThread(QThread):
    # This thread handles updating plots when data is send from the acquisition thread. 
    # It also contains plot processing functions such as Weiner smoothing and baseline correction
    def __init__(self, q, plot, parent):
        super().__init__()
        print("[windowThread] Thread initialized.")
        self.q = q
        self.ax1 = plot.ax1
        self.ax2 = plot.ax2
        self.fig = plot.fig
        #self.setParent(parent)
        self.parent = parent

        self.lineColor = "#3399ff"

        # Holds information about the plot type to be passed to the plotting thread.
        # Plot is initiated with random image (heatmap)
        self.plotType = "image"

        ########################################################
        # Plugging callbacks to buttons from the parent window.
        ########################################################
        self.parent.smoothingSpinBox.valueChanged.connect(self.updatePlot)

        self.parent.PolyOrderSpinBox.valueChanged.connect(self.updatePlot)
        self.parent.exitCriteriaLineEdit.editingFinished.connect(self.updatePlot)

        self.parent.airplsSmoothingVal.editingFinished.connect(self.updatePlot)
        self.parent.knotsSpinBox.valueChanged.connect(self.updatePlot)
        self.parent.splineSpinBox.valueChanged.connect(self.updatePlot)
        self.parent.diffOrderSpinBox.valueChanged.connect(self.updatePlot)
        self.parent.maxIterSpinBox.valueChanged.connect(self.updatePlot)
        self.parent.exitCriteriaPSPLineEdit.editingFinished.connect(self.updatePlot)

        self.parent.baselineCorrectionCBox.currentTextChanged.connect(self.switchToolbar)

    def run(self):
        while True:
            #self.messageDict = self.q.get()
            #time.sleep(0.5)
            self.messageDict = self.q.get()
            
            #print(f"[windowThread] message: {self.messageDict}")
            if self.messageDict["type"] == "image":
                print(f"[mainCanvas/run] Receiving image data.")
                self.ax1.clear()
                # Reshaping data 
                data = self.messageDict["data"].reshape(self.messageDict["ypixels"], self.messageDict["xpixels"])
                # We need to transpose data to have rows horizontal. 
                #data = np.transpose(data)
                #print(f"[mainPlotThread/run] Incoming message : {self.messageDict}")
                self.heatmap = sns.heatmap(data, linewidth=0, cbar=False, cmap ="viridis", ax=self.ax1)
                self.ax1.title.set_text(self.messageDict["title"])
                self.fig.canvas.draw()
            elif self.messageDict["type"] == "spectrum":
                print(f"[mainPlotThread] Entering the spectrum option.")
                print(f"[mainCanvas/run] Receiving spectral data.")
                self.ax1.clear()
                self.ax2.clear()
                self.ax1.title.set_text(self.messageDict["title"])
                self.line1, = self.ax1.plot(self.messageDict["dataX"], self.messageDict["dataY"])
                self.line2, = self.ax2.plot(self.messageDict["dataX"], self.messageDict["dataY"])
                self.fig.canvas.draw()
            else:
                # Something is wrong. Printing message.
                print(f"[mainPlotThread] Error occured. Wrong image type.")
                #print(f"[mainPlotThread] queue content: {self.messageDict}")            
            
            self.updatePlot()

    def switchToolbar(self):
        baselineMethod = self.parent.baselineCorrectionCBox.currentText()

        if baselineMethod == "No baseline correction":
            self.parent.polyToolbar.setVisible(False)
            self.parent.airplsToolbar.setVisible(False)
        elif baselineMethod == "Polynomial correction":
            self.parent.polyToolbar.setVisible(True)
            self.parent.airplsToolbar.setVisible(False)
        elif baselineMethod == "PSspline airPLS":
            self.parent.polyToolbar.setVisible(False)
            self.parent.airplsToolbar.setVisible(True)
        else:
            print(f"[mainCanvas/switchToolbar] Smoothing method not recognized : {baselineMethod}")
        
        # Running a plot update to enact the current selection
        self.updatePlot()
    
    def updatePlot(self):
        print("[plotSettings] Updating plot")
        newSmoothingValue = self.parent.smoothingSpinBox.value()
        print(f"[loadPlotSettings] Value of smoothing is updated to {newSmoothingValue}.")

        #if self.plotType == "spectrum":
        if self.messageDict["type"] == "spectrum":
            print(f"[mainCanvas/updatePlot] updating spectral data")
            # Getting original data from the 1st plot
            dataX = self.line1.get_xdata()
            dataY = self.line1.get_ydata()
            self.lineColor = self.line1.get_color()
            labelX = self.ax1.get_xlabel()
            labelY = self.ax1.get_ylabel()
            title = self.ax1.title.get_text()
        elif self.messageDict["type"] == "image":
            print(f"[mainCanvas/updatePlot] updating image data")
        #elif self.plotType == "image":
            data = np.array(self.ax1.collections[-1].get_array())
            #print(f"[mainCanvas/updatePlot] Properties : {self.ax1.collections[-1].properties()}")
            #self.xaxisRange = int(self.ax1.collections[-1].properties()["xaxis"].get_data_interval()[1])
            #self.yaxisRange = int(self.ax1.collections[-1].properties()["yaxis"].get_data_interval()[1])
            data = self.ax1.collections[-1].properties()["array"]
            #print(f"[mainCanvas/updatePlot] Array : {data}")
            #data = data.reshape((self.xaxisRange, self.yaxisRange))
            dataY = np.sum(data, axis=0)
            dataX = range(0, len(dataY))
            labelX = self.ax1.get_xlabel() 
            labelY =self.ax2.get_ylabel()
            title = self.ax1.title.get_text()

        # Updating smoothing value
        if newSmoothingValue == 0:
            self.ax2.set_title("Processed data, no smoothing")
        else:
            self.ax2.set_title("Processed data, Weiner smoothing")
            dataY = wiener(dataY, newSmoothingValue)
            print(dataY)
            print(dataY[10:])
            dataY = dataY[10:]
            dataX = dataX[10:]
        
        baseline_fitter = pb.Baseline(dataX, check_finite=False)
        # Updating baseline correction
        if self.parent.baselineCorrectionCBox.currentText() == "Polynomial correction":
            print(f"[updatePlot] Implementing modified polynomial order: {self.parent.PolyOrderSpinBox.value()}, exit criteria : {float(self.parent.exitCriteriaLineEdit.text())}.")
            background = baseline_fitter.modpoly(dataY, 
                                                 poly_order = self.parent.PolyOrderSpinBox.value(), 
                                                 tol = float(self.parent.exitCriteriaLineEdit.text()))[0]
            
            dataY = dataY - background
        elif self.parent.baselineCorrectionCBox.currentText() == "PSspline airPLS":
            print("[updatePlot] Implementing PSSpline AIRPLS.")
            background = baseline_fitter.pspline_airpls(dataY, 
                                                        lam = float(self.parent.airplsSmoothingVal.text()),
                                                        num_knots = self.parent.knotsSpinBox.value(),
                                                        spline_degree = self.parent.splineSpinBox.value(),
                                                        max_iter = self.parent.maxIterSpinBox.value(),
                                                        diff_order = self.parent.diffOrderSpinBox.value(),
                                                        tol = float(self.parent.exitCriteriaPSPLineEdit.text()))[0]
            
            dataY = dataY - background

        self.ax1.title.set_text(title)
        self.ax2.title.set_text(f"Smoothed and baseline corrected with {self.parent.baselineCorrectionCBox.currentText()}")
        self.ax2.clear()
        self.line2, = self.ax2.plot(dataX, dataY)
        self.line2.set_color(self.lineColor)
        _ = self.ax2.set_xlabel(labelX)
        _ = self.ax2.set_ylabel(labelY)
        #self.line2, = self.ax2.plot(dataX, dataY)

        self.fig.canvas.draw()

    def stop(self):
        try:
            self.task.close()
        except:
            print("[windowThread/stop] No task to close.")
        
        print("[windowThread/stop] Called the stop function.")
        print("[windowThread/stop] Requesting interruption of the wait function.")
        self.windowThread.requestInterruption()
        self.delayQueue.put("Stop")
        time.sleep(0.1)
        self.exit()
        #self.quit()
        time.sleep(0.1) 

"""
class mainPlotCanvas(FigureCanvasQTAgg):
    # This is a matplotlib canvas backend for QT. Matplotlib figure is started here and 
    # its handle is subsequently passed to the plot thread to update with new incoming 
    # data and post-processing.
    def __init__(self, q):
        
        #exitAction = QAction('Exit', self)        
        #exitAction.triggered.connect(QtGui.qApp.quit)
        #exitMenu.addAction(exitAction)
        ###############################
        # Matplotlib script
        ###############################
        plt.rcParams['ytick.color'] = "#ffffff" 
        plt.rcParams['xtick.color'] = "#ffffff"
        plt.rcParams['axes.labelcolor'] = "#ffffff"
        plt.rcParams['text.color'] = "#ffffff"

        self.backgroundColor = "#1E2529"
        self.plotColor = "#2F3133"
        #self.plotColor = "#1E2529"
        self.lineColor = "#3399ff"

        self.fig, (self.ax1, self.ax2) = plt.subplots(nrows=2, ncols=1, figsize=(3,3), dpi=100, facecolor=self.backgroundColor)
        self.ax1.set_facecolor(self.plotColor)
        self.ax2.set_facecolor(self.plotColor)
        self.fig.tight_layout(pad=1)
        super().__init__(self.fig)

        a = np.random.random((16, 64))
        heatmap = sns.heatmap(a, linewidth=0, cbar=False, cmap ="viridis", ax=self.ax1)
        self.ax1.set(xlabel = "X", ylabel = "Y", title = "Acquired image")

        b = np.sum(a, axis=0)
        #plt.plot(list(range(0, len(b))), b)
        self.ax2.set(xlabel = "X", ylabel = "Y", title = "Full vertical binning")
        self.line, = self.ax2.plot(range(0, len(b)), b, '-')

        self.plotType = "heatmap""
"""

###################################################
# DAQ plot
###################################################

class daqPlotThread(QThread):
    # TODO: This class is probably entirely obsolete now. 
    update = pyqtSignal(list)

    def __init__(self, q, parent):
        
        super().__init__()
        print("[windowThread] DAQ plot thread initialized.")
        self.q = q
        self.parent = parent

        self.oldThresholdValue = -1000 # placeholder threshold value

    def run(self):
        while True:
            #time.sleep(0.5)
            self.messageDict = self.q.get()
            
            #print(f"[daqPlotThread] message : {self.messageDict}")
            #self.linkPeaks()
            #print(self.messageDict["dataArray"][:,0:9])
            #self.thresholdValue = self.messageDict["thresholdValue"]
            #for row in range(0, self.messageDict["dataArray"].shape[0]):
                #self.parent.lines[row].set_ydata(self.messageDict["dataArray"][row])
            
            #self.parent.h1.setData(self.messageDict["data array"][0])
            #self.parent.h2.setData(self.messageDict["data array"][1])
            if "warning" in self.messageDict.keys():
                # Warning due to too many peaks
                self.update.emit([self.messageDict["warning"],
                                  self.messageDict["data"]],
                                  self.messageDict["peakTimes"],
                                  self.messageDict["peakBoundaries"],
                                  [[],[],[]])  # Peak intensities
            else:
                updateMessage = ["data is ok", self.messageDict["data"], self.messageDict["peaks"], self.messageDict["peakTimes"],self.messageDict["peakBoundaries"]]

                self.update.emit(updateMessage)
            
    def stop(self):
        try:
            self.task.close()
        except BaseException as e:
            print(f"[windowThread/stop] Error while closing the thread: {e}")
        
        print("[windowThread/stop] Called the stop function.")
        print("[windowThread/stop] Requesting interruption of the wait function.")
        self.windowThread.requestInterruption()
        self.delayQueue.put("Stop")
        time.sleep(0.1)
        self.exit()
        #self.quit()
        time.sleep(0.1) 


class daqPlotSubWindow(QMainWindow):
    thresholdSignal = pyqtSignal(int, float)
    plotDownsamplingSignal = pyqtSignal(int)
    def __init__(self, parent, q, nchannels):
        self.q = q
        self.parent = parent
        self.nchannels = nchannels
        super().__init__()

        # Data for speed plot
        self.speedData = np.array([[],[]])

        ###############################
        #Matplotlib script
        ###############################
        plt.rcParams['ytick.color'] = "#ffffff" 
        plt.rcParams['xtick.color'] = "#ffffff"
        plt.rcParams['axes.labelcolor'] = "#ffffff"
        plt.rcParams['text.color'] = "#ffffff"

        self.backgroundColor = "#1E2529"
        self.plotColor = "#2F3133"
        #self.plotColor = "#1E2529"
        self.lineColor = "#3399ff"
        self.lineColor1 = "#1f77b4"
        self.peakColor1 = "#aec7e8"
        self.peakColor1invisible = "#aec7e800"
        self.lineColor2 = "#ff7f0e"
        self.peakColor2 = "#ffbb78"
        self.peakColor2invisible = "#ffbb7800"
        self.lineColor3 = "#2ca02c"
        self.peakColor3 = "#80c680"
        self.peakColor3invisible = "#80c68000"
        self.pointColor = "#d62728"
        ####################################
        # Toolbars
        ####################################
        # Collecting minimum and maximum of the Y axisd
        self.minYvalues = []
        self.maxYvalues = []
        #self.minYvalues = [self.ymin1.value(), self.ymin2.value(), self.ymin3.value()]
        #self.maxYvalues = [self.ymax1.value(), self.ymax2.value(), self.ymax3.value()]

        # Toolbar 1
        toolbar1 = QToolBar()
        # Toolbar title
        self.label1 = QLabel()
        self.label1.setText(f"Plot 1")
        toolbar1.addWidget(self.label1)
        toolbar1.addSeparator()
        # Toggle view action
        toggleView1 = toolbar1.toggleViewAction()
        toggleView1.setText("Hide toolbar")
        toolbar1.addWidget(QLabel("Y min"))
        # Spin boxes for axis adjustment
        self.ymin1 = QDoubleSpinBox()
        self.ymin1.setDecimals(3)
        self.ymin1.setRange(-999, 999)
        toolbar1.addWidget(self.ymin1)
        toolbar1.addSeparator()
        toolbar1.addWidget(QLabel("Y max"))
        self.ymax1 = QDoubleSpinBox()
        self.ymax1.setDecimals(3)
        self.ymax1.setRange(-999, 999)
        toolbar1.addWidget(self.ymax1)
        self.addToolBar(toolbar1)
        toolbar1.addSeparator()
        # Spin box for treshold
        toolbar1.addWidget(QLabel("Treshold")) 
        self.threshold1 = QDoubleSpinBox()
        self.threshold1.setRange(-999,999)
        self.threshold1.setValue(10)
        self.threshold1.setDecimals(3)
        toolbar1.addWidget(self.threshold1)
        self.addToolBarBreak()

        self.ymin1.valueChanged.connect(lambda: self.updateAxisLimits(1))
        self.ymax1.valueChanged.connect(lambda: self.updateAxisLimits(1))
        self.threshold1.valueChanged.connect(lambda: self.updateYAxis(1))

        self.minYvalues.append(self.ymin1)
        self.maxYvalues.append(self.ymax1)
        
        if self.nchannels >= 2:
            # Toolbar 2
            toolbar2 = QToolBar()
            # Toolbar title
            self.label2 = QLabel()
            self.label2.setText(f"Plot 2")
            toolbar2.addWidget(self.label2)
            toolbar2.addSeparator()
            # Toggle view action
            toggleView2 = toolbar2.toggleViewAction()
            toggleView2.setText("Hide toolbar")
            toolbar2.addWidget(QLabel("Y min"))
            # Spin boxes for axis adjustment
            self.ymin2 = QDoubleSpinBox()
            self.ymin2.setDecimals(3)
            self.ymin2.setRange(-999, 999)
            toolbar2.addWidget(self.ymin2)
            toolbar2.addSeparator()
            toolbar2.addWidget(QLabel("Y max"))
            self.ymax2 = QDoubleSpinBox()
            self.ymax2.setDecimals(3)
            self.ymax2.setRange(-999, 999)
            toolbar2.addWidget(self.ymax2)
            self.addToolBar(toolbar2)
            toolbar2.addSeparator()
            # Spin box for treshold
            toolbar2.addWidget(QLabel("Treshold")) 
            self.threshold2 = QDoubleSpinBox()
            self.threshold2.setRange(-999,999)
            self.threshold2.setValue(10)
            self.threshold2.setDecimals(3)
            toolbar2.addWidget(self.threshold2)
            self.addToolBarBreak()

            self.ymin2.valueChanged.connect(lambda: self.updateAxisLimits(2))
            self.ymax2.valueChanged.connect(lambda: self.updateAxisLimits(2))
            self.threshold2.valueChanged.connect(lambda: self.updateYAxis(2))

            self.minYvalues.append(self.ymin2)
            self.maxYvalues.append(self.ymax2)
        
        if self.nchannels >= 3:
            # Toolbar 3
            toolbar3 = QToolBar()
            # Toolbar title
            self.label3 = QLabel()
            self.label3.setText(f"Plot 3")
            toolbar3.addWidget(self.label3)
            toolbar3.addSeparator()
            # Toggle view action
            toggleView3 = toolbar3.toggleViewAction()
            toggleView3.setText("Hide toolbar")
            toolbar3.addWidget(QLabel("Y min"))
            # Spin boxes for axis adjustment
            self.ymin3 = QDoubleSpinBox()
            self.ymin3.setDecimals(3)
            self.ymin3.setRange(-999, 999)
            toolbar3.addWidget(self.ymin3)
            toolbar3.addSeparator()
            toolbar3.addWidget(QLabel("Y max"))
            self.ymax3 = QDoubleSpinBox()
            self.ymax3.setDecimals(3)
            self.ymax3.setRange(-999, 999)
            toolbar3.addWidget(self.ymax3)
            self.addToolBar(toolbar3)
            toolbar3.addSeparator()
            # Spin box for treshold
            toolbar3.addWidget(QLabel("Treshold")) 
            self.threshold3 = QDoubleSpinBox()
            self.threshold3.setRange(-999,999)
            self.threshold3.setValue(10)
            self.threshold3.setDecimals(3)
            toolbar3.addWidget(self.threshold3)
            self.addToolBarBreak()

            self.ymin3.valueChanged.connect(lambda: self.updateAxisLimits(3))
            self.ymax3.valueChanged.connect(lambda: self.updateAxisLimits(3))
            self.threshold3.valueChanged.connect(lambda: self.updateYAxis(3))

            self.minYvalues.append(self.ymin3)
            self.maxYvalues.append(self.ymax3)

            # Toolbar 4
            toolbar4 = QToolBar()
            # Toolbar title
            self.label4 = QLabel()
            self.label4.setText(f"Plot 4")
            toolbar4.addWidget(self.label4)
            toolbar4.addSeparator()
            # Toggle view action
            toggleView4 = toolbar4.toggleViewAction()
            toggleView4.setText("Hide toolbar")
            toolbar4.addWidget(QLabel("Y min"))
            # Spin boxes for axis adjustment
            self.ymin4 = QDoubleSpinBox()
            self.ymin4.setDecimals(3)
            self.ymin4.setRange(-999, 999)
            self.ymin4.setToolTip("Sets y axis minimum")
            toolbar4.addWidget(self.ymin4)
            toolbar4.addSeparator()
            toolbar4.addWidget(QLabel("Y max"))
            self.ymax4 = QDoubleSpinBox()
            self.ymax4.setDecimals(3)
            self.ymax4.setRange(-999, 999)
            self.ymax4.setToolTip("Sets y axis maximum")
            toolbar4.addWidget(self.ymax4)
            toolbar4.addSeparator()
            toolbar4.addWidget(QLabel("X range"))
            self.displayRange = QDoubleSpinBox()
            self.displayRange.setDecimals(1)
            self.displayRange.setRange(0,99999)
            self.displayRange.setValue(600)
            self.displayRange.setToolTip("A displayed range of measured particle speeds in seconds")
            toolbar4.addWidget(self.displayRange)
            self.addToolBar(toolbar4)
            
            self.ymin4.valueChanged.connect(lambda: self.updateAxisLimits(4))
            self.ymax4.valueChanged.connect(lambda: self.updateAxisLimits(4))

            #self.minYvalues.append(self.ymin4)
            #self.maxYvalues.append(self.ymax4)
        

        #layout = QHBoxLayout()
        #layout.addWidget()
        #self.setLayout(layout)

        #self.plot = daqPlotCanvas(self.q, nchannels=nchannels)
        
        #### Create Gui Elements ###########
        self.mainbox = QWidget()
        self.mainbox.setLayout(QVBoxLayout())
        self.setCentralWidget(self.mainbox)
        #self.setCentralWidget(self.plot)

        self.canvas = pg.GraphicsLayoutWidget()
        self.canvas.setBackground(self.backgroundColor)
        self.mainbox.layout().addWidget(self.canvas)
        
        self.plots = []
        self.plotHandles = []

        # PlotItem class 
        self.plot1 = self.canvas.addPlot(row=0, col=0)
        self.pen1 = pg.mkPen(color=self.lineColor1, width=5)
        # Plot handle class
        self.h1 = self.plot1.plot(pen=self.pen1)

        self.plots.append(self.plot1)
        self.plotHandles.append(self.h1)

        if nchannels >= 2:
            self.plot2 = self.canvas.addPlot(row=1, col=0)
            self.pen2 = pg.mkPen(color=self.lineColor2, width=5)
            self.h2 = self.plot2.plot(pen=self.pen2)

            self.plots.append(self.plot2)
            self.plotHandles.append(self.h2)
        
        if nchannels >= 3:
            self.plot3 = self.canvas.addPlot(row=3, col=0)
            self.pen3 = pg.mkPen(color=self.lineColor3, width=5)
            self.h3 = self.plot3.plot(pen=self.pen3)
            
            self.plots.append(self.plot3)
            self.plotHandles.append(self.h3)

            # Speed data plot
            self.plot4 = self.canvas.addPlot(row=4, col=0)
            self.plot4.setTitle("Speed measurement result")
            self.plot4.setLabel("bottom", "Detection time [s]")
            self.plot4.setLabel("left", "Transit time [s]")
            
            self.pen4 = pg.mkPen(color=self.pointColor, width=5)
            self.pen4invisible = pg.mkPen(color=self.pointColor, width=5)
            self.h4 = self.plot3.plot(pen=self.pen4)

            # Creating an invisible horizontal region element
            #self.horizontalRegion = pg.LinearRegionItem([0,0], orientation="horizontal", brush=pg.mkBrush(0,0,0,0), pen=pg.mkPen(None))
            self.horizontalRegion = pg.LinearRegionItem([0.6,1.2], orientation="horizontal", movable=False, brush=pg.mkBrush("#2ca02c00"), pen=pg.mkPen("#2ca02c00"))
            self.plot4.addItem(self.horizontalRegion)

            self.peakStartTime = 0
            self.firstPeakBool = True
            #self.plots.append(self.plot4)
            #self.plotHandles.append(self.h4)
        '''
        # Scatter plot labels for peaks with prominence higher than selected by the user
        self.s1 = pg.ScatterPlotItem(size=5)
        self.s1.setSymbol("x")
        self.s1.setBrush(self.lineColor1)

        self.s2 = pg.ScatterPlotItem(size=5)
        self.s2.setSymbol("x")
        self.s2.setBrush(self.lineColor2)

        self.s3 = pg.ScatterPlotItem(size=5)
        self.s3.setSymbol("x")
        self.s3.setBrush(self.lineColor3)
        '''

        ####################################
        # Infinite lines marking peaks
        ####################################
        # Creating bank of infinite lines
        self.peakPen1 = pg.mkPen(color=self.peakColor1, width=2)
        self.peakPen1invisible = pg.mkPen(color=self.peakColor1invisible, width=1)
        self.peakPen2 = pg.mkPen(color=self.peakColor2, width=2)
        self.peakPen2invisible = pg.mkPen(color=self.peakColor2invisible, width=1)
        self.peakPen3 = pg.mkPen(color=self.peakColor3, width=2)
        self.peakPen3invisible = pg.mkPen(color=self.peakColor3invisible, width=1)

        self.peakPens = [self.peakPen1, self.peakPen2, self.peakPen3]
        self.peakPensInvisible = [self.peakPen1invisible, self.peakPen2invisible, self.peakPen3invisible]

        self.infiniteLinesPlot1 = []
        for i in range(0, 10):
            infLine = pg.InfiniteLine(movable=False, angle=90)
            infLine.setPos(0)
            infLine.setPen(self.peakPen1invisible)
            self.infiniteLinesPlot1.append(infLine)
            self.plot1.addItem(infLine)

        self.infiniteLinesPlot2 = []
        for i in range(0, 10):
            infLine = pg.InfiniteLine(movable=False, angle=90)
            infLine.setPos(0)
            infLine.setPen(self.peakPen2invisible)
            self.infiniteLinesPlot2.append(infLine)
            self.plot2.addItem(infLine)

        self.infiniteLinesPlot3 = []
        for i in range(0, 10):
            infLine = pg.InfiniteLine(movable=False, angle=90)
            infLine.setPos(0)
            infLine.setPen(self.peakPen3invisible)
            self.infiniteLinesPlot3.append(infLine),
            self.plot3.addItem(infLine)

        self.infiniteLinesPlot = [self.infiniteLinesPlot1, self.infiniteLinesPlot2, self.infiniteLinesPlot3]

        #########################################

        for plot in self.plots:
            plot.showAxes((True, False, True, True))

        for handle in self.plotHandles:
            handle.setDownsampling(auto=True, method="mean")

        #self.plot1.showAxes((True, False, True, True))
        #self.plot2.showAxes((True, False, True, True))
        #self.plot3.showAxes((True, False, True, True))
        
        #self.h1.setDownsampling(auto=True, method="mean")
        #self.h2.setDownsampling(auto=True, method="mean")
        
        self.ax = []
        for plot in self.plots:
            self.ax.append(plot.getAxis("right"))
        #self.ax = [self.plot1.getAxis("right"), ]
        #self.ax1 = self.plot1.getAxis("right")
        #self.ax2 = self.plot2.getAxis("right")

        self.plotDownsamplingSignal.connect(self.updateDownsampling)
        #self.t1 = pg.InfiniteLine(pos=self.threshold1.value(), angle=0, pen=self.pen1)
        #self.t2 = pg.InfiniteLine(pos=self.threshold2.value(), angle=0, pen=self.pen2)

        ################################################
        # Starting an acquisition thread.
        # Thread updating current pressure
        self.plotThread = daqPlotThread(q=self.q, parent=self)
        self.plotThread.update.connect(self.updatePlot)
        self.plotThread.start()

        self.show()

        #self.ymin.valueChanged.connect(self.updateAxisLimits)
        #self.ymax.valueChanged.connect(self.updateAxisLimits)

        #self.minYvalue1 = self.ymin1.value()
        #self.maxYvalue1 = self.ymax1.value()

        #self.minYvalue2 = self.ymin2.value()
        #self.maxYvalue2 = self.ymax2.value()

    def updateDownsampling(self, value):
        print(f"[daqPlotSubWindow/updateDownsampling] New downsampling: {value}")
        self.downsamplingValue = value

    def updateYAxis(self, label):
        if label == 1:
            thresholdVal = self.threshold1.value()
            self.ax[0].setTicks([[(thresholdVal,str(thresholdVal))],[]])
            self.ax[0].setStyle(tickLength=-10000)

        elif label == 2:
            thresholdVal = self.threshold2.value()
            self.ax[1].setTicks([[(thresholdVal,str(thresholdVal))],[]])
            self.ax[1].setStyle(tickLength=-10000)
        else:
            print(f"[daqPlotSubWindow/updateThresholdLine] Invalid label value : {label}")

        self.thresholdSignal.emit(label, thresholdVal)

        print(f"[daqPlotSubWindow/updateThresholdLine] Treshold: {label}, value: {thresholdVal}")        

    def updatePlot(self, data):
        # Data channel 1: data[1][0]
        # Data channel 2: data[1][1]
        # Data channel 2: data[1][2]
        # Peak list channel 1 : data[2][0]
        # Peak list channel 2 : data[2][1]
        # Peak list channel 3 : data[2][2]

        #for plot in self.plots:
        #    plot.clear()

        #print(f"[daqPlotSubWindow/updatePlot] data: {data}")
        dataStatus = data.pop(0)
        if dataStatus == "too many peaks":
            title = "Warning: Too many peaks"
            for plot in self.plots:
                plot.setTitle(title)
        else:
            title = ""
            for plot in self.plots:
                plot.setTitle(title)

        #self.h1.setData(data[0][0])
        for channel, handle in zip(data[0],self.plotHandles):                  
            handle.setData(data[0][channel].values)

        # self.plot1.addItem(self.h1)
        #for handle, plot in zip(self.plotHandles, self.plots):
        #    plot.addItem(handle)

        for peakList,plot,infiniteLines, peakPen, peakPenInvisible in zip(data[1],self.plots, self.infiniteLinesPlot, self.peakPens, self.peakPensInvisible):
            if len(peakList) > 0:
                #print(f"Peak list: {peakList}, length: {len(peakList)}")
                #y = [10]*len(peakList)
                #points = pg.ScatterPlotItem(x=peakList, y=y, pxMode = True)
                #points.setSymbol("x")
                #points.setBrush(self.lineColor1)

                #plot.addItem(points)
                for i, line in enumerate(infiniteLines):
                    if i < len(peakList):
                        line.setPos([peakList[i],peakList[i]])
                        line.setPen(peakPen)
                    else: 
                        line.setPos(0)
                        line.setPen(peakPenInvisible)

        if len(data[2].keys()) > 0:
            if self.firstPeakBool:
                # Retrieving the value of the first peak to avoid displaying whole UNIX time stamp.
                self.peakStartTime = min(data[2].keys())
                self.firstPeakBool = False
            self.plot4.clear()
            #print(f"[daqPlotSubWindow/updatePlot] Peak times: {data[2]}, peakStartTime: {self.peakStartTime}")
            for key in data[2]:
                self.speedData = np.append(self.speedData, [([key]-self.peakStartTime)*1e9, [data[2][key]*1e9]], axis=1)
            #print(f"[daqPlotSubWindow/updatePlot] speedData : {self.speedData}")

            # Trimming displayed speed data based on user input in the displayRange QDoubleSpinBox
            boolSelect = self.speedData[0] > (self.speedData[0].max() - self.displayRange.value())
            self.speedData = self.speedData[:, boolSelect]

            speedPoints = pg.ScatterPlotItem(x=self.speedData[0], y=self.speedData[1], pxMode = True)
            speedPoints.setSymbol("o")
            speedPoints.setBrush(self.pointColor)
            speedPoints.setPen(width=0)

            self.plot4.addItem(speedPoints)
            self.plot4.addItem(self.horizontalRegion)

        bounaryInfoDict = data[3]
        if bounaryInfoDict["Upper boundary active"]:
            self.horizontalRegion.setBounds([bounaryInfoDict["Lower boundary value"], bounaryInfoDict["Upper boundary value"]])
            self.horizontalRegion.setBrush(pg.mkBrush("#2ca02c33"))
        
        if bounaryInfoDict["Lower boundary active"]:
            self.horizontalRegion.setBounds([bounaryInfoDict["Lower boundary value"], bounaryInfoDict["Upper boundary value"]])
            self.horizontalRegion.setBrush(pg.mkBrush("#2ca02c33"))


        if not (bounaryInfoDict["Upper boundary active"] or bounaryInfoDict["Lower boundary active"]):
            # If both boundaries inactive, make element invisible
            self.horizontalRegion.setBrush(pg.mkBrush("#2ca02c00"))



        '''
        if len(data[4]) != 0: 
            self.point1 = pg.ScatterPlotItem(x=data[2], y=data[4]*1.1, pxMode = True)
            self.point1.setSymbol("x")
            self.point1.setBrush(self.lineColor1)
            
            self.plot1.addItem(self.point1)
        
        if len(data[5]) != 0:
            self.point2 = pg.ScatterPlotItem(x=data[3], y=data[5]*1.1, pxMode = True)
            self.point2.setSymbol("x")
            self.point2.setBrush(self.lineColor2)

            self.plot2.addItem(self.point2)
        '''

    def closeEvent(self, event):
        event.ignore()
        print("[daqPlotSubWindow] Closing event triggered.")
        self.parent.daqThread.stop()
        self.stop()
        time.sleep(1)
        event.accept()

    def updateAxisLimits(self, value):
        match value:
            case 1:
                self.plot1.setYRange(float(self.ymin1.value()), float(self.ymax1.value()))
            case 2:
                self.plot2.setYRange(float(self.ymin2.value()), float(self.ymax2.value()))
            case 3:
                self.plot3.setYRange(float(self.ymin3.value()), float(self.ymax3.value()))
            case 4:
                self.plot4.setYRange(float(self.ymin4.value()), float(self.ymax4.value()))
        
    def stop(self):
        try:
            self.close()
        except BaseException as e:
            print(f"[daqPlotSubWindow/stop] Error while closing the thread: {e}")
        for plot in self.plots:
            plot.close()
        #self.plot1.close()
        #self.plot2.close()

        time.sleep(0.1)
        self.close()
        time.sleep(0.1) 
'''
class daqPlotCanvas(FigureCanvasQTAgg):
    def __init__(self, q, nchannels):
        self.q = q

        print(f"[daqPlotCanvas] number of channels: {nchannels}")

        ###############################
        #Matplotlib script
        ###############################
        plt.rcParams['ytick.color'] = "#ffffff" 
        plt.rcParams['xtick.color'] = "#ffffff"
        plt.rcParams['axes.labelcolor'] = "#ffffff"
        plt.rcParams['text.color'] = "#ffffff"

        self.backgroundColor = "#1E2529"
        self.plotColor = "#2F3133"
        #self.plotColor = "#1E2529"
        self.lineColor = "#3399ff"

        self.fig, self.ax = plt.subplots(nrows=1, ncols=1, figsize=(3,3), dpi=100, facecolor=self.backgroundColor)
        self.ax.set_facecolor(self.plotColor)
        self.ax.set_facecolor(self.plotColor)
        self.fig.tight_layout(pad=1)

        # Threshold line
        self.axhline = self.ax.axhline(y = 1,   # Placeholder value 
                                       color=self.lineColor , 
                                       linestyle="-")
        
        super().__init__(self.fig)
        
        x = list(range(0,10000))
        y = np.zeros(10000)

        #self.line1, = self.ax.plot(x, , 'b-', color=plotColor)
        self.lines = []
        for i in range(0, nchannels):
            self.lines.append(self.ax.plot(x, y, '-')[0])
        self.line1, = self.ax.plot(x, y, '-')
        self.line2, = self.ax.plot(x, y, '-')

        self.linkLines = [self.ax.plot([0,0],[0,0]) for i in range(0, 10)]
        
        self.scatter1, = self.ax.plot([],[], color=self.lineColor,marker='x',ls='', markersize=3)
        self.scatter2, = self.ax.plot([],[], color="#ccff00",marker='o',ls='', markersize=3)
        self.line1.set_color(self.lineColor)

        ################################################
        # Starting an acquisition thread.
        # Thread updating current pressure
        self.plotThread = daqPlotThread(q=self.q, parent=self, ax=self.ax, line1=self.line1, line2=self.line2, fig=self.fig, scatter1=self.scatter1, scatter2=self.scatter2, axhline=self.axhline)
        #self.plotThread = daqPlotThread(q=self.q)
        self.plotThread.start()
    
    def stop(self):
        self.plotThread.close()
        try:
            self.close()
        except BaseException as e:
            print(f"[daqPlotSubWindow/stop] Error while closing the thread: {e}")

        time.sleep(0.1)
        self.exit()
        #self.quit()
        time.sleep(0.1) 
        
'''
"""

class Canvas(FigureCanvasQTAgg):
    count = 0
    def __init__(self, parent):
        ###############################
        #Matplotlib script
        ###############################
        plt.rcParams['ytick.color'] = "#ffffff" 
        plt.rcParams['xtick.color'] = "#ffffff"
        plt.rcParams['axes.labelcolor'] = "#ffffff"
        plt.rcParams['text.color'] = "#ffffff"

        self.backgroundColor = "#1E2529"
        self.plotColor = "#2F3133"
        #self.plotColor = "#1E2529"
        self.lineColor = "#3399ff"

        self.fig, (self.ax1, self.ax2) = plt.subplots(nrows=2, ncols=1, figsize=(1,1), dpi=100, facecolor=self.backgroundColor)
        self.ax1.set_facecolor(self.plotColor)
        self.ax2.set_facecolor(self.plotColor)
        self.fig.tight_layout(pad=5.0)
        super().__init__(self.fig)

        self.setParent(parent)
        self.parent = parent

                
        #a = np.random.random((256, 1024))
        a = np.random.random((16, 64))
        #plt.imshow(a, cmap='cividis', interpolation='nearest')
        #sns.color_palette("viridis", as_cmap=True)
        sns.heatmap(a, linewidth=0, cbar=False, cmap ="viridis", ax=self.ax1)
        self.ax1.set(xlabel = "X", ylabel = "Y", title = "Acquired image")

        b = np.sum(a, axis=0)
        plt.plot(list(range(0, len(b))), b)
        self.ax1.set(xlabel = "X", ylabel = "Y", title = "Full vertical binning")
        #sns.color_palette("viridis", as_cmap=True)
        #self.ax1.imshow(a, interpolation='nearest')
        #self.t = np.arange(0.0, 2.0, 0.01)
        #self.s = 1 + np.sin(2*np.pi*self.t)
        
        #self.ax.plot(self.t, self.s)

        self.plotType = "heatmap"

    def updatePlotHeatmap(self, data, xpixels, ypixels, xlabel="X", ylabel="Y", title="Plot title placeholder"):
        
        #if self.plotType != "heatmap":
        #    self.fig, self.ax = plt.subplots(figsize=(5,4), dpi=100, facecolor='#140019')
        #    self.plotType = "heatmap"
        
        self.ax1.clear()
        self.ax2.clear()
        data = data.reshape(ypixels, xpixels)
        sns.heatmap(data, linewidth=0, cbar=False, cmap ="viridis", ax=self.ax1)
        self.ax1.set(xlabel = xlabel, ylabel = ylabel, title = title)

        sumY = np.sum(data, axis=0)
        plt.plot(list(range(0, len(sumY))), sumY)
        self.line1, = self.ax1.set(xlabel = "X", ylabel = "Y", title = "Raw data")
        self.line1.set_color(self.lineColor)

        self.fig.suptitle(title)

        self.fig.canvas.draw()

    def updatePlotLine(self, dataX, dataY, xlabel = "Wavelength [cm$^{-1}$]", ylabel = "Intensity", title = "Plot title placeholder"):
        # Retrieving smoothing box value.
        # This cannot be done in the __init__ routine, since at the time that is executed, leftSideBar is not loaded yet.
        self.smoothinngSpinBox = self.parent.retrieveElement("smoothingSpinBox", QSpinBox)  
        #if self.plotType != "line":
        #    self.fig, self.ax = plt.subplots(figsize=(5,4), dpi=100, facecolor='#140019')
        #    self.plotType = "line"
        
        self.ax1.clear()
        self.ax2.clear()
        self.line1, = self.ax1.plot(dataX, dataY)
        self.ax1.set(xlabel = xlabel, ylabel = ylabel, title = "Raw data")
        self.line1.set_color(self.lineColor)

        #print(f"[mainCanvas/updatePlotLine] Smoothing value:  {self.smoothingSpinBox.value()}")

        dataY = wiener(dataY, self.smoothinngSpinBox.value())

        dataY = self.baselineCorrection(dataX, dataY)

        self.line2, = self.ax2.plot(dataX, dataY)
        self.ax2.set(xlabel = xlabel, ylabel = ylabel, title = "Weiner smoothed data")
        self.line2.set_color(self.lineColor)

        self.fig.suptitle(title)
        #self.fig.set_figwidth(10)
        #self.fig.set_figheight(5
        self.fig.canvas.draw()

    def baselineCorrection(self, dataX, dataY):
        print("[baselineCorrection] Starting a baseline correction function.")
        self.baselineCorrectionCBox = self.parent.retrieveElement("baselineCorrectionCBox", QComboBox)
        self.PolyOrderSpinBox = self.parent.retrieveElement("PolyOrderSpinBox", QSpinBox)
        self.exitCriteriaLineEdit = self.parent.retrieveElement("exitCriteriaLineEdit", QLineEdit)

        self.smoothingLineEdit = self.parent.retrieveElement("smoothingLineEdit", QLineEdit)
        self.knotsSpinBox = self.parent.retrieveElement("knotsSpinBox", QSpinBox)
        self.splineSpinBox = self.parent.retrieveElement("splineSpinBox", QSpinBox)
        self.diffOrderSpinBox = self.parent.retrieveElement("diffOrderSpinBox", QSpinBox)
        self.maxIterSpinBox = self.parent.retrieveElement("maxIterSpinBox", QSpinBox)
        self.exitCriteriaPSPLineEdit = self.parent.retrieveElement("exitCriteriaPSPLineEdit", QLineEdit)

        baseline_fitter = pb.Baseline(dataX, check_finite=False)
        # Updating baseline correction
        if self.baselineCorrectionCBox.currentText() == "Modified poly.":
            print("[baselineCorrection] Implementing modified polynomial.")
            background = baseline_fitter.modpoly(dataY, 
                                                 poly_order = self.PolyOrderSpinBox.value(), 
                                                 tol = float(self.exitCriteriaLineEdit.text()))[0]
            
            dataY = dataY - background
        elif self.baselineCorrectionCBox.currentText() == "PSspline airPLS":
            print("[baselineCorrection] Implementing PSSpline AIRPLS.")
            background = baseline_fitter.pspline_airpls(dataY, 
                                                        lam = float(self.smoothingLineEdit.text()),
                                                        num_knots = self.knotsSpinBox.value(),
                                                        spline_degree = self.splineSpinBox.value(),
                                                        max_iter = self.maxIterSpinBox.value(),
                                                        diff_order = self.diffOrderSpinBox.value(),
                                                        tol = float(self.exitCriteriaPSPLineEdit.text()))[0]
            
            dataY = dataY - background

        return dataY


        print(f"[mainCanvas/baselineCorrection] {self.baselineCorrectionCBox.currentText()}" )

"""