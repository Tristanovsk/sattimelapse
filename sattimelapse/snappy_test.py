

import numpy as np
from esasnappy import ProductIO
from sattimelapse import utils

file = '/DATA/Satellite/SENTINEL2/test/dimitri/L1C/S2A_MSIL1C_20170903T090551_N0205_R050_T35TLE_20170903T090723.SAFE/'

product = ProductIO.readProduct(file)
product = utils.utils().get_resampled(product, resolution=60, method='Nearest')

# Empty list to receive rows of data
im_bands = list(product.getBandNames())

# Get height and width
h = product.getSceneRasterHeight()
w = product.getSceneRasterWidth()

arr = np.zeros((w,h),dtype=np.float32)  # Empty array

# Get the 1st band of the product for example
currentband = product.getBand( im_bands[0])
lst_arr = []
array = np.zeros([w,h,1],dtype=np.float32)

# Loop over height
for i, band in enumerate(product.getBands()):
    for y in range(h):
        print(y)
        # Create a 1 line array to read in the data

        # Append as list to be more efficient (could be opti mised?)
        band.readPixels(0, y, w, 1, array[y,:])

# Convert to np.array
lst_arr = np.asarray( lst_arr)

