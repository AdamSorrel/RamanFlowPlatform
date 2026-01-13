import sys, os, time, re
from typing import Union, List
import numpy as np
import pandas as pd
from queue import Queue

import cProfile

#os.chdir("C:/Users/adato/Documents/Programs/Andor/")

from PyQt6.QtWidgets import (QMainWindow, QPushButton, QLabel, QLineEdit, QMdiSubWindow,
                            QApplication, QComboBox, QVBoxLayout, QDoubleSpinBox, QSpinBox)
from PyQt6.QtCore import QThread, QMutex
from PyQt6.uic import loadUi
import icons_rc
import leftSidePanel, mainCanvas
# Detector camera libraries
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
# Spectrograph libraries (grating, filters, etc.)
from pyAndorSpectrograph.spectrograph import ATSpectrograph
from ctypes import create_string_buffer

##############################
# Acquisition thread is triggered by a message (dictionary) put into
# an acquisition queue. 

# Acquisition queue is spawned in a main thread (see below).

# Empty dictionary triggers acquisition with current preset parameters.

# The possible options in the  dictionary are following:
# Filename              - user defined output filename
# Wavelength            - defined central wavelength
# Read mode             - Image (2 dimensional data) or spectrum (1 dimensional)
# Xpixels               - Number of acquired pixels on the X axis
# Ypixels               - Number of acquired pixels on the Y axis 
# Acquisition mode      - Acquisition mode. Currently implemented Single scan, Accumulate, Kinetic series
# Kinetic series length - Defines the length of kinetic series in case Kinetic series is selected as acquisition mode

# Acquisition thread is communicating its finished back using the acquisition queue.
# The ready message is in the following format: 
# {"status": "Acquisition ready"}

