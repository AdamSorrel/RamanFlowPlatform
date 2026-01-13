import os, time, datetime, sched, math, redis, json
import win32event  # pip install pyWin32
#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import QFrame, QWidget, QVBoxLayout, \
    QMdiSubWindow
from PyQt6.QtCore import QThread, pyqtSignal, QProcess
from PyQt6.uic import loadUi
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from datetime import datetime
from scipy.signal import argrelextrema, find_peaks

import pickle, multiprocessing
#from concurrent import futures
from nspyre import DataSink
from nspyre.misc.logging import nspyre_init_logger
import logging

#import nidaqmx
#from nidaqmx.stream_readers import AnalogMultiChannelReader
#from nidaqmx.constants import TerminalConfiguration, MIOAIConvertTimebaseSource, ADCTimingMode, Edge, AcquisitionType
from queue import Queue
import mainCanvas

import io

from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

""""
I suspect this is entirely obsolete now. 


class daqSchedulingThread(QThread):
    # User might want to request a delay to acquisition after the singal is processed. 
    # To make this a non-blocking operation, a thread is spawned which is connected to 
    # the daqThread by a delayQueue.
    def __init__(self, acquisitionQ, delayQ):
        super().__init__()
        self.acquisitionQ = acquisitionQ
        self.delayQ = delayQ

        self.scheduler = sched.scheduler(timefunc=time.time, delayfunc=time.sleep)
               
    def run(self):

        #if "Timed acquisition" in self.messageDict.keys():
        #    print("[acquisitionThread] Timed acquisition scheduling.")
        
        #    if len(self.scheduler.queue) == 0: 
        #        self.scheduler.enterabs(self.messageDict["Timed acquisition"])
        #    else:
        #        print("[acquisitionThread] Scheduler is busy. Dropping request.")
        
        print("[daqSchedulingThread] Daq wait thread is initialized. This handles non-blocking delayed acquisition.")
        interrupt = self.isInterruptionRequested()

        self.timeValues = {"Requested time": [], "Actual time": []}

        while not interrupt:
            interrupt = self.isInterruptionRequested()
            self.messageDict = self.delayQ.get()
            
            if self.messageDict == "Stop":
                # Stopping operation
                self.stop()

            # Retrieving value of the delay from a queue message sent by the daqThread.
            triggerTime = self.messageDict["Timed acquisition"]

            if triggerTime < pd.Timestamp.now().value:
                print("[daqSchedulingThread] Trigger time is too late. Skipping.")
                continue

            triggerTime = pd.Timestamp(triggerTime) # Transforming an integer back to a pd.Timestamp format
            print(f"[daqSchedulingThread] Delay: {triggerTime}")    # Printing delay in human readable format
            triggerTimePydate = triggerTime.to_pydatetime().timestamp()     # Transforming to a pydatetime timestamp format which will be used for scheduling, 
                                                                            #but the pd.Timestamp format will be send to the called function
            self.scheduler.enterabs(time=triggerTimePydate, priority=1, action=self.sendForAcquisition, argument=[triggerTime])
            self.scheduler.run(blocking=True)
            
    
    def sendForAcquisition(self, delay):
        print(f"[daqSchedulingThread/sendForAcquisition] Sending acquisition request for time {delay}.")
        now = pd.Timestamp.now()
        print(f"[daqSchedulingThread/sendForAcquisition] Current time: {now}")

        #self.acquisitionQ.put({"Trigger immediate acquisition": True})
        self.timeValues["Requested time"].append(delay)
        self.timeValues["Actual time"].append(now)


        if len(self.timeValues["Requested time"]) == 10:
            dfTimes = pd.DataFrame(self.timeValues)
            dfTimes.to_csv("Scheduling performance.csv")

    def stop(self):
        print("[daqSchedulingThread] Stopping operation.")
        self.exit()
        #self.quit()
        time.sleep(0.1)
"""


class daqResultThread(QThread):
    # This thread collects information from the result Q and updates the UI.
    resultUpdate = pyqtSignal(float, int, int)

    def __init__(self, resultQ):

        super().__init__()
        self.resultQ = resultQ

        print(f"[daqResultThread] =============================================")
        print(f"[daqResultThread] Initializing daqResultThread.")
        print(f"[daqResultThread] =============================================")
               
    def run(self):
        while True:
            resultDict = self.resultQ.get()
            print(f"[daqResultThread] Result dictionary : {resultDict}")
            self.resultUpdate.emit(resultDict["Result"], resultDict["Peak dictionary length channel 1"],  resultDict["Peak dictionary length channel 2"])
        
    def stop(self):
        print("[daqResultThread] Stopping operation.")
        self.exit()
        #self.quit()
        time.sleep(0.1)
