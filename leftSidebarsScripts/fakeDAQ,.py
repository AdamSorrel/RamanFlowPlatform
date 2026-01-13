import redis, time, json, pickle
from matplotlib import pyplot as plt
import pandas as pd
import numpy as np

# Define the Lorentzian function
def lorentzian(x, x0, gamma, A):
    return A / (1 + ((x - x0) / gamma) ** 2)

# Parameters
A = 10        # Height of the peak
FWHM = 5     # Full width at half maximum
gamma = FWHM / 2  # Width parameter
x0 = 0        # Center of the peak
x_values = np.linspace(-10, 10, 20)  # X range

# Fake peak shape
peakVals = lorentzian(x_values, x0, gamma, A)

r = redis.Redis(host="127.0.0.1",
                port=6379,
                decode_responses=True)

# Testing connection
if not r.ping():
    raise RuntimeError

channel2delay = 1.5   # 1 second delay
peakList = []

try: 
    while True:

        timestamp = time.time()
        # Generating  random data
        data=np.random.rand(100,3)

        # Generating timestamps
        timeIndex = np.array([timestamp-i*0.001 for i in range(100,0,-1)]).reshape(100,1)

        if np.random.rand() > 0.75:
            data[40:60,0] = peakVals
            # Peak time
            peakList.append(timeIndex[40]) 

        if len(peakList) > 0:
            if (peakList[0] + channel2delay) < timestamp:
                data[40:60,1] = peakVals

                del peakList[0]

        # Generating timestamps
        timeIndex = np.array([timestamp-i*0.001 for i in range(100,0,-1)]).reshape(100,1)
        data = np.concatenate((timeIndex, data), axis=1)
        data = data.tolist()

        r.set(f"data_{timestamp}", json.dumps(data))
        r.expire(f"data_{timestamp}", 1)
        time.sleep(0.1)

except KeyboardInterrupt:
    print("Closing program")
    r.close()