# ##############################
class acquisitionThread(QThread):
    #progressUpdate = pyqtSignal(str)
    #def __init__(self, sdk, readMode, xpixels, ypixels, plot, startBtn, q):
    def __init__(self, parent, sdk, spc, acquisitionQ, acquisitionFinishedQ, plotQ):
        self.parent = parent
        self.sdk = sdk
        self.spc = spc
        self.acquisitionQ = acquisitionQ
        self.acquisitionFinishedQ = acquisitionFinishedQ
        self.plotQ = plotQ
        super().__init__()

        # Retrieving SDK prior (if it already exists)
        self.SDKPrior = self.parent.leftSidePanel.SDKPrior
        self.sessionID = self.parent.leftSidePanel.sessionID
        self.rx = create_string_buffer(1000)
        print("[acquisitionThread] Acquisition thread initialized.")
        #self.progressUpdate.emit("Acquisition thread initialized")

        #print("##################################")
        #print(f"[main] acquisition thread isSignalConnected: {self.isSignalConnected(self.progressUpdate)}")
        #print("##################################")

    def run(self):
        # Read mode options switch block structure
        readModeOptions = {
            "Full vertical binning": self.__fullVerticalBinning,
            "Single track": self.__singleTrack,
            "Multi track" : self.__multiTrack,
            "Random track" : self.__randomTrack,
            "Image": self.__image}
        
        while True:           
            self.messageDict = self.acquisitionQ.get()
        
            print(f"[acquisitionThread/run] message: {self.messageDict}")
            # If incoming message defines wavelength, it is set in the machine and the UI is updated with the appropriate values. 
            # Note: This is a blocking operation of the acquisitionThread and will increase the length of acquisition. 
            if "Wavelength" in self.messageDict.keys():
                print(f"[acquisitionThread/run] User supplied wavelength: {self.messageDict['Wavelength']}")
                self.parent.wavelengthSetValue.setText(str(self.messageDict['Wavelength']))
                
                # Checking current wavelength
                ret, currentWavelength = self.spc.GetWavelength(0)
                # If current wavelength is already set, no further action is taken
                if currentWavelength != self.messageDict['Wavelength']:
                    shm = self.spc.SetWavelength(0, float(self.messageDict['Wavelength']))
                    print(f"[acqisitionThread/setWavelength] Function SetWavelength returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")

                    # Retrieving current grating (0 -> number of machine)
                    (ret, grat) = self.spc.GetGrating(0)

                    (shm, min, max) = self.spc.GetWavelengthLimits(0, grat)
                    print(f"[acqisitionThread/setWavelength] Function GetWavelengthLimits returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]} Wavelength Min: {min} Wavelength Max: {max}")

                    self.parent.wavelengthMinimum.setText(str(min)+" nm")
                    self.parent.wavelengthMaximum.setText(str(max)+" nm")

                    # Checking if wavelength is at zero order
                    # atZeroOrder - pointer to flag:: 0 - wave
                    # length is NOT at zero order / 1 - wavelength IS at zero order
                    ret, atZeroOrder = self.spc.AtZeroOrder(device=0)
                    print(f"[acqisitionThread/setWavelength] Function AtZeroOrder returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")
                    print(f"[acqisitionThread/setWavelength] Function AtZeroOrder returned: {self.spc.GetFunctionReturnDescription(shm, 64)[1]}")
                    if atZeroOrder == 1:
                        #print(f"[setWavelength] Wavelength IS at zero order.")
                        self.parent.zeroOrderValue.setText("True")
                    else:
                        #print(f"[setWavelength] Wavelength is NOT at zero order.")
                        self.parent.zeroOrderValue.setText("False")

                else:
                    print(f"[acqisitionThread/setWavelength] Current wavelength already set at the desired value: {currentWavelength} nm")
    	        
            # Setting up saving of data.
            # If the incoming message contains a filename, the resulting data will be saved.
            if self.parent.saveFolderLineEdit.text() != "":
                path = self.parent.saveFolderLineEdit.text()
                # Validating path
                if os.path.exists(path):
                    if "Filename" in self.messageDict.keys():
                        fileName = self.messageDict["Filename"]
                        # Replacing all blank space with underscore. The detector data saving routine can't handle blank spaces
                        fileName = re.sub('[ ]', '_', fileName) 
                        if path[-1] == "/":
                            self.pathAndName = path + self.messageDict['Filename']
                        else:
                            self.pathAndName = path + '/' + self.messageDict['Filename']
                        print(f"[acquisitionThread/run] Output file path: {self.pathAndName}")
                    else:
                        spectrumName = f"Spectrum_{pd.Timestamp.now()}"
                        spectrumName = "-".join(spectrumName.split(":"))
        
                        #self.pathAndName = "_".join(self.pathAndName.split(" "))
                        #self.pathAndName = "_".join(self.pathAndName.split(".")[0:2])+".sif"
                        #self.pathAndName = "-".join(self.pathAndName.split(":"))
                        #self.pathAndName = "C:" + self.pathAndName[2:]

                        if path[-1] == "/":
                            self.pathAndName = path + spectrumName
                        else:
                            self.pathAndName = path + '/' + spectrumName
                        print(f"[acquisitionThread/run] Output file path: {self.pathAndName}")
                    # Setting up a "spool" to save the outcoming data
                    dataSaveMethod, name = self.getOutputModeCBox()
                    print(f"[acquisitionThread/run] Selected data saving method is: {name}")
                    #ret = self.sdk.SetSpool(active=1, 
                    #                        method=dataSaveMethod, 
                    #                        path=pathAndName, 
                    #                        framebuffersize=10)
                    #print("[acquisitionThread/run] Function SetSpool returned {} ".format(ret))
                else: 
                    print(f"[acquisitionThread/run] Warning:  Data is not saved! Invalid filepath {path}.")


            if "Xpixels" in self.messageDict.keys():
                self.xpixels = self.messageDict["Xpixels"]
            else:
                print(f"[acquisitionThread/run] Missing x pixels value. Retrieving from device.")
                (ret, self.xpixels, self.ypixels) = self.sdk.GetDetector()
                print(f"[startAcquisition] Function GetDetector returned {ret} xpixels = {self.xpixels} ypixels = {self.ypixels}")
                
            
            if "Ypixels" in self.messageDict.keys():
                self.ypixels = self.messageDict["Ypixels"]
            else:
                print(f"[acquisitionThread/run] Missing y pixels value. Retrieving from device.")
                (ret, self.xpixels, self.ypixels) = self.sdk.GetDetector()
                print(f"[startAcquisition] Function GetDetector returned {ret} xpixels = {self.xpixels} ypixels = {self.ypixels}")

            # This is not how we plot anymore. Should be removed in the future.
            #if "Plot" in self.messageDict.keys():
            #    self.plot = self.messageDict["Plot"]
            #else:
            #    print(f"[acquisitionThread/run] Missing plot handle. Terminating acquisition.")
            #    self.q.task_done()

            if "Acquisition mode" in self.messageDict.keys():
                self.mode = self.messageDict["Acquisition mode"]
            else:
                self.mode = self.parent.acquisitionMode.currentText()
                print("[acquisitionThread] Acquisition mode not supplied in a message, retrieving from the UI.")


            if self.mode == "Single scan": 
                # Single scan acquisition
                print(f"[acquisitionThread/run] Acquiting single scan.")
                # If read mode not supplied in the message, retrieve from UI
                if "Read mode" not in self.messageDict.keys():
                    print(f"[acquisitionThread/run] Missing read mode. Retrieving from UI.")
                    self.readMode = self.parent.readModeCBox.currentText()
                else:
                    self.readMode = self.messageDict["Read mode"]

                ret, self.calibrationValues = self.spc.GetCalibration(0, 1024)
                if ret == ATSpectrograph.ATSPECTROGRAPH_SUCCESS:
                    print(f"[acquisitionThread/run] Calibration values are {self.calibrationValues[0:9]}")
                elif ret == ATSpectrograph.ATSPECTROGRAPH_P1INVALID:
                    print("[acquisitionThread/run] Retrieving X calibration error: Invalid device, spectrograph not connected")
                elif ret == ATSpectrograph.ATSPECTROGRAPH_NOT_INITIALIZED:
                    print("[acquisitionThread/run] Retrieving X calibration error: Spectrograph not initialized")
                elif ret == ATSpectrograph.ATSPECTROGRAPH_COMMUNICATION_ERROR:
                    print("[acquisitionThread/run] Retrieving X calibration error: Communication error.")
                elif ret == ATSpectrograph.ATSPECTROGRAPH_P3INVALID:
                    print("[acquisitionThread/run] Retrieving X calibration error: Invalid number of pixels")
                else:
                    print(f"[acquisitionThread/run] Retrieving X calibration error: Unknown issue code: {ret}") 
                
                # Opening shutter if it is connected.
                #if self.parent.leftSidePanel.shutterSidebar.connectionStatusLabel.text() == "Connected":
                #    self.parent.leftSidePanel.shutterSidebar.shutterDriver("Open")
                #self.priorCMD("controller.ttl.out.set 1")

                ret = self.sdk.PrepareAcquisition()
                print("[acquisitionThread/run] Function PrepareAcquisition returned {}".format(ret))

                # Perform Acquisition
                ret = self.sdk.StartAcquisition()
                print("[acquisitionThread/run] Function StartAcquisition returned {}".format(ret))

                ret = self.sdk.WaitForAcquisition()
                print("[acquisitionThread/run] Function WaitForAcquisition returned {}".format(ret))
                # Calling the diferent read modes bellow
                readModeOptions[self.readMode]()


                #try:
                #    self.acquisitionFinishedQ.put({"Status": "Finished"})
                #except:
                #    self.acquisitionFinishedQ.get()
                #    self.acquisitionFinishedQ.put({"Status": "Finished"})
                    

                # Saving data
                if self.parent.saveFolderLineEdit.text() != "":
                    fileFormat = self.parent.fileFormatCBox.currentText()
                    print(f"[acquisitionThread/run] Attempting to save data into : {self.parent.saveFolderLineEdit.text()} as {fileFormat}")
                    self.saveSpectrum(fileFormat)
                    
            elif self.mode == "Kinetic series":
                print(f"[acquisitionThread/run] Acquiting kinetic series.")
                
                if "Read mode" not in self.messageDict.keys():
                    print(f"[acquisitionThread/run] Missing read mode. Retrieving from UI.")
                    self.readMode = self.parent.readModeCBox.currentText()
                else:
                    self.readMode = self.messageDict["Read mode"]

                start_time = time.time()
                if "Kinetic series length" in self.messageDict.keys():
                    # If length of kinetic series supplied, use that. 
                    self.series = self.__acquire_series(self.messageDict["Kinetic series length"])
                else:
                    # If not supplied, retrieve from UI
                    self.series = self.__acquire_series(self.parent.kineticsNumScans.value())

                print(f"[acquisitionThread/run] Acquired series: {self.series}.")
                end_time = time.time()
                print(f"[acquisitionThread/run] Total execution time: {end_time - start_time:.3f} s")
                #except:
                #print(f"[acquisitionThread/run] Kinetic series failed.")
                maxValue = 0
                maxSpectrum = 0
                for i, spectrum in enumerate(self.series):
                    if max(spectrum) > maxValue:
                        maxValue = max(spectrum)
                        maxSpectrum = i

                print(f"[acquisitionThread/run] Spectrum with the highest peak is #{maxSpectrum}, values: {self.series[maxSpectrum]}")
                # Sending data for plotting.
                self.plotQ.put({"data": self.series[maxSpectrum], 
                                "dataX": range(0, len(self.series[maxSpectrum])), 
                                "dataY":self.series[maxSpectrum], 
                                "title": f"Single track spectrum {maxSpectrum}", 
                                "type": "spectrum",
                                "xpixels" : self.xpixels,
                                "ypixels" : self.ypixels})
            
            print("[acquisitionThread/run] Finishing task and labelling it as done.")
            self.acquisitionQ.task_done()
            # Closing shutter if it is connected.
            #if self.parent.leftSidePanel.shutterSidebar.connectionStatusLabel.text() == "Connected":
            #    self.parent.leftSidePanel.shutterSidebar.shutterDriver("Close")
            #self.priorCMD("controller.ttl.out.set 0")
            print("------------------------------------------------------------------")
            
                    
    
    def __handle_return(self, ret_value: int) -> int:
        print(f"[__handle_return] Return value is {ret_value}.")
        if (ret_value != atmcd_errors.Error_Codes.DRV_SUCCESS) and (ret_value != atmcd_errors.Error_Codes.DRV_NOT_INITIALIZED):
            raise print(f'{ret_value}')
        return ret_value
    
    def __acquire(self) -> np.ndarray:
        print(f"[acquisitionThread/__acquire] Acquiring single scan.")
        #ret, xpixels, ypixels = self.sdk.GetDetector()
        #self.__handle_return(ret)
        self.beginningTime = time.time()
        print(f"[acquisitionThread/__acquire] Time between scans: {self.beginningTime-self.endTime:.3f} s")
        startTime = time.time()
        prepRet = self.__handle_return(self.sdk.PrepareAcquisition())
        self.__handle_return(self.sdk.StartAcquisition())
        self.__handle_return(self.sdk.WaitForAcquisition())
        prepEndTime = time.time()
        
        if self.messageDict["Read mode"] == "Image":
            imageSize = self.xpixels * self.ypixels
        else:
            imageSize = self.xpixels

        # Simulated data in case the detector is not present.
        if prepRet == atmcd_errors.Error_Codes.DRV_NOT_INITIALIZED:
            print(f"[main/_acquire] Detector not initialized, presenting simulated data.")
            ret, fullFrameBuffer = self.sdk.GetMostRecentImage(imageSize)
            fullFrameBuffer = [987, 984, 978, 971, 977, 973, 979, 981, 982, 992, 992, 999, 1007, 983, 988, 996, 989, 991, 987, 970, 979, 977, 962, 961, 941, 960, 961, 956, 936, 962, 943, 932, 946, 935, 944, 942, 936, 938, 922, 932, 931, 926, 917, 925, 925, 923, 929, 916, 908, 921, 908, 922, 909, 921, 913, 923, 923, 918, 920, 927, 930, 924, 935, 922, 924, 909, 917, 930, 936, 930, 927, 922, 929, 944, 935, 921, 930, 932, 932, 933, 939, 938, 944, 952, 941, 940, 960, 950, 962, 964, 971, 969, 958, 965, 968, 973, 978, 968, 999, 991, 990, 974, 998, 996, 976, 963, 981, 979, 951, 951, 955, 953, 955, 942, 945, 948, 940, 928, 958, 945, 948, 968, 973, 965, 965, 969, 971, 971, 974, 956, 970, 955, 953, 949, 970, 972, 957, 960, 982, 956, 956, 957, 948, 937, 934, 940, 940, 948, 949, 948, 946, 939, 937, 934, 937, 949, 939, 946, 938, 946, 951, 943, 947, 927, 939, 925, 930, 929, 923, 933, 947, 936, 937, 947, 926, 937, 943, 942, 945, 950, 945, 933, 948, 943, 947, 937, 947, 937, 944, 947, 941, 941, 937, 960, 943, 941, 940, 940, 965, 936, 938, 965, 958, 960, 961, 958, 971, 994, 983, 984, 1003, 1029, 1040, 1069, 1080, 1056, 1080, 1077, 1063, 1051, 1064, 1056, 1057, 1046, 1068, 1056, 1076, 1068, 1086, 1080, 1094, 1101, 1102, 1095, 1105, 1117, 1084, 1096, 1077, 1081, 1080, 1065, 1065, 1052, 1054, 1039, 1041, 1033, 1023, 1010, 1014, 997, 1006, 988, 976, 1002, 986, 993, 976, 998, 992, 975, 992, 971, 966, 981, 974, 971, 961, 955, 942, 958, 945, 955, 958, 965, 982, 951, 968, 956, 953, 943, 934, 926, 923, 931, 925, 905, 899, 905, 909, 899, 897, 907, 908, 910, 904, 922, 905, 902, 894, 898, 897, 891, 899, 898, 878, 892, 877, 891, 868, 865, 870, 868, 866, 868, 873, 888, 901, 885, 893, 902, 903, 900, 910, 908, 915, 908, 915, 912, 921, 939, 932, 944, 925, 949, 946, 967, 943, 954, 958, 966, 966, 974, 962, 979, 976, 969, 958, 962, 956, 963, 968, 968, 956, 971, 969, 970, 967, 950, 960, 983, 949, 947, 960, 957, 962, 954, 948, 956, 946, 959, 962, 964, 964, 941, 967, 947, 966, 949, 961, 948, 954, 945, 948, 935, 954, 926, 954, 948, 964, 947, 952, 951, 949, 948, 953, 941, 908, 925, 917, 928, 913, 896, 907, 917, 894, 906, 904, 900, 886, 900, 893, 879, 879, 888, 888, 883, 880, 884, 877, 870, 886, 883, 885, 896, 893, 879, 881, 873, 872, 881, 878, 881, 861, 860, 878, 879, 863, 882, 888, 872, 876, 882, 907, 913, 923, 918, 944, 960, 954, 962, 978, 998, 984, 965, 960, 960, 959, 954, 940, 924, 903, 884, 896, 870, 863, 854, 850, 825, 825, 803, 817, 805, 797, 791, 801, 800, 783, 788, 781, 784, 797, 788, 789, 787, 776, 783, 783, 789, 799, 792, 787, 800, 801, 803, 807, 808, 809, 822, 812, 827, 820, 828, 832, 837, 863, 860, 862, 868, 877, 877, 881, 873, 883, 880, 892, 883, 910, 900, 892, 910, 895, 924, 927, 921, 933, 928, 932, 940, 932, 940, 941, 958, 944, 961, 975, 971, 962, 988, 973, 981, 979, 989, 996, 984, 988, 982, 1003, 1000, 994, 1013, 1006, 1008, 1012, 1009, 1016, 1013, 1026, 1012, 1048, 1023, 1035, 1053, 1036, 1028, 1044, 1057, 1052, 1048, 1053, 1058, 1043, 1059, 1051, 1037, 1043, 1015, 1013, 985, 968, 971, 936, 923, 920, 910, 879, 877, 848, 846, 833, 816, 812, 793, 799, 792, 775, 769, 764, 772, 754, 765, 743, 748, 742, 728, 745, 721, 740, 736, 720, 727, 725, 724, 719, 714, 713, 720, 697, 714, 704, 706, 702, 705, 706, 706, 703, 689, 688, 695, 676, 690, 704, 684, 689, 685, 697, 670, 681, 691, 670, 673, 673, 673, 678, 669, 688, 675, 678, 669, 669, 669, 679, 672, 677, 672, 671, 668, 670, 670, 654, 665, 676, 660, 651, 661, 662, 661, 663, 656, 663, 652, 661, 653, 666, 661, 665, 663, 655, 658, 654, 671, 660, 658, 664, 664, 657, 650, 650, 652, 666, 664, 659, 665, 659, 671, 676, 657, 654, 674, 663, 665, 664, 664, 669, 676, 668, 670, 670, 667, 667, 656, 662, 661, 663, 666, 675, 661, 671, 663, 671, 667, 674, 671, 662, 660, 668, 682, 673, 671, 669, 680, 668, 663, 672, 675, 666, 675, 674, 673, 667, 674, 678, 662, 669, 670, 670, 672, 670, 677, 666, 669, 670, 666, 664, 662, 687, 677, 674, 670, 684, 672, 666, 662, 674, 673, 678, 676, 653, 667, 679, 673, 677, 673, 679, 679, 681, 679, 672, 698, 686, 693, 687, 679, 685, 682, 693, 674, 702, 699, 680, 681, 689, 696, 682, 683, 695, 688, 694, 700, 700, 691, 691, 695, 709, 699, 703, 697, 707, 703, 700, 702, 709, 704, 718, 704, 716, 719, 713, 718, 730, 717, 729, 724, 721, 729, 726, 737, 732, 727, 728, 746, 740, 744, 730, 746, 746, 742, 741, 757, 756, 758, 754, 744, 753, 764, 771, 767, 771, 775, 772, 776, 770, 770, 778, 786, 794, 780, 782, 782, 769, 776, 772, 796, 787, 783, 780, 776, 772, 771, 768, 770, 762, 785, 778, 792, 769, 763, 776, 763, 771, 767, 756, 756, 754, 766, 760, 745, 754, 753, 751, 745, 736, 739, 748, 748, 742, 723, 728, 734, 737, 729, 728, 733, 715, 715, 723, 727, 724, 722, 713, 717, 713, 706, 709, 710, 698, 708, 708, 713, 700, 690, 713, 710, 706, 708, 697, 714, 703, 704, 693, 708, 697, 683, 689, 688, 692, 690, 698, 708, 698, 696, 696, 701, 690, 691, 694, 686, 689, 694, 690, 691, 682, 690, 681, 678, 694, 686, 689, 675, 686, 674, 680, 672, 664, 668, 674, 675, 675, 681, 682, 679, 678, 674, 668, 666, 677, 682, 685, 667, 667, 672, 670, 677, 669, 675, 672, 677, 677, 682, 663, 670, 670, 672, 667, 676, 670, 671, 685, 669, 665, 682, 675, 657, 670, 667, 670, 675, 670, 659, 662, 682, 664, 684, 667, 680, 680, 673, 674, 676, 675, 678, 673, 671] 

        else:
            ret, fullFrameBuffer = self.sdk.GetMostRecentImage(imageSize)

        self.__handle_return(ret)
        endTime = time.time()
        print(f"[acquisitionThread/__acquire] Prep time: {prepEndTime-startTime:.3f} s. Acquisition time: {prepEndTime-endTime:.3f} s")
        self.endTime = time.time()
        return np.ctypeslib.as_array(fullFrameBuffer)

    def __acquire_series(self, length: int) -> List[np.ndarray]:
        series = []
        # Measuring time of execution
        self.endTime = time.time()
        for i in range(length):
            series.append(self.__acquire())
        return series
    """
    --------------------------------------------------------------------------------
    Methods of acquisition that are used by the startAcquisition function uniquely
    --------------------------------------------------------------------------------
    """
    def __fullVerticalBinning(self):
        print("[acquisitionThread/run] Full vertical binning")

        imageSize = self.xpixels
        try:
            (ret, self.arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
            print(f"[startAcquisition/run] Function GetImages16 returned {ret} first pixel = {self.arr[0]} size = {imageSize}")
            self.plotQ.put({"data": self.arr, 
                            "dataX": np.array(self.calibrationValues), 
                            #"dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Full vertical binning", 
                            "type": "spectrum",
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
        except:
            # Placeholder plot in case the attempts fails
            imageSize = 1024
            self.arr = [987, 984, 978, 971, 977, 973, 979, 981, 982, 992, 992, 999, 1007, 983, 988, 996, 989, 991, 987, 970, 979, 977, 962, 961, 941, 960, 961, 956, 936, 962, 943, 932, 946, 935, 944, 942, 936, 938, 922, 932, 931, 926, 917, 925, 925, 923, 929, 916, 908, 921, 908, 922, 909, 921, 913, 923, 923, 918, 920, 927, 930, 924, 935, 922, 924, 909, 917, 930, 936, 930, 927, 922, 929, 944, 935, 921, 930, 932, 932, 933, 939, 938, 944, 952, 941, 940, 960, 950, 962, 964, 971, 969, 958, 965, 968, 973, 978, 968, 999, 991, 990, 974, 998, 996, 976, 963, 981, 979, 951, 951, 955, 953, 955, 942, 945, 948, 940, 928, 958, 945, 948, 968, 973, 965, 965, 969, 971, 971, 974, 956, 970, 955, 953, 949, 970, 972, 957, 960, 982, 956, 956, 957, 948, 937, 934, 940, 940, 948, 949, 948, 946, 939, 937, 934, 937, 949, 939, 946, 938, 946, 951, 943, 947, 927, 939, 925, 930, 929, 923, 933, 947, 936, 937, 947, 926, 937, 943, 942, 945, 950, 945, 933, 948, 943, 947, 937, 947, 937, 944, 947, 941, 941, 937, 960, 943, 941, 940, 940, 965, 936, 938, 965, 958, 960, 961, 958, 971, 994, 983, 984, 1003, 1029, 1040, 1069, 1080, 1056, 1080, 1077, 1063, 1051, 1064, 1056, 1057, 1046, 1068, 1056, 1076, 1068, 1086, 1080, 1094, 1101, 1102, 1095, 1105, 1117, 1084, 1096, 1077, 1081, 1080, 1065, 1065, 1052, 1054, 1039, 1041, 1033, 1023, 1010, 1014, 997, 1006, 988, 976, 1002, 986, 993, 976, 998, 992, 975, 992, 971, 966, 981, 974, 971, 961, 955, 942, 958, 945, 955, 958, 965, 982, 951, 968, 956, 953, 943, 934, 926, 923, 931, 925, 905, 899, 905, 909, 899, 897, 907, 908, 910, 904, 922, 905, 902, 894, 898, 897, 891, 899, 898, 878, 892, 877, 891, 868, 865, 870, 868, 866, 868, 873, 888, 901, 885, 893, 902, 903, 900, 910, 908, 915, 908, 915, 912, 921, 939, 932, 944, 925, 949, 946, 967, 943, 954, 958, 966, 966, 974, 962, 979, 976, 969, 958, 962, 956, 963, 968, 968, 956, 971, 969, 970, 967, 950, 960, 983, 949, 947, 960, 957, 962, 954, 948, 956, 946, 959, 962, 964, 964, 941, 967, 947, 966, 949, 961, 948, 954, 945, 948, 935, 954, 926, 954, 948, 964, 947, 952, 951, 949, 948, 953, 941, 908, 925, 917, 928, 913, 896, 907, 917, 894, 906, 904, 900, 886, 900, 893, 879, 879, 888, 888, 883, 880, 884, 877, 870, 886, 883, 885, 896, 893, 879, 881, 873, 872, 881, 878, 881, 861, 860, 878, 879, 863, 882, 888, 872, 876, 882, 907, 913, 923, 918, 944, 960, 954, 962, 978, 998, 984, 965, 960, 960, 959, 954, 940, 924, 903, 884, 896, 870, 863, 854, 850, 825, 825, 803, 817, 805, 797, 791, 801, 800, 783, 788, 781, 784, 797, 788, 789, 787, 776, 783, 783, 789, 799, 792, 787, 800, 801, 803, 807, 808, 809, 822, 812, 827, 820, 828, 832, 837, 863, 860, 862, 868, 877, 877, 881, 873, 883, 880, 892, 883, 910, 900, 892, 910, 895, 924, 927, 921, 933, 928, 932, 940, 932, 940, 941, 958, 944, 961, 975, 971, 962, 988, 973, 981, 979, 989, 996, 984, 988, 982, 1003, 1000, 994, 1013, 1006, 1008, 1012, 1009, 1016, 1013, 1026, 1012, 1048, 1023, 1035, 1053, 1036, 1028, 1044, 1057, 1052, 1048, 1053, 1058, 1043, 1059, 1051, 1037, 1043, 1015, 1013, 985, 968, 971, 936, 923, 920, 910, 879, 877, 848, 846, 833, 816, 812, 793, 799, 792, 775, 769, 764, 772, 754, 765, 743, 748, 742, 728, 745, 721, 740, 736, 720, 727, 725, 724, 719, 714, 713, 720, 697, 714, 704, 706, 702, 705, 706, 706, 703, 689, 688, 695, 676, 690, 704, 684, 689, 685, 697, 670, 681, 691, 670, 673, 673, 673, 678, 669, 688, 675, 678, 669, 669, 669, 679, 672, 677, 672, 671, 668, 670, 670, 654, 665, 676, 660, 651, 661, 662, 661, 663, 656, 663, 652, 661, 653, 666, 661, 665, 663, 655, 658, 654, 671, 660, 658, 664, 664, 657, 650, 650, 652, 666, 664, 659, 665, 659, 671, 676, 657, 654, 674, 663, 665, 664, 664, 669, 676, 668, 670, 670, 667, 667, 656, 662, 661, 663, 666, 675, 661, 671, 663, 671, 667, 674, 671, 662, 660, 668, 682, 673, 671, 669, 680, 668, 663, 672, 675, 666, 675, 674, 673, 667, 674, 678, 662, 669, 670, 670, 672, 670, 677, 666, 669, 670, 666, 664, 662, 687, 677, 674, 670, 684, 672, 666, 662, 674, 673, 678, 676, 653, 667, 679, 673, 677, 673, 679, 679, 681, 679, 672, 698, 686, 693, 687, 679, 685, 682, 693, 674, 702, 699, 680, 681, 689, 696, 682, 683, 695, 688, 694, 700, 700, 691, 691, 695, 709, 699, 703, 697, 707, 703, 700, 702, 709, 704, 718, 704, 716, 719, 713, 718, 730, 717, 729, 724, 721, 729, 726, 737, 732, 727, 728, 746, 740, 744, 730, 746, 746, 742, 741, 757, 756, 758, 754, 744, 753, 764, 771, 767, 771, 775, 772, 776, 770, 770, 778, 786, 794, 780, 782, 782, 769, 776, 772, 796, 787, 783, 780, 776, 772, 771, 768, 770, 762, 785, 778, 792, 769, 763, 776, 763, 771, 767, 756, 756, 754, 766, 760, 745, 754, 753, 751, 745, 736, 739, 748, 748, 742, 723, 728, 734, 737, 729, 728, 733, 715, 715, 723, 727, 724, 722, 713, 717, 713, 706, 709, 710, 698, 708, 708, 713, 700, 690, 713, 710, 706, 708, 697, 714, 703, 704, 693, 708, 697, 683, 689, 688, 692, 690, 698, 708, 698, 696, 696, 701, 690, 691, 694, 686, 689, 694, 690, 691, 682, 690, 681, 678, 694, 686, 689, 675, 686, 674, 680, 672, 664, 668, 674, 675, 675, 681, 682, 679, 678, 674, 668, 666, 677, 682, 685, 667, 667, 672, 670, 677, 669, 675, 672, 677, 677, 682, 663, 670, 670, 672, 667, 676, 670, 671, 685, 669, 665, 682, 675, 657, 670, 667, 670, 675, 670, 659, 662, 682, 664, 684, 667, 680, 680, 673, 674, 676, 675, 678, 673, 671] 
            self.plotQ.put({"data": self.arr, 
                            "dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Full vertical binning", 
                            "type": "spectrum",
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Full vertical binning")
            print(f"[startAcquisition] Failed attempt. Presenting a placeholder image!")

    def __singleTrack(self):
        print("[main] Single track")

        imageSize = self.xpixels
        try:
            (ret, self.arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
            print(f"[startAcquisition/__singleTrack] Function GetImages16 returned {ret} first pixel = {self.arr[0]} size = {imageSize}")
            print(f"[startAcquisition/__singleTrack] data: {self.arr}")
            self.plotQ.put({"data": self.arr, 
                            "dataX": np.array(self.calibrationValues),
                            #"dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Single track", 
                            "type": "spectrum", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Single track")
        except:
            # Placeholder plot in case the attempts fails
            imageSize = 1024
            self.arr = [987, 984, 978, 971, 977, 973, 979, 981, 982, 992, 992, 999, 1007, 983, 988, 996, 989, 991, 987, 970, 979, 977, 962, 961, 941, 960, 961, 956, 936, 962, 943, 932, 946, 935, 944, 942, 936, 938, 922, 932, 931, 926, 917, 925, 925, 923, 929, 916, 908, 921, 908, 922, 909, 921, 913, 923, 923, 918, 920, 927, 930, 924, 935, 922, 924, 909, 917, 930, 936, 930, 927, 922, 929, 944, 935, 921, 930, 932, 932, 933, 939, 938, 944, 952, 941, 940, 960, 950, 962, 964, 971, 969, 958, 965, 968, 973, 978, 968, 999, 991, 990, 974, 998, 996, 976, 963, 981, 979, 951, 951, 955, 953, 955, 942, 945, 948, 940, 928, 958, 945, 948, 968, 973, 965, 965, 969, 971, 971, 974, 956, 970, 955, 953, 949, 970, 972, 957, 960, 982, 956, 956, 957, 948, 937, 934, 940, 940, 948, 949, 948, 946, 939, 937, 934, 937, 949, 939, 946, 938, 946, 951, 943, 947, 927, 939, 925, 930, 929, 923, 933, 947, 936, 937, 947, 926, 937, 943, 942, 945, 950, 945, 933, 948, 943, 947, 937, 947, 937, 944, 947, 941, 941, 937, 960, 943, 941, 940, 940, 965, 936, 938, 965, 958, 960, 961, 958, 971, 994, 983, 984, 1003, 1029, 1040, 1069, 1080, 1056, 1080, 1077, 1063, 1051, 1064, 1056, 1057, 1046, 1068, 1056, 1076, 1068, 1086, 1080, 1094, 1101, 1102, 1095, 1105, 1117, 1084, 1096, 1077, 1081, 1080, 1065, 1065, 1052, 1054, 1039, 1041, 1033, 1023, 1010, 1014, 997, 1006, 988, 976, 1002, 986, 993, 976, 998, 992, 975, 992, 971, 966, 981, 974, 971, 961, 955, 942, 958, 945, 955, 958, 965, 982, 951, 968, 956, 953, 943, 934, 926, 923, 931, 925, 905, 899, 905, 909, 899, 897, 907, 908, 910, 904, 922, 905, 902, 894, 898, 897, 891, 899, 898, 878, 892, 877, 891, 868, 865, 870, 868, 866, 868, 873, 888, 901, 885, 893, 902, 903, 900, 910, 908, 915, 908, 915, 912, 921, 939, 932, 944, 925, 949, 946, 967, 943, 954, 958, 966, 966, 974, 962, 979, 976, 969, 958, 962, 956, 963, 968, 968, 956, 971, 969, 970, 967, 950, 960, 983, 949, 947, 960, 957, 962, 954, 948, 956, 946, 959, 962, 964, 964, 941, 967, 947, 966, 949, 961, 948, 954, 945, 948, 935, 954, 926, 954, 948, 964, 947, 952, 951, 949, 948, 953, 941, 908, 925, 917, 928, 913, 896, 907, 917, 894, 906, 904, 900, 886, 900, 893, 879, 879, 888, 888, 883, 880, 884, 877, 870, 886, 883, 885, 896, 893, 879, 881, 873, 872, 881, 878, 881, 861, 860, 878, 879, 863, 882, 888, 872, 876, 882, 907, 913, 923, 918, 944, 960, 954, 962, 978, 998, 984, 965, 960, 960, 959, 954, 940, 924, 903, 884, 896, 870, 863, 854, 850, 825, 825, 803, 817, 805, 797, 791, 801, 800, 783, 788, 781, 784, 797, 788, 789, 787, 776, 783, 783, 789, 799, 792, 787, 800, 801, 803, 807, 808, 809, 822, 812, 827, 820, 828, 832, 837, 863, 860, 862, 868, 877, 877, 881, 873, 883, 880, 892, 883, 910, 900, 892, 910, 895, 924, 927, 921, 933, 928, 932, 940, 932, 940, 941, 958, 944, 961, 975, 971, 962, 988, 973, 981, 979, 989, 996, 984, 988, 982, 1003, 1000, 994, 1013, 1006, 1008, 1012, 1009, 1016, 1013, 1026, 1012, 1048, 1023, 1035, 1053, 1036, 1028, 1044, 1057, 1052, 1048, 1053, 1058, 1043, 1059, 1051, 1037, 1043, 1015, 1013, 985, 968, 971, 936, 923, 920, 910, 879, 877, 848, 846, 833, 816, 812, 793, 799, 792, 775, 769, 764, 772, 754, 765, 743, 748, 742, 728, 745, 721, 740, 736, 720, 727, 725, 724, 719, 714, 713, 720, 697, 714, 704, 706, 702, 705, 706, 706, 703, 689, 688, 695, 676, 690, 704, 684, 689, 685, 697, 670, 681, 691, 670, 673, 673, 673, 678, 669, 688, 675, 678, 669, 669, 669, 679, 672, 677, 672, 671, 668, 670, 670, 654, 665, 676, 660, 651, 661, 662, 661, 663, 656, 663, 652, 661, 653, 666, 661, 665, 663, 655, 658, 654, 671, 660, 658, 664, 664, 657, 650, 650, 652, 666, 664, 659, 665, 659, 671, 676, 657, 654, 674, 663, 665, 664, 664, 669, 676, 668, 670, 670, 667, 667, 656, 662, 661, 663, 666, 675, 661, 671, 663, 671, 667, 674, 671, 662, 660, 668, 682, 673, 671, 669, 680, 668, 663, 672, 675, 666, 675, 674, 673, 667, 674, 678, 662, 669, 670, 670, 672, 670, 677, 666, 669, 670, 666, 664, 662, 687, 677, 674, 670, 684, 672, 666, 662, 674, 673, 678, 676, 653, 667, 679, 673, 677, 673, 679, 679, 681, 679, 672, 698, 686, 693, 687, 679, 685, 682, 693, 674, 702, 699, 680, 681, 689, 696, 682, 683, 695, 688, 694, 700, 700, 691, 691, 695, 709, 699, 703, 697, 707, 703, 700, 702, 709, 704, 718, 704, 716, 719, 713, 718, 730, 717, 729, 724, 721, 729, 726, 737, 732, 727, 728, 746, 740, 744, 730, 746, 746, 742, 741, 757, 756, 758, 754, 744, 753, 764, 771, 767, 771, 775, 772, 776, 770, 770, 778, 786, 794, 780, 782, 782, 769, 776, 772, 796, 787, 783, 780, 776, 772, 771, 768, 770, 762, 785, 778, 792, 769, 763, 776, 763, 771, 767, 756, 756, 754, 766, 760, 745, 754, 753, 751, 745, 736, 739, 748, 748, 742, 723, 728, 734, 737, 729, 728, 733, 715, 715, 723, 727, 724, 722, 713, 717, 713, 706, 709, 710, 698, 708, 708, 713, 700, 690, 713, 710, 706, 708, 697, 714, 703, 704, 693, 708, 697, 683, 689, 688, 692, 690, 698, 708, 698, 696, 696, 701, 690, 691, 694, 686, 689, 694, 690, 691, 682, 690, 681, 678, 694, 686, 689, 675, 686, 674, 680, 672, 664, 668, 674, 675, 675, 681, 682, 679, 678, 674, 668, 666, 677, 682, 685, 667, 667, 672, 670, 677, 669, 675, 672, 677, 677, 682, 663, 670, 670, 672, 667, 676, 670, 671, 685, 669, 665, 682, 675, 657, 670, 667, 670, 675, 670, 659, 662, 682, 664, 684, 667, 680, 680, 673, 674, 676, 675, 678, 673, 671] 
            self.plotQ.put({"data": self.arr, 
                            "dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "PLACEHOLDER IMAGE: Single track", 
                            "type": "spectrum",
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Single track")
            print(f"[startAcquisition] Failed attempt. Presenting a placeholder image!")

    def __multiTrack(self):
        print("[main] Multi track")

        imageSize = self.xpixels
        try:
            (ret, self.arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
            print(f"[startAcquisition] Function GetImages16 returned {ret} first pixel = {self.arr[0]} size = {imageSize}")
            self.plotQ.put({"data": self.arr, 
                            "dataX": np.array(self.calibrationValues),
                            #"dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Multi track", 
                            "type": "spectrum", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Multi track")
        except:
            # Placeholder plot in case the attempts fails
            imageSize = 1024
            self.arr = [987, 984, 978, 971, 977, 973, 979, 981, 982, 992, 992, 999, 1007, 983, 988, 996, 989, 991, 987, 970, 979, 977, 962, 961, 941, 960, 961, 956, 936, 962, 943, 932, 946, 935, 944, 942, 936, 938, 922, 932, 931, 926, 917, 925, 925, 923, 929, 916, 908, 921, 908, 922, 909, 921, 913, 923, 923, 918, 920, 927, 930, 924, 935, 922, 924, 909, 917, 930, 936, 930, 927, 922, 929, 944, 935, 921, 930, 932, 932, 933, 939, 938, 944, 952, 941, 940, 960, 950, 962, 964, 971, 969, 958, 965, 968, 973, 978, 968, 999, 991, 990, 974, 998, 996, 976, 963, 981, 979, 951, 951, 955, 953, 955, 942, 945, 948, 940, 928, 958, 945, 948, 968, 973, 965, 965, 969, 971, 971, 974, 956, 970, 955, 953, 949, 970, 972, 957, 960, 982, 956, 956, 957, 948, 937, 934, 940, 940, 948, 949, 948, 946, 939, 937, 934, 937, 949, 939, 946, 938, 946, 951, 943, 947, 927, 939, 925, 930, 929, 923, 933, 947, 936, 937, 947, 926, 937, 943, 942, 945, 950, 945, 933, 948, 943, 947, 937, 947, 937, 944, 947, 941, 941, 937, 960, 943, 941, 940, 940, 965, 936, 938, 965, 958, 960, 961, 958, 971, 994, 983, 984, 1003, 1029, 1040, 1069, 1080, 1056, 1080, 1077, 1063, 1051, 1064, 1056, 1057, 1046, 1068, 1056, 1076, 1068, 1086, 1080, 1094, 1101, 1102, 1095, 1105, 1117, 1084, 1096, 1077, 1081, 1080, 1065, 1065, 1052, 1054, 1039, 1041, 1033, 1023, 1010, 1014, 997, 1006, 988, 976, 1002, 986, 993, 976, 998, 992, 975, 992, 971, 966, 981, 974, 971, 961, 955, 942, 958, 945, 955, 958, 965, 982, 951, 968, 956, 953, 943, 934, 926, 923, 931, 925, 905, 899, 905, 909, 899, 897, 907, 908, 910, 904, 922, 905, 902, 894, 898, 897, 891, 899, 898, 878, 892, 877, 891, 868, 865, 870, 868, 866, 868, 873, 888, 901, 885, 893, 902, 903, 900, 910, 908, 915, 908, 915, 912, 921, 939, 932, 944, 925, 949, 946, 967, 943, 954, 958, 966, 966, 974, 962, 979, 976, 969, 958, 962, 956, 963, 968, 968, 956, 971, 969, 970, 967, 950, 960, 983, 949, 947, 960, 957, 962, 954, 948, 956, 946, 959, 962, 964, 964, 941, 967, 947, 966, 949, 961, 948, 954, 945, 948, 935, 954, 926, 954, 948, 964, 947, 952, 951, 949, 948, 953, 941, 908, 925, 917, 928, 913, 896, 907, 917, 894, 906, 904, 900, 886, 900, 893, 879, 879, 888, 888, 883, 880, 884, 877, 870, 886, 883, 885, 896, 893, 879, 881, 873, 872, 881, 878, 881, 861, 860, 878, 879, 863, 882, 888, 872, 876, 882, 907, 913, 923, 918, 944, 960, 954, 962, 978, 998, 984, 965, 960, 960, 959, 954, 940, 924, 903, 884, 896, 870, 863, 854, 850, 825, 825, 803, 817, 805, 797, 791, 801, 800, 783, 788, 781, 784, 797, 788, 789, 787, 776, 783, 783, 789, 799, 792, 787, 800, 801, 803, 807, 808, 809, 822, 812, 827, 820, 828, 832, 837, 863, 860, 862, 868, 877, 877, 881, 873, 883, 880, 892, 883, 910, 900, 892, 910, 895, 924, 927, 921, 933, 928, 932, 940, 932, 940, 941, 958, 944, 961, 975, 971, 962, 988, 973, 981, 979, 989, 996, 984, 988, 982, 1003, 1000, 994, 1013, 1006, 1008, 1012, 1009, 1016, 1013, 1026, 1012, 1048, 1023, 1035, 1053, 1036, 1028, 1044, 1057, 1052, 1048, 1053, 1058, 1043, 1059, 1051, 1037, 1043, 1015, 1013, 985, 968, 971, 936, 923, 920, 910, 879, 877, 848, 846, 833, 816, 812, 793, 799, 792, 775, 769, 764, 772, 754, 765, 743, 748, 742, 728, 745, 721, 740, 736, 720, 727, 725, 724, 719, 714, 713, 720, 697, 714, 704, 706, 702, 705, 706, 706, 703, 689, 688, 695, 676, 690, 704, 684, 689, 685, 697, 670, 681, 691, 670, 673, 673, 673, 678, 669, 688, 675, 678, 669, 669, 669, 679, 672, 677, 672, 671, 668, 670, 670, 654, 665, 676, 660, 651, 661, 662, 661, 663, 656, 663, 652, 661, 653, 666, 661, 665, 663, 655, 658, 654, 671, 660, 658, 664, 664, 657, 650, 650, 652, 666, 664, 659, 665, 659, 671, 676, 657, 654, 674, 663, 665, 664, 664, 669, 676, 668, 670, 670, 667, 667, 656, 662, 661, 663, 666, 675, 661, 671, 663, 671, 667, 674, 671, 662, 660, 668, 682, 673, 671, 669, 680, 668, 663, 672, 675, 666, 675, 674, 673, 667, 674, 678, 662, 669, 670, 670, 672, 670, 677, 666, 669, 670, 666, 664, 662, 687, 677, 674, 670, 684, 672, 666, 662, 674, 673, 678, 676, 653, 667, 679, 673, 677, 673, 679, 679, 681, 679, 672, 698, 686, 693, 687, 679, 685, 682, 693, 674, 702, 699, 680, 681, 689, 696, 682, 683, 695, 688, 694, 700, 700, 691, 691, 695, 709, 699, 703, 697, 707, 703, 700, 702, 709, 704, 718, 704, 716, 719, 713, 718, 730, 717, 729, 724, 721, 729, 726, 737, 732, 727, 728, 746, 740, 744, 730, 746, 746, 742, 741, 757, 756, 758, 754, 744, 753, 764, 771, 767, 771, 775, 772, 776, 770, 770, 778, 786, 794, 780, 782, 782, 769, 776, 772, 796, 787, 783, 780, 776, 772, 771, 768, 770, 762, 785, 778, 792, 769, 763, 776, 763, 771, 767, 756, 756, 754, 766, 760, 745, 754, 753, 751, 745, 736, 739, 748, 748, 742, 723, 728, 734, 737, 729, 728, 733, 715, 715, 723, 727, 724, 722, 713, 717, 713, 706, 709, 710, 698, 708, 708, 713, 700, 690, 713, 710, 706, 708, 697, 714, 703, 704, 693, 708, 697, 683, 689, 688, 692, 690, 698, 708, 698, 696, 696, 701, 690, 691, 694, 686, 689, 694, 690, 691, 682, 690, 681, 678, 694, 686, 689, 675, 686, 674, 680, 672, 664, 668, 674, 675, 675, 681, 682, 679, 678, 674, 668, 666, 677, 682, 685, 667, 667, 672, 670, 677, 669, 675, 672, 677, 677, 682, 663, 670, 670, 672, 667, 676, 670, 671, 685, 669, 665, 682, 675, 657, 670, 667, 670, 675, 670, 659, 662, 682, 664, 684, 667, 680, 680, 673, 674, 676, 675, 678, 673, 671] 
            self.plotQ.put({"data": self.arr, 
                            "dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "PLACEHOLDER IMAGE: Multi track", 
                            "type": "spectrum", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Multi track")
            print(f"[startAcquisition] Failed attempt. Presenting a placeholder image!")

    def __randomTrack(self):
        print("[main] Random track")

        imageSize = self.xpixels
        try:
            (ret, self.arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
            print(f"[startAcquisition] Function GetImages16 returned {ret} first pixel = {self.arr[0]} size = {imageSize}")
            self.plotQ.put({"data": self.arr, 
                            "dataX": np.array(self.calibrationValues),
                            #"dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Random track", 
                            "type": "spectrum", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Random track")
        except:
            # Placeholder plot in case the attempts fails
            imageSize = 1024
            self.arr = [987, 984, 978, 971, 977, 973, 979, 981, 982, 992, 992, 999, 1007, 983, 988, 996, 989, 991, 987, 970, 979, 977, 962, 961, 941, 960, 961, 956, 936, 962, 943, 932, 946, 935, 944, 942, 936, 938, 922, 932, 931, 926, 917, 925, 925, 923, 929, 916, 908, 921, 908, 922, 909, 921, 913, 923, 923, 918, 920, 927, 930, 924, 935, 922, 924, 909, 917, 930, 936, 930, 927, 922, 929, 944, 935, 921, 930, 932, 932, 933, 939, 938, 944, 952, 941, 940, 960, 950, 962, 964, 971, 969, 958, 965, 968, 973, 978, 968, 999, 991, 990, 974, 998, 996, 976, 963, 981, 979, 951, 951, 955, 953, 955, 942, 945, 948, 940, 928, 958, 945, 948, 968, 973, 965, 965, 969, 971, 971, 974, 956, 970, 955, 953, 949, 970, 972, 957, 960, 982, 956, 956, 957, 948, 937, 934, 940, 940, 948, 949, 948, 946, 939, 937, 934, 937, 949, 939, 946, 938, 946, 951, 943, 947, 927, 939, 925, 930, 929, 923, 933, 947, 936, 937, 947, 926, 937, 943, 942, 945, 950, 945, 933, 948, 943, 947, 937, 947, 937, 944, 947, 941, 941, 937, 960, 943, 941, 940, 940, 965, 936, 938, 965, 958, 960, 961, 958, 971, 994, 983, 984, 1003, 1029, 1040, 1069, 1080, 1056, 1080, 1077, 1063, 1051, 1064, 1056, 1057, 1046, 1068, 1056, 1076, 1068, 1086, 1080, 1094, 1101, 1102, 1095, 1105, 1117, 1084, 1096, 1077, 1081, 1080, 1065, 1065, 1052, 1054, 1039, 1041, 1033, 1023, 1010, 1014, 997, 1006, 988, 976, 1002, 986, 993, 976, 998, 992, 975, 992, 971, 966, 981, 974, 971, 961, 955, 942, 958, 945, 955, 958, 965, 982, 951, 968, 956, 953, 943, 934, 926, 923, 931, 925, 905, 899, 905, 909, 899, 897, 907, 908, 910, 904, 922, 905, 902, 894, 898, 897, 891, 899, 898, 878, 892, 877, 891, 868, 865, 870, 868, 866, 868, 873, 888, 901, 885, 893, 902, 903, 900, 910, 908, 915, 908, 915, 912, 921, 939, 932, 944, 925, 949, 946, 967, 943, 954, 958, 966, 966, 974, 962, 979, 976, 969, 958, 962, 956, 963, 968, 968, 956, 971, 969, 970, 967, 950, 960, 983, 949, 947, 960, 957, 962, 954, 948, 956, 946, 959, 962, 964, 964, 941, 967, 947, 966, 949, 961, 948, 954, 945, 948, 935, 954, 926, 954, 948, 964, 947, 952, 951, 949, 948, 953, 941, 908, 925, 917, 928, 913, 896, 907, 917, 894, 906, 904, 900, 886, 900, 893, 879, 879, 888, 888, 883, 880, 884, 877, 870, 886, 883, 885, 896, 893, 879, 881, 873, 872, 881, 878, 881, 861, 860, 878, 879, 863, 882, 888, 872, 876, 882, 907, 913, 923, 918, 944, 960, 954, 962, 978, 998, 984, 965, 960, 960, 959, 954, 940, 924, 903, 884, 896, 870, 863, 854, 850, 825, 825, 803, 817, 805, 797, 791, 801, 800, 783, 788, 781, 784, 797, 788, 789, 787, 776, 783, 783, 789, 799, 792, 787, 800, 801, 803, 807, 808, 809, 822, 812, 827, 820, 828, 832, 837, 863, 860, 862, 868, 877, 877, 881, 873, 883, 880, 892, 883, 910, 900, 892, 910, 895, 924, 927, 921, 933, 928, 932, 940, 932, 940, 941, 958, 944, 961, 975, 971, 962, 988, 973, 981, 979, 989, 996, 984, 988, 982, 1003, 1000, 994, 1013, 1006, 1008, 1012, 1009, 1016, 1013, 1026, 1012, 1048, 1023, 1035, 1053, 1036, 1028, 1044, 1057, 1052, 1048, 1053, 1058, 1043, 1059, 1051, 1037, 1043, 1015, 1013, 985, 968, 971, 936, 923, 920, 910, 879, 877, 848, 846, 833, 816, 812, 793, 799, 792, 775, 769, 764, 772, 754, 765, 743, 748, 742, 728, 745, 721, 740, 736, 720, 727, 725, 724, 719, 714, 713, 720, 697, 714, 704, 706, 702, 705, 706, 706, 703, 689, 688, 695, 676, 690, 704, 684, 689, 685, 697, 670, 681, 691, 670, 673, 673, 673, 678, 669, 688, 675, 678, 669, 669, 669, 679, 672, 677, 672, 671, 668, 670, 670, 654, 665, 676, 660, 651, 661, 662, 661, 663, 656, 663, 652, 661, 653, 666, 661, 665, 663, 655, 658, 654, 671, 660, 658, 664, 664, 657, 650, 650, 652, 666, 664, 659, 665, 659, 671, 676, 657, 654, 674, 663, 665, 664, 664, 669, 676, 668, 670, 670, 667, 667, 656, 662, 661, 663, 666, 675, 661, 671, 663, 671, 667, 674, 671, 662, 660, 668, 682, 673, 671, 669, 680, 668, 663, 672, 675, 666, 675, 674, 673, 667, 674, 678, 662, 669, 670, 670, 672, 670, 677, 666, 669, 670, 666, 664, 662, 687, 677, 674, 670, 684, 672, 666, 662, 674, 673, 678, 676, 653, 667, 679, 673, 677, 673, 679, 679, 681, 679, 672, 698, 686, 693, 687, 679, 685, 682, 693, 674, 702, 699, 680, 681, 689, 696, 682, 683, 695, 688, 694, 700, 700, 691, 691, 695, 709, 699, 703, 697, 707, 703, 700, 702, 709, 704, 718, 704, 716, 719, 713, 718, 730, 717, 729, 724, 721, 729, 726, 737, 732, 727, 728, 746, 740, 744, 730, 746, 746, 742, 741, 757, 756, 758, 754, 744, 753, 764, 771, 767, 771, 775, 772, 776, 770, 770, 778, 786, 794, 780, 782, 782, 769, 776, 772, 796, 787, 783, 780, 776, 772, 771, 768, 770, 762, 785, 778, 792, 769, 763, 776, 763, 771, 767, 756, 756, 754, 766, 760, 745, 754, 753, 751, 745, 736, 739, 748, 748, 742, 723, 728, 734, 737, 729, 728, 733, 715, 715, 723, 727, 724, 722, 713, 717, 713, 706, 709, 710, 698, 708, 708, 713, 700, 690, 713, 710, 706, 708, 697, 714, 703, 704, 693, 708, 697, 683, 689, 688, 692, 690, 698, 708, 698, 696, 696, 701, 690, 691, 694, 686, 689, 694, 690, 691, 682, 690, 681, 678, 694, 686, 689, 675, 686, 674, 680, 672, 664, 668, 674, 675, 675, 681, 682, 679, 678, 674, 668, 666, 677, 682, 685, 667, 667, 672, 670, 677, 669, 675, 672, 677, 677, 682, 663, 670, 670, 672, 667, 676, 670, 671, 685, 669, 665, 682, 675, 657, 670, 667, 670, 675, 670, 659, 662, 682, 664, 684, 667, 680, 680, 673, 674, 676, 675, 678, 673, 671] 
            self.plotQ.put({"data": self.arr, 
                            "dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "PLACEHOLDER IMAGE: Random track", 
                            "type": "spectrum", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
            #self.plot.updatePlotLine(dataX = range(0, len(arr)), dataY = arr, title = "Random track")
            print(f"[startAcquisition] Failed attempt. Presenting a placeholder image!")
    
    def __image(self):
        print("[main] Image")

        imageSize = self.xpixels*self.ypixels
        try:
            (ret, self.arr, validfirst, validlast) = self.sdk.GetImages16(1, 1, imageSize)
            print(f"[startAcquisition] Function GetImages16 returned {ret} first pixel = {self.arr[0]} size = {imageSize}")
            #self.plot.updatePlotHeatmap(data = arr, xpixels=self.xpixels, ypixels=self.ypixels, title = "Image")
            self.plotQ.put({"data": self.arr, 
                            "dataX": np.array(self.calibrationValues),
                            # "dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Detector image", 
                            "type": "image",
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})
        except:
            self.arr = np.random.random((16, 64))
            self.arr = pd.read_csv("test/example.csv.gz", index_col=0)
            self.arr = self.arr.transpose()
            self.arr = self.arr.to_numpy()
            #self.plot.updatePlotHeatmap(data = arr, xpixels=64, ypixels=16, title = "Image")
            self.plotQ.put({"data": self.arr, 
                            "dataX": range(0, len(self.arr)), 
                            "dataY": self.arr, 
                            "title": "Detector image", 
                            "type": "image", 
                            "xpixels" : self.xpixels,
                            "ypixels" : self.ypixels})            
            print(f"[startAcquisition] Failed attempt. Presenting a placeholder image!")

    def _scanArea(self):
        print(f"[acquisitionThread/scanAread] Starting a scanning sequence.")

    """
    --------------------------------------------------------------------------------
    End of methods of acquisition that are used by the startAcquisition function uniquely
    --------------------------------------------------------------------------------
    """
    """
    while True:
        time.sleep(3)
        try:
            (ret, temperature) = self.sdk.GetTemperature()
        except:
            print("[TemperatureThread] Skipping temperature reading.")
        self.change_value.emit(int(ret),int(temperature))
        #self.currentTemperature.setText(str(temperature) + " °C")
        #print(f"Function GetTemperature returned {ret} current temperature = {temperature} ", end='\r')
    """
    def getOutputModeCBox(self):
        comboDict = {"File 16 bit sequence": atmcd_codes.Spool_Mode.FILE_16_BIT_SEQUENCE,
                     "File 32 bit sequence": atmcd_codes.Spool_Mode.FILE_32_BIT_SEQUENCE,
                     "Data dependent": atmcd_codes.Spool_Mode.DATA_DEPENDENT_FORMAT,
                     "Multiple dirs": atmcd_codes.Spool_Mode.MULTIPLE_DIRECTORY_STRUCTURE,
                     "Compressed multiple dirs": atmcd_codes.Spool_Mode.COMPRESSED_MULTIPLE_DIRECTORY_STRUCTURE,
                     "Save to RAM": atmcd_codes.Spool_Mode.SPOOL_TO_RAM,
                     "Save to SIF": atmcd_codes.Spool_Mode.SPOOL_TO_SIF
                    }

        self.selectedMode = self.parent.outputModeCBox.currentText()

        return comboDict[self.selectedMode], self.selectedMode
    
    def saveSpectrum(self, fileFormat):
        
        comboDict = {"Direct save": self._directSave,
                     "Raw data": self._rawData,
                     "SIF" : self._sifFormat,
                     "Calibrated SIF" : self._calibratedSifFormat,
                     "GRAMS .spc" : self._spcFormat,
                     "TIFF" : self._tiffFormat,
                     "NASA's FITS" : self._fitsFormat,
                     "EDF" : self._edfFormat,
                     "BMP" : self._bmpFormat
                    }
        
        comboDict[fileFormat]()

    def _directSave(self):
        data = pd.DataFrame({"Wavelengths": self.calibrationValues, "X": self.arr}) 
        data.to_csv(self.pathAndName+".csv.gz", index=False, sep=",", compression='gzip')
        
    def _rawData(self):
        # Typ : 1 - Signed 16; 2 - Signed 32; 3 - Float
        self.pathAndName = "_".join(self.pathAndName.split(" "))
        ret = self.sdk.SaveAsRaw(szFileTitle=self.pathAndName+".csv", typ=3)
        print(f"[acquisitionThread/rawData] Saving filepath {self.pathAndName+'.csv'} as raw data returned {ret}")

    def _sifFormat(self):
        #self.pathAndName = "_".join(self.pathAndName.split(" "))
        #self.pathAndName = "_".join(self.pathAndName.split(".")[0:2])+".sif"
        #self.pathAndName = "-".join(self.pathAndName.split(":"))
        #self.pathAndName = "C:" + self.pathAndName[2:]
        #self.pathAndName = "C:/Users/adato/Programs/RACS/testSpectrum.sif"
        ret = self.sdk.SaveAsSif(path=self.pathAndName+".sif")
        print(f"[acquisitionThread/sifFormat] Saving filepath {self.pathAndName+'.sif'} as .sif format returned {ret}")
        
    def _calibratedSifFormat(self):
        ret = self.sdk.SaveAsSif(path=self.pathAndName)
        print(f"[acquisitionThread/calibratedSifFormat] Calibrated sif not implemented yet!!! Saving file as .sif format returned {ret}")

    def _spcFormat(self):
        ret = self.sdk.SaveAsSPC(path=self.pathAndName+'.spc')
        print(f"[acquisitionThread/spcFormat] Saving filepath {self.pathAndName+'.spc'} as .spc format returned {ret}")

    def _tiffFormat(self):
        # For now I don't have a pallete file. Once I do, this can be activated
        #ret = self.sdk.SaveAsTiff(path=self.pathAndName, palette=,  position=1, typ=2)
        print(f"[acquisitionThread/tiffFormat] Saving filepath {self.pathAndName+'.tiff'} as .tiff format is not implemented.")
    
    def _fitsFormat(self):
        # Typ: 0 - Unsigned 16, 1 - Unsigned 32, 2 - Signed 16, 3 - Signed 32, 4 - Float
        ret = self.sdk.SaveAsFITS(szFileTitle=self.pathAndName+".fits", typ=4)
        print(f"[acquisitionThread/fitsFormat] Saving filepath {self.pathAndName+'.fits'} as .fits format returned {ret}.")

    def _edfFormat(self):
        # iMode : 0 - Save to 1 file, 1 - Save kinetic series to multiple files
        ret = self.sdk.SaveAsEDF(szPath=self.pathAndName+".edf", iMode=0)
        print(f"[acquisitionThread/edfFormat] Saving filepath {self.pathAndName+'.edf'} as .edf format returned {ret}.")

    def _bmpFormat(self):
        # Don't have pallet for bmp file. Not implementing
        #ret = self.sdk.SaveAsBmp(path=self.pathAndName, palette=, ymin, ymax)
        print(f"[acquisitionThread/bmpFormat] Saving file as .bmp format is not implemented.")

    """
    def priorCMD(self, msg, callerFunction=""):
        #print(msg)
        ret = self.SDKPrior.PriorScientificSDK_cmd(self.sessionID, create_string_buffer(msg.encode()), self.rx)
        if ret:
            print(f"[loadStageSidebar: cmd/{callerFunction}] Api error {ret}")
        else:
            print(f"[loadStageSidebar: cmd/{callerFunction}] OK {self.rx.value.decode()}")

        #input("Press ENTER to continue...")
        return ret, self.rx.value.decode()
    """

class main(QMainWindow):
    def __init__(self):
        super().__init__()
        loadUi("mainLayout.ui", self)

        
        #Initializing detector camera
        self.initializeDetector()
        
        #Initializing spectrograph (mirrors, gratings etc.)
        self.initializeSpectrograph()

        # Setting up a new MDI subwindow
        #self.mainCanvasMdi.count = self.plot.count + 1
        self.plotQ = Queue(maxsize = 1)

        sub = QMdiSubWindow()
        sub.setWidget(mainCanvas.mainPlotSubWindow(q = self.plotQ, type="smoothed"))
        sub.setWindowTitle(f"Main plot window: Smoothed data")
        self.mainCanvasMdi.addSubWindow(sub)
        sub.show()

        # Starting an acquisition thread.
        self.acquisitionQ = Queue(maxsize = 1)
        # TODO: acquisitionFinishedQ is very likely obsolete. Finished tasks can be checked by the acquisitionQ .join() method
        self.acquisitionFinishedQ = Queue(maxsize = 1)

        # Layout for the side pannel and connecting side pannel
        vbox = QVBoxLayout()
        self.leftSidePanel = leftSidePanel.loadSidePanel(sdk=self.sdk, 
                                                         spc=self.spc, 
                                                         acquisitionQ=self.acquisitionQ, 
                                                         acquisitionFinishedQ=self.acquisitionFinishedQ,
                                                         mainCanvasMdi=self.mainCanvasMdi,
                                                         plotQ = self.plotQ,
                                                         #plot=self.plot
                                                         )
        vbox.addWidget(self.leftSidePanel)
        vbox.setContentsMargins(0,0,0,0)
        ret = self.leftWidget.setLayout(vbox)

        # UI Elements
        self.startBtn = self.findChild(QPushButton, "startBtn")
        self.exposureValue = self.findChild(QDoubleSpinBox, "exposureValue")
        self.acquisitionMode = self.findChild(QComboBox, "acquisitionModeCBox")
        self.kineticsNumScans = self.findChild(QSpinBox, "kineticsNumScans")
        self.wavelengthSetValue = self.findChild(QLineEdit, "wavelengthSetValue")
        self.wavelengthMinimum = self.findChild(QLabel, "wavelengthMinimum")
        self.wavelengthMaximum = self.findChild(QLabel, "wavelengthMaximum")
        self.zeroOrderValue = self.findChild(QLabel, "zeroOrderValue")
        self.saveFolderLineEdit = self.findChild(QLineEdit, "saveFolderLineEdit")
        self.outputModeCBox = self.findChild(QComboBox, "outputModeCBox")
        self.fileFormatCBox = self.findChild(QComboBox, "fileFormatCBox")
        #bottomWidget.loadBottomWidgetFunctions(sdk=self.sdk, spc=self.spc, elements=self.elements)

        # Plugging power button
        self.powerBtn = self.findChild(QPushButton, "powerBtn")
        self.powerBtn.clicked.connect(self.shutDownFunction)

        # Setting up bottom widget functionality
        self.startBtn.clicked.connect(self.startAcquisition)
        self.exposureValue.valueChanged.connect(self.setExposureTime)

        self.readModeCBox = self.findChild(QComboBox, "readModeCBox")

        (ret, self.xpixels, self.ypixels) = self.sdk.GetDetector()
        print("[startAcquisition] Function GetDetector returned {} xpixels = {} ypixels = {}".format(
        ret, self.xpixels, self.ypixels))

        self.exposureTimingValue = self.findChild(QLabel, "exposureTimingValue")
        self.accumulateTimingValue = self.findChild(QLabel, "accumulateTimingValue")
        self.kineticTimingValue = self.findChild(QLabel, "kineticTimingValue")
        # Setting default exposure time (also updates timing values in the detector sidebar)
        self.setExposureTime()
        
        # Connecting a button to organize the subWindows in the MDI area as tiles.
        self.tileMdiAreaBtn.clicked.connect(self.mainCanvasMdi.tileSubWindows)

        self.acquisitionThread = acquisitionThread(parent=self, 
                                                   sdk=self.sdk, 
                                                   spc=self.spc, 
                                                   acquisitionQ=self.acquisitionQ, 
                                                   acquisitionFinishedQ = self.acquisitionFinishedQ,
                                                   plotQ=self.plotQ)
        self.acquisitionThread.start()

    def updateStatusBar(self, statusMessage, something):
        # Updates status bar at the bottom of the main window
        print("####################################")
        print("Status bar updated.")
        print("####################################")

        self.statusbar.showMessage(statusMessage)
        #self.statusbar.showMessage("This is a status bar!")

    def retrieveElement(self, elementName, elementClass):
        #print(f"[main/retrieveElement] Retrieving {elementName}.")
        return self.findChild(elementClass, elementName)

    def setExposureTime(self):
        desiredExposureTime = self.exposureValue.value()
        print(f"[setExposureTime] attempting to set exposure time to : {desiredExposureTime}")
        
        ret = self.sdk.SetExposureTime(desiredExposureTime)
        print(f"[setExposureTime] Function SetExposureTime returned {ret} time = {desiredExposureTime}s")
        
        (ret, fminExposure, fAccumulate, fKinetic) = self.sdk.GetAcquisitionTimings()
        print(f"[setExposureTime] Function GetAcquisitionTimings returned {ret} exposure = {fminExposure} accumulate = {fAccumulate} kinetic = {fKinetic}")

        try:
            self.exposureTimingValue.setText(f"{fminExposure} s")
        except:
            print()
        try:
            self.accumulateTimingValue.setText(f"{fAccumulate} s")
        except:
            print()
        try:
            self.kineticTimingValue.setText(f"{fKinetic} s")
        except:
            print()

    def startAcquisition(self):

        # This might not be necessary to do again. 
        self.setExposureTime()
        """
        # TODO : Change to be shared.
        readMode = self.readModeCBox.currentText()
        messageDict = {}
        messageDict["Read mode"] = readMode
        messageDict["Xpixels"] = self.xpixels
        messageDict["Ypixels"] = self.ypixels
        #messageDict["Plot"] = self.plot
        messageDict["Acquisition mode"] = self.acquisitionMode.currentText()

        if messageDict["Acquisition mode"] == "Kinetic series":
            messageDict["Kinetic series length"] = self.kineticsNumScans.value()
        print(f"[startAcquisition] Message : {messageDict}")
        print(f"[startAcquisition] Current queue size: {self.q.qsize()}")
        print(f"[startAcquisition] Current queue: {self.q}")
        """
        #messageDict = {"Wavelength" : 575,
        #               #"Filename" : "./Spectra/Spectrum 1"
        #               }
        messageDict = {}
        try: 
            self.acquisitionQ.put_nowait(messageDict)
        except:
            print(f"[startAcquisition] Queue is full.")
            print(f"[startAcquisition] Queue content : {self.acquisitionQ.get()}")
              
        #self.startBtn.clicked.connect(self.killAcquisitionThread)
        #self.startBtn.setText("Cancel acquisition")
    
    def killAcquisitionThread(self):
        # Terminating acquisition thread
        #self.acquisitionThread.terminate()
        #self.acquisitionThread.exit()

        # Cancelling WaitForAcquisition() function/thread.
        ret = self.sdk.CancelWait()
        print(f"[killAcquisitionThread] Function CancelWait returned {ret}.")
        ret = self.sdk.AbortAcquisition()
        print(f"[killAcquisitionThread] Function AbortAcquisition returned {ret}.")
        self.acquisitionThread.quit()
        print(f"[killAcquisitionThread] returned : {self.acquisitionThread.isFinished()}, TOP")
        # Waiting for 2 seconds maximum, checking every 0.1 sec
        for i in range(0, 20):    
            self.acquisitionThread.wait(100)
            if self.acquisitionThread.isFinished():
                break

            i = i + 1 
        if not self.acquisitionThread.isFinished():
            #self.acquisitionThread.quit()
            self.acquisitionThread.exit()

        print(f"[killAcquisitionThread] returned : {self.acquisitionThread.isFinished()}, BOTTOM")

    def updateProgressBar(self, currentValue):
        self.acquisitionProgressBar.setValue(currentValue)
        
    #def gotoScreen(self, layoutNum):
    #    self.leftBarStacked.setCurrentIndex(layoutNum)
    def initializeSpectrograph(self):
        """
        Initializing spectrgraph
        """
        print("[initializeSpectrograph] Initialising Spectrograph.")
        self.spc = ATSpectrograph() #Load the ATSpectrograph library
        self.shm = self.spc.Initialize("")

        print(f"[initializeSpectrograph] shm : {self.shm}")

        if ATSpectrograph.ATSPECTROGRAPH_SUCCESS==self.shm:

            print("[initializeSpectrograph] Detector initialized successfully.")

            (ret, devices) = self.spc.GetNumberDevices()
            print("[initializeSpectrograph] Function GetNumberDevices returned {}".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
            print("[initializeSpectrograph] \tNumber of devices: {}".format(devices))

            for index in range(devices):
                (ret, serial) = self.spc.GetSerialNumber(index, 64)
                print("[initializeSpectrograph] Function GetSerialNumber returned {}".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
                print("[initializeSpectrograph] \tSerial No: {}".format(serial))
                
                (ret, FocalLength, AngularDeviation, FocalTilt) = self.spc.EepromGetOpticalParams(index)
                print("[initializeSpectrograph] Function EepromGetOpticalParams {}".format(self.spc.GetFunctionReturnDescription(ret, 64)[1]))
                print("[initializeSpectrograph] \tFocal Length: {}".format(FocalLength))         
                print("[initializeSpectrograph] \tAngular Deviation: {}".format(AngularDeviation))
                print("[initializeSpectrograph] \tFocal Tilt: {}".format(FocalTilt))
        else:
            print("[initializeSpectrograph] Could not initialise Spectrograph")

        # Getting number of pixels on x axis from camera and setting that in the spectrograph
        ret, xpixels, ypixels = self.sdk.GetDetector()
        print(f"[main/initializeSpectrograph] GetDetector returned: {ret}, x pixels: {xpixels}, y pixels: {ypixels}")
        ret = self.spc.SetNumberPixels(device=0, NumberPixels=xpixels)
        print(f"[main/initializeSpectrograph] SetNumberPixels returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")
        ret, number = self.spc.GetNumberPixels(0)
        print(f"[main/initializeSpectrograph] GetNumberPixels returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}, pixels: {number}")

        # Getting pixel width (and height) from the camera and setting the pixel width in the spectrograph
        ret, pixelWidth, pixelHeight = self.sdk.GetPixelSize()
        print(f"[main/initializeSpectrograph] GetPixelSize returned {ret} pixel height: {pixelWidth}, pixel width: {pixelHeight}")
        ret = self.spc.SetPixelWidth(device=0, Width=pixelWidth)
        print(f"[main/initializeSpectrograph] SetPixelWidth returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}")

        # Checking X calibration values 
        ret, val1, val2, val3, val4 = self.spc.GetPixelCalibrationCoefficients(device=0)
        print(f"[main/initializeSpectrograph] GetPixelCalibrationCoefficients returned {self.spc.GetFunctionReturnDescription(ret, 64)[1]}, calibration coefficients are: {val1}, {val2}, {val3} and {val4}.")

        ret, calibration = self.spc.GetCalibration(device=0, NumberPixels=1024)
        print(f"[main/initializeSpectrograph] GetCalibration returned: {self.spc.GetFunctionReturnDescription(ret, 64)[1]}, calibration: {calibration[0:9]}")

    def initializeDetector(self):
        """
        Initializing camera
        """
        #self.initializeStatusLabel.setText("Initializing camera.")

        self.sdk = atmcd()  # Load the atmcd library
        print(f"[initialize_detector] sdk : {self.sdk}")
        self.codes = atmcd_codes

        ret = self.sdk.Initialize("")  # Initialize camera
        print("[initialize_detector] Function Initialize returned {}".format(ret))

        if atmcd_errors.Error_Codes.DRV_SUCCESS == ret:
            # Changing initialize status label to inform GUI user.
            #self.initializeStatusLabel.setText("Camera initilized.")
            print("[initializeDetector] Detector initialized successfully.")

            (ret, iSerialNumber) = self.sdk.GetCameraSerialNumber()
            print("[initializeDetector] GetCameraSerialNumber returned {} Serial No: {}".format(
            ret, iSerialNumber))
    
    def shutDownFunction(self):
        # Clean up
        tempRet = self.leftSidePanel.acquisitionSidebar.temperatureThread.exit()
        print("[main/shutDownFunction] Temperature thread shutdown returned {}".format(tempRet))
        shutterRet = self.leftSidePanel.shutterSidebar.exit()
        print("[main/shutDownFunction] Shutter shutdown returned {}".format(shutterRet))
        time.sleep(0.5)
        coolerRet = self.sdk.CoolerOFF()
        print("[shutDownFunction] Function Cooler OFF {}".format(coolerRet))
        stageRet = self.leftSidePanel.stageSidebar.controllerDisconnect()
        print(f"[shutDownFunction] Stage controller disconnect returned : {stageRet}")
        sdkRet = self.sdk.ShutDown()
        print("[shutDownFunction] Function Shutdown returned {}".format(sdkRet))
        spcRet = self.spc.Close()
        print("[shutDownFunction] Function Close returned {}".format(self.spc.GetFunctionReturnDescription(spcRet, 64)[1]))

        exit()

if __name__ == "__main__":

    #def Run():
        
    #    app = QApplication(sys.argv)
        #app.setAttribute(AA_Use96Dpi) #Fixes axis shrinking issue when using different monitores or laptop/external monitor combos. Still deforms the graph, but axis follows graph now.
        #_translate = QCoreApplication.translate
    #    cProfile.run('main()','PROFILE.txt')
    #    window = main()
    #    window.show()
    #    sys.exit(app.exec())
    

    #Run()

    app = QApplication([])
    window = main()
    window.show()
    sys.exit(app.exec())