"""
class daqDataSavingThread(QThread):
    # This thread collects and saves spectra acquired by the camera.

    def __init__(self, sdk, redisDatabase, plotQ):

        super().__init__()
        self.sdk = sdk
        self.r = redisDatabase
        self.plotQ = plotQ

        self.winEvent = win32event.CreateEvent(None, 0, 0, None)

        ret = self.sdk.SetDriverEvent(self.winEvent.handle)
        print("[ExternalTriggerThread] Function SetDriverEvent returned {}".format(ret))
    
        print(f"[ExternalTriggerThread] =============================================")
        print(f"[ExternalTriggerThread] Initialized daqDataSavingThread.")
        print(f"[ExternalTriggerThread] =============================================")

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

    def run(self):
        while True:
            ret = self.sdk.StartAcquisition()
            print("[ExternalTriggerThread] Function StartAcquisition returned {}".format(ret))
            # This is a mutex that will be released upon acquisition event from the camera
            ret = win32event.WaitForSingleObject(self.winEvent, win32event.INFINITE)
            print("[ExternalTriggerThread] Event triggered, saving data")
            
            self.imageSize = self.xpixels
            (ret, arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, self.imageSize)
            print(f"[ExternalTriggerThread] Function GetImages16 returned {ret} first pixel = {arr[0]} size = {self.imageSize}")

            directory = "C:\\Users\\adato\\Programs\\ramanData" #+ "\\" # Replace with desired directory
            print(f"Saving into directory: {directory}")

            #filename = f"{directory}{time.strftime('TestSpectrum_%Y-%m-%d-%H-%M-%S')}.sif"
            filename = f"{directory}{datetime.now().strftime('TestSpectrum-%Y-%m-%d_%H-%M-%S-%f')}.sif"
            ret = self.sdk.SaveAsSif(filename)
            print("Function SaveAsSif returned {}".format(ret))

            self.plotQ.put({"data": arr, 
                            "dataX": range(0, len(arr)), 
                            "dataY":arr, 
                            "title": "Single track", 
                            "type": "spectrum", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})


    def stop(self):
        print("[daqResultThread] Stopping operation.")
        self.exit()
        #self.quit()
        time.sleep(0.1)
"""

