import sys, os, time
from queue import Queue

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QWidget, QMdiSubWindow
from PyQt6.QtCore import QPropertyAnimation, QParallelAnimationGroup, QSize, Qt
from PyQt6.uic import loadUi
import icons_rc
# Loading prior stage library
from ctypes import WinDLL, create_string_buffer

# Wiener smoothing
from scipy.signal import wiener
# Baseline correction
import pybaselines as pb
# Plotting classes
import mainCanvas


class loadPlotSettings(QWidget):
    def __init__(self, mainCanvasMdi, plotQ):
        super().__init__()
        self.mainCanvasMdi = mainCanvasMdi
        self.plotQ = plotQ
        loadUi("leftSidebarsUIs/plotSettings.ui", self)
        
        ######################################################
        # Connecting buttons
        ######################################################
        #self.goToPositionHelpBtn.clicked.connect(self.goToPositionHelp)
        
        self.baselineCorrectionCBox.currentTextChanged.connect(self.setBaselineCorrection)
        self.smoothingSpinBox.valueChanged.connect(self.updatePlot)

        # Connecting all settings items to updatePlot callback to enable immediate updates when values are changed.
        self.PolyOrderSpinBox.valueChanged.connect(self.updatePlot)
        self.knotsSpinBox.valueChanged.connect(self.updatePlot)
        self.splineSpinBox.valueChanged.connect(self.updatePlot)
        self.maxIterSpinBox.valueChanged.connect(self.updatePlot)
        self.diffOrderSpinBox.valueChanged.connect(self.updatePlot)
        self.exitCriteriaLineEdit.returnPressed.connect(self.updatePlot)
        self.smoothingLineEdit.returnPressed.connect(self.updatePlot)
        self.exitCriteriaPSPLineEdit.returnPressed.connect(self.updatePlot)
        """
        self.plotQ = Queue(maxsize = 1)
        sub = QMdiSubWindow()
        sub.setWidget(mainCanvas.mainPlotSubWindow(q = self.plotQ, type="raw"))
        sub.setWindowTitle(f"Main plot window: Raw data")
        self.mainCanvasMdi.addSubWindow(sub)
        sub.show()
        """
        #self.plotQ = Queue(maxsize = 1)
        sub = QMdiSubWindow()
        sub.setWidget(mainCanvas.mainPlotSubWindow(q = self.plotQ, type="smoothed"))
        sub.setWindowTitle(f"Main plot window: Smoothed data")
        self.mainCanvasMdi.addSubWindow(sub)
        sub.show()
    

    def updatePlot(self):
        print("[plotSettings] Updating plot")

    """
        newSmoothingValue = self.smoothingSpinBox.value()
        print(f"[loadPlotSettings] Value of smoothing is updated to {newSmoothingValue}.")

        # Getting original data from the 1st plot
        dataX = self.plot.line1.get_xdata()
        dataY = self.plot.line1.get_ydata()
        lineColor = self.plot.line1.get_color()
        labelX = self.plot.ax1.get_xlabel()
        labelY = self.plot.ax1.get_ylabel()

        # Updating smoothing value
        if newSmoothingValue == 0:
            self.plot.ax2.set_title("Processed data, no smoothing")
        else:
            self.plot.ax2.set_title("Processed data, Weiner smoothing")
            dataY = wiener(dataY, newSmoothingValue)
        
        baseline_fitter = pb.Baseline(dataX, check_finite=False)
        # Updating baseline correction
        if self.baselineCorrectionCBox.currentText() == "Modified poly.":
            print("[updatePlot] Implementing modified polynomial.")
            background = baseline_fitter.modpoly(dataY, 
                                                 poly_order = self.PolyOrderSpinBox.value(), 
                                                 tol = float(self.exitCriteriaLineEdit.text()))[0]
            
            dataY = dataY - background
        elif self.baselineCorrectionCBox.currentText() == "PSspline airPLS":
            print("[updatePlot] Implementing PSSpline AIRPLS.")
            background = baseline_fitter.pspline_airpls(dataY, 
                                                        lam = float(self.smoothingLineEdit.text()),
                                                        num_knots = self.knotsSpinBox.value(),
                                                        spline_degree = self.splineSpinBox.value(),
                                                        max_iter = self.maxIterSpinBox.value(),
                                                        diff_order = self.diffOrderSpinBox.value(),
                                                        tol = float(self.exitCriteriaPSPLineEdit.text()))[0]
            
            dataY = dataY - background

        self.plot.ax2.clear()
        self.plot.line2, = self.plot.ax2.plot(dataX, dataY)
        self.plot.line2.set_color(lineColor)
        self.plot.ax2.set_xlabel(labelX)
        self.plot.ax2.set_ylabel(labelY)
        #self.line2, = self.ax2.plot(dataX, dataY)

        self.plot.fig.canvas.draw()
    """

    def setBaselineCorrection(self):
        print("[plotSettings] Setting baseline correction.")
        if self.baselineCorrectionCBox.currentText() == "Modified poly.":
            self.modpolyFrameAnimation()
        elif self.baselineCorrectionCBox.currentText() == "PSspline airPLS":
            self.psplineFrameAnimation()
        else:
            print("Closing all baseline correction windows.")
            self.closeAllBaselineCorrectionWindowsAnimation()

        self.updatePlot()

    def modpolyFrameAnimation(self):
        if self.baselineCorrectionCBox.currentText() == "Modified poly.":
            print("[modpolyFrameAnimation] Modified polynomial selected")
            duration = 500
            # Opening multitrack animation
            self.modpolyAnimationSequence = QPropertyAnimation(self.modpolyFrame, b"maximumSize")
            self.modpolyAnimationSequence.setDuration(duration)
            self.modpolyAnimationSequence.setStartValue(self.modpolyFrame.maximumSize())
            self.modpolyAnimationSequence.setEndValue(QSize(1000,1000))
            if self.psplineFrame.maximumHeight() != 0:
                self.psplineFrame.setMaximumHeight(0)
            self.modpolyAnimationSequence.start()
        else:
            print("Something else selected")
            duration = 250
            self.animationMenu = QPropertyAnimation(self.modpolyFrame, b"maximumSize")
            self.animationMenu.setDuration(duration)
            self.animationMenu.setStartValue(self.modpolyFrame.maximumSize())
            self.animationMenu.setEndValue(QSize(1000,0))
            self.animationMenu.start()

    def psplineFrameAnimation(self):
        if self.baselineCorrectionCBox.currentText() == "PSspline airPLS":
            print("[psplineFrameFrameAnimation] PSP line selected")
            duration = 500
            # Opening multitrack animation
            self.psplineAnimationSequence = QPropertyAnimation(self.psplineFrame, b"maximumSize")
            self.psplineAnimationSequence.setDuration(duration)
            self.psplineAnimationSequence.setStartValue(self.psplineFrame.maximumSize())
            self.psplineAnimationSequence.setEndValue(QSize(1000,1000))
            if self.modpolyFrame.maximumHeight() != 0:
                self.modpolyFrame.setMaximumHeight(0)
            self.psplineAnimationSequence.start()
        else:
            print("Something else selected")
            duration = 250
            self.animationMenu = QPropertyAnimation(self.psplineFrame, b"maximumSize")
            self.animationMenu.setDuration(duration)
            self.animationMenu.setStartValue(self.psplineFrame.maximumSize())
            self.animationMenu.setEndValue(QSize(1000,0))
            self.animationMenu.start()

    def closeAllBaselineCorrectionWindowsAnimation(self):
        duration = 500
        self.animationGroup = QParallelAnimationGroup()
        if self.modpolyFrame.maximumHeight() != 0:
            self.modpolyAnimSequence = QPropertyAnimation(self.modpolyFrame, b"maximumSize")
            self.modpolyAnimSequence.setDuration(duration)
            self.modpolyAnimSequence.setStartValue(self.modpolyFrame.maximumSize())
            self.modpolyAnimSequence.setEndValue(QSize(1000,0))
            self.animationGroup.addAnimation(self.modpolyAnimSequence)
        elif self.psplineFrame.maximumHeight() != 0:
            self.psplineFrameAnimSequence = QPropertyAnimation(self.psplineFrame, b"maximumSize")
            self.psplineFrameAnimSequence.setDuration(duration)
            self.psplineFrameAnimSequence.setStartValue(self.psplineFrame.maximumSize())
            self.psplineFrameAnimSequence.setEndValue(QSize(1000,0))
            self.animationGroup.addAnimation(self.psplineFrameAnimSequence)
        else:
            print("Nothing selected")

        self.animationGroup.start()

    

if __name__ == "__main__":
    print("Not possible to load stageSidebar alone.")
