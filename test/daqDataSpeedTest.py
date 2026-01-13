import sys, time
import pandas as pd
import numpy as np
import pickle 
#from concurrent import futures
from nspyre import DataSink
from nspyre.misc.logging import nspyre_init_logger

import io

def parsingData(inputData, dfData, samplingFrequency, timeStampList, DeltaT):
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
        if timestamp not in timeStampList:
            nloops=nloops+1
            
            t1 = time.perf_counter_ns()
            # Data is coming in with typically only 1 new timestamp.
            # Timestamps that have already been processed in previous 
            # iterations are ignored.
            # New time stamp is appended to the list of processed timestamps
            timeStampList.append(timestamp)
            if len(timeStampList) > 1000:
                # To keep the list lookup reasonably fast, we remove old values
                timeStampList.pop(0)
            t2 = time.perf_counter_ns()
            # Transformig values into a data frame
            values = list(entry.values())[0]
            dfSubsetData = pd.DataFrame(values)
            # Generating timestamp values for each entry
            t3 = time.perf_counter_ns()
 
            end = timestamp
            dataLen = dfSubsetData.shape[1]
            start = end - pd.Timedelta(dataLen*1/samplingFrequency, unit="seconds")

            timeIndex = pd.date_range(start=start, end=end, periods=dataLen)
            t4 = time.perf_counter_ns()
            
            dfSubsetData.columns = pd.DatetimeIndex(timeIndex)
            dfSubsetData = dfSubsetData.transpose()
            dfData = pd.concat([dfData, dfSubsetData])
            
            #################################################################################################
            # T6
            ############################
            t5 = time.perf_counter_ns()
            # Concatenating the data chunk to the main data frame.
            dfData.sort_index(inplace=True, ascending=False)
            t6 = time.perf_counter_ns()
            #################################################################################################
            
            # The upper bound of the data frame size (e.g. latest value + 1 second)
            lowerBound = dfData.index[0] - DeltaT
            # Truncate will remove all values that are over the upperBound value
            dfData = dfData.truncate(before=lowerBound)
            t7 = time.perf_counter_ns()

            # For debugging purposes
            #print(f"T1: {(t1 - t0)/1e6} ms, T2: {(t2 - t1)/1e6} ms, T3: {(t3-t3)/1e6} ms, T4: {(t4-t3)/1e6} ms, T5: {(t5-t4)/1e6} ms, T6: {(t6-t5)/1e6} ms, T7: {(t7-t6)/1e6} ms")

    return dfData

def main():
    opTime = []
    samplingFrequency = 10000
    timeStampList = []

    dfData = pd.DataFrame(np.zeros([1,3]))
    dfData.index = [pd.Timestamp.fromtimestamp(0)]
    # This is the size of the final data frame.
    DeltaT = pd.Timedelta(1, "seconds")

    lineBreak = "\n".encode()
    delta = pd.Timedelta(value=300, unit="microseconds")
    output_file = io.FileIO("daq_output"+str(time.time())+".csv", 'a')

    with DataSink("daq") as ds:
        #with open("testCsvOutput.tsv", "a") as output_file:
        #with bz2.open("testCsvOutput.tsv.bz2", "ab") as output_file:
        #with zipfile.ZipFile("testCsvOutput.tsv.zip", mode='', compression=zipfile.ZIP_DEFLATED) as output_file:
        output_buffer = io.BufferedWriter(output_file,buffer_size=10000000,)
        while True:
            try:
                ds.pop(timeout=None)
                t0 = time.perf_counter_ns()
                dfData = parsingData(ds.data, dfData=dfData, samplingFrequency=samplingFrequency, timeStampList=timeStampList, DeltaT=DeltaT)
                t1 = time.perf_counter_ns()
                #dfData.to_csv("testCsvOutput.tsv", mode="a", sep="\t")
                #dfData = dfData.resample(delta).mean()
                output = []
                index = list((dfData.index - pd.Timestamp("1970-01-01")) // pd.Timedelta('1ns'))
                index = [str(x) for x in index]
                index = " ".join(index)
                output.append(index)
                for column in dfData:
                    col = [str(np.float16(x)) for x in dfData[column]]
                    col = " ".join(col)
                    output.append(col)

                    #output_file.write(str(list(dfData[column])))
                #output_file.write(str(output) + "\n")
                #output_file.write("\n")
                output = "|".join(output)
                output = str(output).encode() + lineBreak
                t2 = time.perf_counter_ns()
                output_buffer.write(output)
                output_buffer.flush()
                #output_file.write(lineBreak)
                t3 = time.perf_counter_ns()

                operationTime = (t2 - t1)/1e6
                opTime.append(operationTime)
                print(f"Parsing: {(t1-t0)/1e6} ms, Encoding: {(t2 - t1)/1e6} ms, Writing: {(t3-t2)/1e6} ms")

            except KeyboardInterrupt:
                print("Routine was interrupted.")
                print(dfData)
                output_file.close()
                df1 = pd.DataFrame({"Operation time [ms]": opTime})
                df1.to_csv("Operation time.csv")
                sys.exit()

if __name__ == '__main__':
    main()