class daqThread(QThread): 
    daqData = pyqtSignal(int)
    def __init__(self, parent, peakQ, resultQ, daqPlotQ, acquisitionQ, sdk, plotQ):
        super().__init__()
        self.parent = parent
        self.peakQ = peakQ
        self.resultQ = resultQ
        self.daqPlotQ = daqPlotQ
        self.acquisitionQ = acquisitionQ
        self.sdk = sdk
        self.plotQ = plotQ
        print("[daqThread] Daq thread initialized.")
        self.setTerminationEnabled(True)

        """
        self.operationModeDict = {"Default" : TerminalConfiguration.DEFAULT, 
                                  "Differential" : TerminalConfiguration.DIFF, 
                                  "NRSE" : TerminalConfiguration.NRSE, 
                                  "Pseudo differential" : TerminalConfiguration.PSEUDO_DIFF, 
                                  "RSE" : TerminalConfiguration.RSE}
        
        self.timeSource = {
            "100 MHz timebase" : MIOAIConvertTimebaseSource.ONE_HUNDRED_MHZ_TIMEBASE.value,
            "80 MHz timebase" : MIOAIConvertTimebaseSource.EIGHTY_MHZ_TIMEBASE.value,
            "20 MHz timebase" : MIOAIConvertTimebaseSource.TWENTY_MHZ_TIMEBASE.value,
            "8 MHz timebase" : MIOAIConvertTimebaseSource.EIGHT_MHZ_TIMEBASE.value,
            "Same source as Master Timebase" : MIOAIConvertTimebaseSource.SAME_AS_MASTER_TIMEBASE.value,
            "Same source as Sample Clock timebase" : MIOAIConvertTimebaseSource.SAME_AS_SAMP_TIMEBASE.value
        }

        self.timingMode = {
            "Automatic" : ADCTimingMode.AUTOMATIC,
            "Best 50 Hz rejection" : ADCTimingMode.BEST_50_HZ_REJECTION,
            "Best 60 Hz rejection" : ADCTimingMode.BEST_60_HZ_REJECTION,
            "Custom" : ADCTimingMode.CUSTOM,
            "High resolution" : ADCTimingMode.HIGH_RESOLUTION,
            "High speed" : ADCTimingMode.HIGH_SPEED
        }

        self.activeEdgeDict = {
            "Rising" : Edge.RISING,
            "Falling" : Edge.FALLING
        }
        """

        self.parent.daqSettings.daqChannel1CBox.currentIndexChanged.connect(self.assignChannels)
        self.parent.daqSettings.daqChannel2CBox.currentIndexChanged.connect(self.assignChannels)
        self.parent.daqSettings.daqChannel3CBox.currentIndexChanged.connect(self.assignChannels)
        
        self.assignChannels()  

    def assignChannels(self):
        self.channels = []
        if self.parent.daqSettings.daqChannel1CBox.currentText() != "Inactive":
            self.channels.append(self.parent.daqSettings.daqChannel1CBox.currentText())

        if self.parent.daqSettings.daqChannel2CBox.currentText() != "Inactive": 
            self.channels.append(self.parent.daqSettings.daqChannel2CBox.currentText())

        if self.parent.daqSettings.daqChannel3CBox.currentText() != "Inactive":
            self.channels.append(self.parent.daqSettings.daqChannel3CBox.currentText())

    def catchError(self):
        # This function is called when the daqVelocityProcess exits with an error in order to catch that error
        print(f"[daqVelocityProcess] ERROR: {self.daqVelocityProcess.error()},ERROR STRING: {self.daqVelocityProcess.errorString()}")
      
    def run(self):

        # Logging time offsets
        self.timeOffsets = pd.DataFrame({"Offset": []})

        # Connecting to the REDIS database
        r = redis.Redis(host="192.168.222.233", 
                password="redisRacs233", 
                port=6379, 
                decode_responses=True,
                #ssl=True,
               )
        
        # Locally hosted redis database for testing purposes
        #r = redis.Redis(host="127.0.0.1", 
        #                port=6379, 
        #                decode_responses=True
        #                )
        
        # Testing connection
        if not r.ping():
            raise RuntimeError

        
        interrupt = self.isInterruptionRequested()
        # TODO: Resolve if this is necessary since I am preparing data a few lines earlier.
        self.peakArray1 = np.array([]) 
        self.peakArray2 = np.array([])

        # Peak list storing a batch of recent peaks
        self.peakList = [[],[],[]]

        # List of already encountered time stamps
        self.timeStampList = []
        # Size of the displayed dataset
        self.DeltaT = pd.Timedelta(2, "seconds")

        # Initializing data frame to receive incoming data.
        self.dfData = pd.DataFrame({0: [], 1: [], 2: []})
        self.samplingRate = 10000
        
        self.lineBreak = "\n".encode()
        #delta = pd.Timedelta(value=500, unit="microseconds")
        output_file = io.FileIO("daq_output"+str(time.time())+".txt", 'a')

        #newTimestamps = []
        
        processedTimestamps = []

        # Time stamp to calculate particles per minute
        tPpm = time.perf_counter_ns()
        nPeaksCh1Ppm = 0
        nPeaksCh2Ppm = 0

        # Data is coming in with typically only 1 new timestamp.
        # Timestamps that have already been processed in previous 
        # iterations are ignored.
        # New time stamp is appended to the list of processed timestamps
        with io.BufferedWriter(output_file,buffer_size=10000000) as output_buffer:
            while True:
                n = 0
                # This is for timing and debugging
                #t0 = time.perf_counter_ns()

                # Peak time dictionary starts already here, but it is actually filled only when some travel time is calculated successfully
                # The dictionary is created here for plotting purposes, so something can be sent to the plotting thread.
                peakTimeDictionary = {}

                # Scanning REDIS database for the label "data_" that belongs to the DAQ output
                keysToProcess = []
                for dataLabel in r.scan_iter(match="data_*"):
                    if dataLabel not in processedTimestamps:
                        keysToProcess.append(dataLabel)
                
                # Sorting new keys to start from the earliest
                if len(keysToProcess) > 0:
                    for key in sorted(keysToProcess):
                        n = n + 1 
                        t0 = time.perf_counter_ns()
                        processedTimestamps.append(key)
                        if len(processedTimestamps) > 100:
                            # To keep the list lookup reasonably fast, we remove very old values
                            processedTimestamps.pop(0)
                        # Retrieving the actual data from the REDIS database
                        rawData = r.get(key)
                        
                        if rawData is not None:
                            # Transforming from numpy array to pandas
                            newDataArr = np.array(json.loads(rawData))

                            # Data are "interleaved", meaning that they appear in the following sequence:
                            # ch1-1, ch2-1, ch3-1, ch1-2, ch2-2, ch3-2, ... 
                            #arr1 = newDataArr[0::3]
                            #arr2 = newDataArr[1::3]
                            #arr3 = newDataArr[2::3]

                            newDataDf = pd.DataFrame(newDataArr)
                            newDataDf.index = newDataDf[0]
                            newDataDf.index.name = ""
                            del newDataDf[0]
                            newDataDf.columns = [0,1,2]
                                
                            #newDataDf = pd.DataFrame(dataOut).transpose()
                            #ttest1 = time.perf_counter_ns()
                            # Parsing time stamp
                            #end = pd.Timestamp(float(dataLabel.split("_")[1]), unit="s")
                            
                            # # # # start = pd.Timestamp(float(key.split("_")[1]), unit="s")
                            #end = np.float64(key.split("_")[1])

                            #dataLen = newDataDf.shape[0]
                            # Getting a start value of the dataset
                            # # # #  end = start + pd.Timedelta(dataLen*1/self.samplingRate, unit="seconds")
                            #start =  end - (dataLen*(1/self.samplingRate))
                            # Adding timestamp as an index of the new data frame
                            #timeIndex = pd.date_range(start=start, end=end, periods=dataLen)
                            #timeIndex = np.linspace(start, end, num=dataLen)

                            #newDataDf.index = pd.DatetimeIndex(timeIndex)                           
                            #newDataDf.index = timeIndex

                            if self.parent.saveDataCheckbox.isChecked():
                                # Long float gets truncated when the to_string is called
                                # Strings do not get truncated so we pre-transform to a string
                                savingDataDf = newDataDf.copy(deep=True)
                                savingDataDf.index = savingDataDf.index.astype(str)
                                newDataString = savingDataDf.to_string(index=True, header=False)
                                
                                output_buffer.write(newDataString.encode())
                                output_buffer.write(b"\n")
                                output_buffer.flush()

                            #ttest2 = time.perf_counter_ns()
                            # Concatenating the data chunk to the main data frame.
                            self.dfData = pd.concat([self.dfData, newDataDf])

                            self.dfData.sort_index(inplace=True, ascending=True)
                            
                            # The upper bound of the data frame size (e.g. latest value + 2 seconds)
                            #lowerBound = self.dfData.index[-1] - self.DeltaT
                            lowerBound = self.dfData.index[-1] - 2

                            # Truncate will remove all values that are over the upperBound value
                            self.dfData = self.dfData.truncate(before=lowerBound)


                            #ttest3 = time.perf_counter_ns()
                            #print(f"T1 : {(ttest1 - ttest0)/1e6} ms, T2: {(ttest2 - ttest1)/1e6} ms, T3: {(ttest3 - ttest2)/1e6} ms")
                else:
                    #print("No new keys to process")
                    delay = 5e7 - (time.perf_counter_ns() - t0) 
                    if delay < 0:
                        delay = 0
                    #print(f"Delay: {delay/1e9} s, Length of data: {len(self.dfData)}, number of labels processed: {n}.")

                    continue

                self.currentPeaks = []
                self.propertiesList = []
                self.newPeaksList = [[],[],[]]
                      
                if self.parent.startDetectingPeaks.isChecked():
                    #print("Entering the start detecting peaks section.")
                    # Peaks are returned as positions in self.dfData data frame. This needs to be transformed into timestamps later. 
                    self.currentPeaks, self.propertiesList = self._findPeaks(data=self.dfData)
                    #t3 = time.perf_counter_ns()
                    #print(f"Properties: {propertiesList}")
                    #print(f"Times: T1 : {(t1-t0)/1e6} ms, T2 : {(t2-t1)/1e6} ms, T3 : {(t3-t1)/1e6} ms")
                    peakTimestampList = []
                    for channel in self.dfData.iloc[:,0:2]: 
                        #print(list(dfData.iloc[peakList[channel],channel].index))
                        peakTimestamps = self.dfData.iloc[self.currentPeaks[channel],channel].index
                        #peakTimestamps = list((peakTimestamps - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ns'))
                        peakTimestampList.append(list(peakTimestamps))
                    #if len(self.currentPeaks) > 0:
                        
                    # If there is something in the peak list, check the peak speed.
                    if (sum([len(array) > 0 for array in self.currentPeaks]) > 0) and (self.parent.startDetectingPeaks.isChecked()):
                        newPeaksBool = False
                        for channel in range(0, len(peakTimestampList)):
                            for peak in peakTimestampList[channel]:
                                if peak not in self.peakList[channel]:
                                    newPeaksBool = True
                                    #print(f"New peak : {peak}")
                                    self.peakList[channel].append(peak)
                                    self.newPeaksList[channel].append(peak)
                        if newPeaksBool:
                            #print(f"[daqThread] New peaks: {self.newPeaksList}")
                            peakTimeDictionary = self.speedMeasurement(self.newPeaksList, self.peakList)        
                            # Adding new peaks from channel 1 to the counter of peaks per second
                            nPeaksCh1Ppm += self.newPeaksList[0]
                            nPeaksCh2Ppm += self.newPeaksList[1]
                            #print(f"New peak detected. Speed measurement triggerd with ({self.newPeaksList}, {self.peakList})")
                            for peak in peakTimeDictionary:
                                detectionDistance = self.parent.detectionFieldDistSpinBox.value() # Distance in mm from the second (probably?) channel
                                channelDistance = self.parent.channelDistanceSpinBox.value()    # Distance between two speed measurement channels. Ordinarily should be 4 mm.
                                offset = (peakTimeDictionary[peak]/channelDistance)*detectionDistance 
                                triggerTime = peak + offset
                                r.set(f"trigger_{triggerTime}", triggerTime)
                                # Expiration time should be a trigger offset time (must be integer) plus 2 second for a good measure. 
                                r.expire(f"trigger_{peak}", int(offset) + 2)

                            

                            #print(f"PEAK TIME DICTIONARY: {peakTimeDictionary}")

                    # Calculating particles per minut
                    if (t0-tPpm) > 60.0:
                        tPpm = t0

                        self.parent.ppmCh1ValueQLabel.setText(f"{nPeaksCh1Ppm}")
                        self.parent.ppmCh2ValueQLabel.setText(f"{nPeaksCh2Ppm}")
                        # Zeroing the peaks count
                        nPeaksCh1Ppm = 0
                        nPeaksCh2Ppm = 0
                         



                peakBoundaries = {"Upper boundary active": self.parent.upperTimeConstrainCheckBox.isChecked(), 
                                  "Lower boundary active": self.parent.lowerTimeConstrainCheckBox.isChecked(),
                                  "Upper boundary value": self.parent.upperTimeConstrainCBox.value(),
                                  "Lower boundary value": self.parent.lowerTimeConstrainCBox.value()}
                
                plotDict = {"data": self.dfData, 
                            "peaks": self.currentPeaks,
                            "properties": self.propertiesList,
                            "peakTimes": peakTimeDictionary,
                            "peakBoundaries": peakBoundaries}
                
                self.daqPlotQ.put_nowait(plotDict)

                delay = 5e7 - (time.perf_counter_ns() - t0) 
                if delay < 0:
                    delay = 0
                #print(f"Delay: {delay/1e9} s, Length of data: {len(self.dfData)}, number of labels processed: {n}.")
                time.sleep(delay/1e9)
            
    def speedMeasurement(self, newPeaks, allPeaks):

        #window = self.parent.peakWindowValue.value()
        numberOfPeaksToCheck = self.parent.peakWindowValue.value()
        matchingThreshold = self.parent.tresholdForPeakMatchingValue.value()

        # Retrieving a peak tolerance (within which peaks are considered matching)
        try:
            self.peakTolerance = float(self.parent.daqPeakTolerance.value())
        except:
            print(f"[daqThread/speedMeasurement] Cannot read peak tolerance. Using previous value.")

        peaksCh1 = np.array(allPeaks[0])
        peaksCh2 = np.array(allPeaks[1])

        outputDict = {}

        #newPeaks = np.array(newPeaks, dtype=np.float64)
        # HACK! This needs to be resolved! It just occasionally does not have any peak in Ch1 when it starts so then min(peaksCh1) fails.
        # This is to reduce the size of the time stamp float.
        try:
            minVal = min(peaksCh1)
        except:
            return outputDict
        
        peaksCh1 = peaksCh1 - minVal
        peaksCh2 = peaksCh2 - minVal

        newPeaks[0] = newPeaks[0] - minVal
        newPeaks[1] = newPeaks[1] - minVal

        for peak in newPeaks[1]:
            
            nearestPeakCh1 = self.findingPreviousPeak(peaksCh1, peak)

            n = 0
    
            nIterations = self.parent.iterationsSpinBox.value()
            while n < nIterations:    
                #print(f"Number of iterations: {nIterations}")            
                # Calculating peak offset from an earlier peak in ch1.
                timeOffset = peak - nearestPeakCh1

                # Lower time limit is a user defined limit under which no possible peaks will be considered. 
                if self.parent.lowerTimeConstrainCheckBox.isChecked():                    
                    lowerTimeConstrainLimit = self.parent.lowerTimeConstrainCBox.value()
                    #print(f"Lower limit active: {lowerTimeConstrainLimit}") 
                    
                    if timeOffset <  lowerTimeConstrainLimit:
                        nearestPeakCh1 = self.findingPreviousPeak(peaksCh1, nearestPeakCh1)
                        continue

                if self.parent.upperTimeConstrainCheckBox.isChecked():
                    upperTimeConstrainLimit = self.parent.upperTimeConstrainCBox.value()
                    #print(f"Upper limit active: {upperTimeConstrainLimit}") 

                    if timeOffset > upperTimeConstrainLimit:
                        #print(f"[daqThread/speedMeasurement] Not enough peaks matched the criteria.")
                        break

                matchingPeaks = self.checkPeaksMatch(peaksCh1=peaksCh1, peaksCh2=peaksCh2, offset=timeOffset, numberOfPeaksToCheck=numberOfPeaksToCheck, tolerance=self.peakTolerance)
                
                print(f"[daqThread/speedMeasurement] Matching peaks: {matchingPeaks}")
                
                if matchingPeaks > matchingThreshold:
                    self.parent.currentTimeValue.setText(f"{timeOffset:.4f}")
                    self.parent.currentVelocityValue.setText(f"{(self.parent.channelDistanceSpinBox.value()/timeOffset):.4f}")
                    print(f"[daqThread/speedMeasurement] Time offset {timeOffset:.4f}")
                    outputDict[(peak+minVal)/1e9] = (timeOffset)/1e9
                    break
                else:
                    #print(f"[daqThread/speedMeasurement] No result, recalculating previous peak.")
                    nearestPeakCh1 = self.findingPreviousPeak(peaksCh1, nearestPeakCh1)
                
                n += 1
        return outputDict

    
    def findingPreviousPeak(self, peaksCh1, peak):
        
        earlierPeaksCh1 = peaksCh1[peaksCh1 < peak]
        if len(earlierPeaksCh1) == 0:
            #print("No earlier peaks.")
            return 0
        else:
            nearestPeakCh1 = max(earlierPeaksCh1)
            return nearestPeakCh1

    def checkPeaksMatch(self, peaksCh1, peaksCh2, offset, numberOfPeaksToCheck, tolerance):

        # Chchecking if we have all values necessary. 
        if (len(peaksCh1) < numberOfPeaksToCheck):
            #print(f"[daqThread/speedMeasurement] Not enough peaks in channel 1.")
            matchingPeaks = 0
            return matchingPeaks
        
        if (len(peaksCh2) < numberOfPeaksToCheck):
            #print(f"[daqThread/speedMeasurement] Not enough peaks in channel 2.")
            matchingPeaks = 0
            return matchingPeaks

        pkVect1 = peaksCh1[-numberOfPeaksToCheck:]
        pkVect2 = peaksCh2[-numberOfPeaksToCheck:]-offset

        #print(f"ch1 : {peaksCh1[-window:]}, ch2 : {peaksCh2[-window:]}, offset : {offset}, tolerance: {self.peakTolerance}")

        matchedPeaks = 0
        #print(f"[daqThread/checkPeaksMatch] pkVect1 : {pkVect1}, pkVect2 : {pkVect2}")
        for peak in pkVect1:
            boolVect = [math.isclose(a=peak, b=x, abs_tol=tolerance) for x in pkVect2]
            if True in boolVect:
                matchedPeaks += 1

        return matchedPeaks

    def parsingData(self, inputData, dfData, samplingFrequency, newTimestamps, DeltaT):
        ''' 
        Receiving a list of dictionaries with single key (a timestamp) and a value, 
        which is a list of 1 to 3 lists of voltages (one per channel). Each list has 
        around 1000 entries, but not necessarily exactly.
        The time stamps are expanded for each voltage separately. The values are extra-
        polated from the known sampling frequency.
        '''
        nloops = 0
        for entry in inputData:
            t0 = time.perf_counter_ns()
            # Looping over entries
            timestamp = list(entry.keys())[0]
            if timestamp in newTimestamps:            
                # Transformig values into a data frame
                values = list(entry.values())[0]
                dfSubsetData = pd.DataFrame(values)
                # Generating timestamp values for each entry
                t1 = time.perf_counter_ns()
    
                end = timestamp
                dataLen = dfSubsetData.shape[1]
                start = end - pd.Timedelta(dataLen*1/samplingFrequency, unit="seconds")

                timeIndex = pd.date_range(start=start, end=end, periods=dataLen)
                t2 = time.perf_counter_ns()
                
                dfSubsetData = dfSubsetData.transpose()
                dfSubsetData.index = pd.DatetimeIndex(timeIndex)
                
                # Concatenating the data chunk to the main data frame.
                dfData = pd.concat([dfData, dfSubsetData])

                t3 = time.perf_counter_ns()
                
                dfData.sort_index(inplace=True, ascending=True)
                t4 = time.perf_counter_ns()
                
                # The upper bound of the data frame size (e.g. latest value + 1 second)
                lowerBound = dfData.index[-1] - DeltaT
                # Truncate will remove all values that are over the upperBound value
                dfData = dfData.truncate(before=lowerBound)
                t5 = time.perf_counter_ns()

                # For debugging purposes
                #print(f"T1: {(t1 - t0)/1e6} ms, T2: {(t2 - t1)/1e6} ms, T3: {(t3-t3)/1e6} ms, T4: {(t4-t3)/1e6} ms, T5: {(t5-t4)/1e6} ms")

        return dfData

    def _findPeaks(self, data):
        peakList = []
        propertiesList = []

        thresholds = [self.parent.threshold1, self.parent.threshold2]
        doublePeakDistance = self.parent.doublePeakDistanceValue.value()
        
        if self.parent.invertedBox.isChecked():
            data = -data
            thresholds = [-threshold for threshold in thresholds]
        width = self.parent.peakWidthValue.value()
        distance = self.parent.peakDistanceValue.value()
        # Only checking for channel 1 and channel 2. 
        # No peaks are retrieved for channel 3.
        # TODO: What is exactly peak width?
        for channel, threshold in zip(data[0:2], thresholds):
            peaks, properties = find_peaks(data[channel], height=threshold, width=width, distance=distance)
            # If we have more than one peak, let's see if we can merge some.
            # We are checking left ips to consider the moment the peak enters the laser beam
            # Left_ips are the left sides of peak. 
            # Left ips are floats so they need to be cast as integers first.
            peaks = properties["left_ips"].astype(int)

            if len(peaks) > 1:
                previousPeak = peaks[0]
                i = 1 # Since the first peak is taken as the "previous peak"
                peaksToRemove = []
                for peak in peaks[1:]:
                    # Let's check distance to the previous peak
                    delta = abs(peak - previousPeak)
                    if delta < doublePeakDistance:
                        # If peaks are too close, the second one (later one) is removed
                        peaksToRemove.append(i)
                    i += 1
                peaks = np.delete(peaks, peaksToRemove)
                #print(f"[findPeaks] Removing {len(peaksToRemove)} peaks that are duplicate")
            
            # This function gets peak positions in data frame, but not their time stamps.
            peakList.append(peaks.astype(int))
            propertiesList.append(properties)

        return peakList, propertiesList
    
    def _peakArea(self):
        desidredPeakArea = self.parent.daqPeakArea.value()
        selectedPeaks = []

        selectedPeaksIntensities = []
        selectedPeakAreas = []
        for i, peak in enumerate(self.peaks):
            peakArea = abs(np.trapz(self.data[0][round(peak - self.properties["widths"][i]):round(peak + self.properties["widths"][i])]))
            if peakArea > desidredPeakArea:
                selectedPeaks.append(peak)
                selectedPeaksIntensities.append(self.data[0][peak])
                selectedPeakAreas.append(peakArea)

        return np.array(selectedPeaks), np.array(selectedPeaksIntensities), np.array(selectedPeakAreas)
    
    def startAcquisition(self):
        # This function prepares the acquisition message and places it to the acquisition queue. 
        print(f"[daqThread/startAcquisition] Acquisition start requested.")
        self.parent.acquisitionQ.put({"Filename" : f"Spectrum_{'_'.join(str(pd.Timestamp.now).split(' '))}"})

    def stop(self):
        print("[daqThread/stop] Called the stop function.")
        print("[daqThread/stop] Requesting interruption of the wait function.")
        #self.daqWaitingThread.requestInterruption()
        self.delayQ.put("Stop")
        time.sleep(0.1)
        self.exit()
        #self.quit()
        time.sleep(0.1)            

