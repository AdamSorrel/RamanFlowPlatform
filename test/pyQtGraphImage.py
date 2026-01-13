import numpy as np
import pandas as pd

import pyqtgraph as pg
from pyqtgraph.Qt import QtWidgets


# Interpret image data as row-major instead of col-major
pg.setConfigOptions(imageAxisOrder='row-major')

app = pg.mkQApp("ImageView Example")

## Create window with ImageView widget
win = QtWidgets.QMainWindow()
win.resize(800,800)
imv = pg.ImageView(discreteTimeLine=True)
win.setCentralWidget(imv)
win.show()

## Create random 3D data set with time varying signals
dataRed = np.ones((100, 200, 200)) * np.linspace(90, 150, 100)[:, np.newaxis, np.newaxis]
dataRed += pg.gaussianFilter(np.random.normal(size=(200, 200)), (5, 5)) * 100
dataGrn = np.ones((100, 200, 200)) * np.linspace(90, 180, 100)[:, np.newaxis, np.newaxis]
dataGrn += pg.gaussianFilter(np.random.normal(size=(200, 200)), (5, 5)) * 100
dataBlu = np.ones((100, 200, 200)) * np.linspace(180, 90, 100)[:, np.newaxis, np.newaxis]
dataBlu += pg.gaussianFilter(np.random.normal(size=(200, 200)), (5, 5)) * 100

data = np.concatenate(
    (dataRed[:, :, :, np.newaxis], dataGrn[:, :, :, np.newaxis], dataBlu[:, :, :, np.newaxis]), axis=3
)

data = pd.read_csv("example.csv.gz", index_col=0)
data = data.transpose()
data = data.to_numpy()

# Display the data and assign each frame a time value from 1.0 to 3.0
imv.setImage(data, xvals=np.linspace(1., 3., data.shape[0]))
#imv.play(10)

## Set a custom color map
colors = [
    (0, 0, 0),
    (45, 5, 61),
    (84, 42, 55),
    (150, 87, 60),
    (208, 171, 141),
    (255, 255, 255)
]
#cmap = pg.ColorMap(pos=np.linspace(0.0, 1.0, 6), color=colors)
#imv.setColorMap(cmap)

# Start up with an ROI
#imv.ui.roiBtn.setChecked(True)
#imv.roiClicked()

if __name__ == '__main__':
    pg.exec()
