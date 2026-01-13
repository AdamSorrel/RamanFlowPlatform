import os, time
from datetime import datetime
import win32event  # pip install pyWin32
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors

sdk = atmcd()  # Load the atmcd library
codes = atmcd_codes

(ret) = sdk.Initialize("")  # Initialize camera
print("Function Initialize returned {}".format(ret))

if atmcd_errors.Error_Codes.DRV_SUCCESS == ret:

    (ret, iSerialNumber) = sdk.GetCameraSerialNumber()
    print("Function GetCameraSerialNumber returned {} Serial No: {}".format(
        ret, iSerialNumber))

    # Configure the acquisition

    # Letting the system cool completely
    ret = sdk.CoolerON()
    print("Function CoolerON returned {}".format(ret))

    # Configure the acquisition
    targetTemperature=0
    ret = sdk.SetTemperature(targetTemperature)
    print(f"Function SetTemperature returned {ret} target temperature {targetTemperature}")

    while ret != atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
        time.sleep(5)
        (ret, temperature) = sdk.GetTemperature()
        print("Function GetTemperature returned {} current temperature = {} ".format(
            ret, temperature), end='\r')
    # Catches above the print statement and preserves the below print statement
    print("")
    print("Temperature stabilized")

    #-------------------------------
    #   Setting acquisition params
    #-------------------------------

    ret = sdk.SetAcquisitionMode(codes.Acquisition_Mode.SINGLE_SCAN)
    print("Function SetAcquisitionMode returned {} mode = Single Scan".format(ret))

    ret = sdk.SetReadMode(codes.Read_Mode.FULL_VERTICAL_BINNING)
    print("Function SetReadMode returned {} mode".format(ret))

    ret = sdk.SetTriggerMode(codes.Trigger_Mode.EXTERNAL)
    print("Function SetTriggerMode returned {} mode = External".format(ret))

    # Setting trigger to raising edge (value 0)
    #ret = sdk.SetTriggerInvert(0)
    #print(f"Setting of the Function SetTriggerInvert to 0 (raising edge) returnd {ret}")

    (ret, xpixels, ypixels) = sdk.GetDetector()
    print("Function GetDetector returned {} xpixels = {} ypixels = {}".format(
        ret, xpixels, ypixels))


    #-------------------------------
    #   Exposure
    #-------------------------------

    exposureTime = 0.1 
    ret = sdk.SetExposureTime(exposureTime)
    print(f"Function SetExposureTime returned {ret} time = {exposureTime}s")
    if ret == atmcd_errors.Error_Codes.DRV_SUCCESS:
        print(f"Exposure time successfully set to {exposureTime}.")
    elif ret == atmcd_errors.Error_Codes.DRV_NOT_INITIALIZED:
        print("Error: Exposure time not set. Driver not initialized.")
    elif ret == atmcd_errors.Error_Codes.DRV_ACQUIRING:
        print(f"Warning: Exposure not set. Acquisition in progress.")
    elif ret == atmcd_errors.Error_Codes.DRV_P1INVALID:
        print(f"Error: Exposure time not set. Exposure Time invalid.")

    #-------------------------------
    #   Acquisition timings
    #-------------------------------

    (ret, fminExposure, fAccumulate, fKinetic) = sdk.GetAcquisitionTimings()
    print("Function GetAcquisitionTimings returned {} exposure = {} accumulate = {} kinetic = {}".format(
        ret, fminExposure, fAccumulate, fKinetic))

    #-------------------------------
    #   Enable keep clean cycle
    #-------------------------------

    # Enabling keep clean cycles
    # Note: Currently only available on Newton and iKon cameras operating in FVB external trigger mode.
    ret = sdk.EnableKeepCleans(mode=1)
    if ret == atmcd_errors.Error_Codes.DRV_SUCCESS:
        print("Keep clean mode enabled.")
    elif ret == atmcd_errors.Error_Codes.DRV_NOT_INITIALIZED:
        print("Error: Keep clean not enabled. Driver not initialized.")
    elif ret == atmcd_errors.Error_Codes.DRV_NOT_AVAILABLE:
        print("Error: Keep clean not initialized. Function not available.")
    else:
        print(f"Error: Keep clean return value error : {ret} ")

    ret = sdk.PrepareAcquisition()
    print("Function PrepareAcquisition returned {}".format(ret))

    #-------------------------------
    #   Set data ready event
    #-------------------------------
    event = win32event.CreateEvent(None, 0, 0, None)
    ret = sdk.SetDriverEvent(event.handle)
    print("Function SetDriverEvent returned {}".format(ret))
    
    
    n = 0
    while n < 1000:
        n = n + 1
        print("###########################################")
        print(f"Acquisition number {n}")
        
        # Perform Acquisition
        ret = sdk.StartAcquisition()
        print("Function StartAcquisition returned {}".format(ret))

        print("Enter WaitForSingleObject")
        ret = win32event.WaitForSingleObject(event, win32event.INFINITE)
        print("Function WaitForSingleObject returned {}".format(ret))

        imageSize = xpixels
        (ret, arr, validfirst, validlast) = sdk.GetImages16(1, 1, imageSize)
        print("Function GetImages16 returned {} first pixel = {} size = {}".format(
            ret, arr[0], imageSize))
        
        directory = "C:\\Users\\adato\\Programs\\Test\\testTiggerData\\30.10.2024\\5Hz\\" #+ "\\" # Replace with desired directory
        print(f"Saving into directory: {directory}")

        #filename = f"{directory}{time.strftime('TestSpectrum_%Y-%m-%d-%H-%M-%S')}.sif"
        filename = f"{directory}{datetime.now().strftime('TestSpectrum-%Y-%m-%d_%H-%M-%S-%f')}.sif"
        ret = sdk.SaveAsSif(filename)
        print("Function SaveAsSif returned {}".format(ret))

    # Clean up
    (ret) = sdk.ShutDown()
    print("Function Shutdown returned {}".format(ret))

else:
    print("Cannot continue, could not initialise camera")