class loadDaqSidebar(QWidget):
    def __init__(self, acquisitionQ, daqSettings, mainCanvasMdi, sdk, plotQ):
        super().__init__()
        self.acqiusitionQ = acquisitionQ
        self.daqSettings = daqSettings
        self.mainCanvasMdi = mainCanvasMdi
        self.sdk = sdk
        self.plotQ = plotQ
        #loadUi("leftSidebarsUIs/daqSidebar.ui", self)
        loadUi("leftSidebarsUIs/daqSidebarV2.ui", self)

        """
        self.plot = daqCanvas(self)
        self.daqPlotCanvas = self.findChild(QFrame, "daqPlotFrame")
        vbox = QVBoxLayout()
        vbox.addWidget(self.plot)
        vbox.setContentsMargins(0,0,0,0)
        self.daqPlotCanvas.setLayout(vbox)
        """

        #self.updateAxisLimits()
        #self.updateThresholdLine()

        # Connecting buttons
        self.startMonitoring.clicked.connect(self.runDaqThread)
        #self.stopMonitoring.clicked.connect(self.stopDaqThread)

        #self.minYDaq.returnPressed.connect(self.updateAxisLimits)
        #self.maxYDaq.valueChanged.connect(self.updateAxisLimits)
        #self.maxYDaq.returnPressed.connect(self.updateAxisLimits)
        #self.thresholdDaq.valueChanged.connect(self.updateThresholdLine)

        # Queues for sending peak data and collecting offset process data
        self.peakQ = multiprocessing.Queue(maxsize=100)
        self.resultQ = multiprocessing.Queue(maxsize=100)

        # Spawning daqThread
        # Queue for plotting DAQ data
        self.daqPlotQ = Queue(maxsize=100)
        self.daqThread = daqThread(parent=self, 
                                   peakQ=self.peakQ, 
                                   resultQ=self.resultQ, 
                                   daqPlotQ=self.daqPlotQ, 
                                   acquisitionQ=self.acqiusitionQ,
                                   sdk=self.sdk,
                                   plotQ = self.plotQ)

        self.timeValuesList = []

        self.daqResultThread = daqResultThread(resultQ=self.resultQ)
        self.daqResultThread.resultUpdate.connect(self.updateVelocity)
        self.daqResultThread.start()

        # Peak threshold default value
        self.threshold1 = 10
        self.threshold2 = 10

    def updateDownsampling(self):
        downsamplingValue = self.plotDownsamplingSpinBox.value()
        
        self.plot.plotDownsamplingSignal.emit(downsamplingValue)
        #except:
        #    print(f"[loadDaqSidebar/updateDownsampling] Error updating downsampling. Make sure a DAQ plot is running.")

    def updateVelocity(self, result, datasetLenCh1, datasetLenCh2):
        self.currentTimeValue.setText(f"{result:.4f}")
        distance = self.channelDistanceSpinBox.value()
        self.currentVelocityValue.setText(f"{distance/result:.4f}")
        self.datasetSizeCh1Value.setText(f"{datasetLenCh1}")
        self.datasetSizeCh2Value.setText(f"{datasetLenCh2}")

        self.timeValuesList.append(result)
        # If we have 10 values of velocity, calculating standard deviation and removing the first value. 
        # Always calculating only on the last 10 values.  
        if len(self.timeValuesList) > 10:
            self.velocityStdDevValue.setText(f"{np.std(self.timeValuesList)*1000:.4f}")
            self.averageTimeValue.setText(f"{np.median(self.timeValuesList):.4f}")
            self.medianVelocityValue.setText(f"{distance/np.median(self.timeValuesList):.4f}")
            del self.timeValuesList[0]
        else:
            self.velocityStdDevValue.setText("NA")
            self.medianVelocityValue.setText("NA")

    def updateDatasetSize(self):
        print(f"[loadDaqSidebar/updateDatasetSize] updating dataset size to {self.setDatasetSizeSpinBox.value()}")
        if self.setDatasetSizeSpinBox.value() < 10:
            print("Flushing database completely.")
            self.peakQ.put({"Action": "Flush database"})
        else:
            self.peakQ.put({"Database size":self.setDatasetSizeSpinBox.value()})
        
    def runDaqThread(self):

        self.nDaqChannels = 0

        if self.daqSettings.daqChannel1CBox.currentText() != "Inactive":
            self.nDaqChannels += 1
        if self.daqSettings.daqChannel2CBox.currentText() != "Inactive":
            self.nDaqChannels += 1
        if self.daqSettings.daqChannel3CBox.currentText() != "Inactive":
            self.nDaqChannels += 1    

        print(f"############################################################################")
        print(f"[daqCanvas] Number of channels: {self.nDaqChannels}")
        print(f"############################################################################")
        
        sub = QMdiSubWindow()
        self.plot = mainCanvas.daqPlotSubWindow(parent=self, q=self.daqPlotQ, nchannels=self.nDaqChannels)

        self.plot.thresholdSignal.connect(self.updateThreshold)
        sub.setWidget(self.plot)
        
        sub.setWindowTitle(f"Sub window")
        #sub.RubberBandResize()
        self.mainCanvasMdi.addSubWindow(sub)
        sub.show()

        if self.daqThread.isRunning():
            # If daqThread is already running, refuse to turn it on again.
            print("[runDaqThread] Daq thread is already running.")
        else:
            #self.daqThread.change_value.connect(self.updateTemperature)
            self.daqThread.start()
            #daqCanvas.updatePlot(dataPoint=dataPoint, line=self.plot.line1, canvas=self.plot.fig.canvas)
        #else:
        #    print(f"[runDaqCard] Daq card thread is already running.") 
            
    def updateThreshold(self, label, value):
        #label, value = data
        print(f"[daqSidebar/loadDaqSidebar/updateThreshold] Label: {label}, value: {value}.")
        #self.peakQ.put({"Action": "Update threshold", 
        #                "Plot label": label, 
        #                "Threshold value": value})
        if label == 1:
            self.threshold1 = value
        elif label == 2:
            self.threshold2 = value
    """
    def stopDaqThread(self):
        #ret = self.daqThread.exit()
        # We have some warning.
        time.sleep(0.5)
        print(f"[stopDaqThread] Terminating daqVelocityProcess.")
        ret = self.daqThread.requestInterruption()
        time.sleep(0.1)
        #self.daqThread.quit()
        #self.thread.wait()
        self.daqThread.stop()
        #print(f"[stopDaqCard] function returned {ret}. Terminating fake data stream.")
        #self.daqThreadRunning = False
    """

        


        

        

    
