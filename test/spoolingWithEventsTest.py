import os
import time
import win32event  # pip install pyWin32
from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
import threading

sdk = atmcd()  # Load the atmcd library
codes = atmcd_codes
ret = sdk.Initialize("")  # Initialize camera
print("Function Initialize returned {}".format(ret))


class driverEventThread(threading.Thread):
    def __init__(self, event, sdk):
        print("[driverEventThread] Enter WaitForSingleObject")
        print(f"[driverEventThread] eventList {event}")
        print(f"[driverEventThread] eventList type {type(event)}")
        
        while True:
            # Infinite wait
            #ret = win32event.WaitForSingleObject(event, win32event.INFINITE)
            ret = win32event.WaitForSingleObject(event, win32event.INFINITE)
            print("[driverEventThread] Function WaitForSingleObject returned {}".format(ret))
            ret, status = sdk.GetStatus()
            print("[driverEventThread] Status {}".format(status))
    
    def stop(self):
        self.exit()
        

class acquisitionEventThread(threading.Thread):
    def __init__(self, event, sdk):
        print("[acquisitionEventThread] Enter WaitForSingleObject")
        print(f"[acquisitionEventThread] eventList {event}")
        print(f"[acquisitionEventThread] eventList type {type(event)}")
    
        while True:
            # Infinite wait
            #ret = win32event.WaitForSingleObject(event, win32event.INFINITE)
            ret = win32event.WaitForSingleObject(event, win32event.INFINITE)
            print("[acquisitionEventThread] Function WaitForSingleObject returned {}".format(ret))
            ret, status = sdk.GetStatus()
            print("[acquisitionEventThread] Status {}".format(status))

    def stop(self):
        self.exit()
    
def statusThread(sdk):
    print("[acquisitionEventThread] Enter WaitForSingleObject")

    while True:
        ret, status = sdk.GetStatus()
        print("[statusThread] Status {}".format(status))
        time.sleep(0.3)


if atmcd_errors.Error_Codes.DRV_SUCCESS == ret:
    NUMKIN = 4
    ret = sdk.SetAcquisitionMode(codes.Acquisition_Mode.KINETICS)
    print("Function SetAcquisitionMode returned {} mode = Kinetics".format(ret))

    ret = sdk.SetKineticCycleTime(0.5)
    print("Function SetKineticCycleTime returned {} cycle time = 0.5 seconds".format(ret))

    ret = sdk.SetNumberKinetics(NUMKIN)
    print("Function SetNumberKinetics returned {}".format(ret))

    ret = sdk.SetTriggerMode(codes.Trigger_Mode.SOFTWARE_TRIGGER)
    print("Function SetTriggerMode returned {} mode = Software trigger".format(ret))

    ret = sdk.SetReadMode(codes.Read_Mode.IMAGE)
    print("Function SetReadMode returned {} mode = Image".format(ret))


    # Setting up an event thread

    driverEvent = win32event.CreateEvent(None, 0, 0, None)
    ret = sdk.SetDriverEvent(driverEvent.handle)
    print("Function SetDriverEvent returned {}".format(ret))

    acquisitionEvent = win32event.CreateEvent(None, 0, 0, None)
    ret = sdk.SetAcqStatusEvent(acquisitionEvent.handle)
    print("Function SetAcqStatusEvent returned {}".format(ret))

    driverThreadHandle = threading.Thread(target=driverEventThread, args=([driverEvent, sdk]))
    driverThreadHandle.start()

    acquisitionThreadHandle = threading.Thread(target=acquisitionEventThread, args=([acquisitionEvent, sdk]))
    acquisitionThreadHandle.start()

    #statusThreadHandle = threading.Thread(target=statusThread, args=([sdk]))
    #statusThreadHandle.start()

    #####################################################

    directory = os.getcwd()  # Replace with desired directory

    filename = "{}-{}".format(directory, time.strftime("%Y-%m-%d-%H-%M"))
    ret = sdk.SetSpool(1, codes.Spool_Mode.SPOOL_TO_16_BIT_FITS, filename, 10)
    print("Function SetSpool returned {} ".format(ret))

    (ret, xpixels, ypixels) = sdk.GetDetector()
    print("Function GetDetector returned {} xpixels = {} ypixels = {}".format(
        ret, xpixels, ypixels))

    ret = sdk.SetImage(1, 1, 1, xpixels, 1, ypixels)
    print("Function SetImage returned {} hbin = 1 vbin = 1 hstart = 1 hend = {} vstart = 1 vend = {}".format(
        ret, xpixels, ypixels))

    ret = sdk.SetExposureTime(0.5)
    print("Function SetExposureTime returned {} time = 0.5s".format(ret))

    ret = sdk.StartAcquisition()
    print("Function StartAcquisition returned {} ".format(ret))

    index = 0
    while index < NUMKIN:
        (ret, index) = sdk.GetTotalNumberImagesAcquired()
        print("Function current count {} ".format(index), end="\r")
    print("")
    
    # Clean up
    
    #driverThreadHandle.stop()
    #acquisitionThreadHandle.stop()
    ret = sdk.ShutDown()

    print("Function Shutdown returned {}".format(ret))

else:
    print("Cannot continue, could not initialise camera")
