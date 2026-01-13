# Created by Diego Alonso Alvarez on the 12th July 2020
#
# Copyright (c) 2020 Imperial College London
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.

from ctypes import WinDLL, create_string_buffer
import os
import sys
import time

#path = "C:/Users/adato/OneDrive - Danmarks Tekniske Universitet/Dokumenter/Programs/qtspectra/AndorV2/PriorSDK/x64/PriorScientificSDK.dll"
path = "../../x64/PriorScientificSDK.dll"

if os.path.exists(path):
    SDKPrior = WinDLL(path)
else:
    raise RuntimeError("DLL could not be loaded.")

rx = create_string_buffer(1000)
realhw = True


def cmd(msg):
    print(msg)
    ret = SDKPrior.PriorScientificSDK_cmd(
        sessionID, create_string_buffer(msg.encode()), rx
    )
    if ret:
        print(f"Api error {ret}")
    else:
        if isinstance(rx, str):
            print(f"OK {rx}")
            return ret, rx
        else:
            print(f"OK {rx.value.decode()}")
            return ret, rx.value.decode()

    
    


ret = SDKPrior.PriorScientificSDK_Initialise()
if ret:
    print(f"Error initialising {ret}")
    sys.exit()
else:
    print(f"Ok initialising {ret}")


ret = SDKPrior.PriorScientificSDK_Version(rx)
print(f"dll version api ret={ret}, version={rx.value.decode()}")


sessionID = SDKPrior.PriorScientificSDK_OpenNewSession()
if sessionID < 0:
    print(f"Error getting sessionID {ret}")
else:
    print(f"SessionID = {sessionID}")


ret = SDKPrior.PriorScientificSDK_cmd(
    sessionID, create_string_buffer(b"dll.apitest 33 goodresponse"), rx
)
print(f"api response {ret}, rx = {rx.value.decode()}")
input("Press ENTER to continue...")


ret = SDKPrior.PriorScientificSDK_cmd(
    sessionID, create_string_buffer(b"dll.apitest -300 stillgoodresponse"), rx
)
print(f"api response {ret}, rx = {rx.value.decode()}")
input("Press ENTER to continue...")


if realhw:
    print("Connecting...")
    # substitute 3 with your com port Id
    cmd("controller.connect 3")
    input("Press ENTER to continue...")

    # test an illegal command
    cmd("controller.stage.position.getx")
    input("Press ENTER to continue...")

    # get current XY position in default units of microns
    cmd("controller.stage.position.get")
    input("Press ENTER to continue...")

    # re-define this current position as 1234,5678
    cmd("controller.stage.position.set 1234 5678")
    input("Press ENTER to continue...")

    # check it worked
    cmd("controller.stage.position.get")
    input("Press ENTER to continue...")

    # set it back to 0,0
    cmd("controller.stage.position.set 0 0")
    cmd("controller.stage.position.get")
    input("Press ENTER to continue...")

    # start a move to a new position, normally you would poll
    # 'controller.stage.busy.get' until response = 0
    cmd("controller.stage.goto-position 1234 5678")
    input("Press ENTER to continue...")

    ret, rx = cmd("controller.stage.busy.get")
    while rx != "0":
        time.sleep(0.1)
        ret, rx = cmd("controller.stage.busy.get")
        print(rx)

    input("Press ENTER to continue...")



    # example velocity move of 10u/s in both x and y
    cmd("controller.stage.move-at-velocity 10 10")
    input("Press ENTER to continue...")


    # see busy status
    cmd("controller.stage.busy.get")
    input("Press ENTER to continue...")

    # stop velocity move
    cmd("controller.stage.move-at-velocity 0 0")
    input("Press ENTER to continue...")

    # see busy status */
    cmd("controller.stage.busy.get")
    input("Press ENTER to continue...")

    # see new position
    cmd("controller.stage.position.get")
    input("Press ENTER to continue...")

    # TTL output
    print("#### TTL output")
    cmd("controller.ttl.out.get")
    input("Press ENTER to continue...")

    cmd("controller.ttl.out.set 1")
    input("Press ENTER to continue...")

    cmd("controller.ttl.out.get")
    input("Press ENTER to continue...")

    cmd("controller.ttl.out.set 0")
    input("Press ENTER to continue...")

    cmd("controller.ttl.out.get")
    input("Press ENTER to continue...")

    # disconnect cleanly from controller
    cmd("controller.disconnect")
    input("Press ENTER to continue...")

else:
    input("Press ENTER to continue...")
