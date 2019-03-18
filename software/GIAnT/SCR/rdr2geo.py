import numpy as np
import matplotlib.pyplot as plt
import h5py
import geocode as gc

latfile='lat.flt' 			# Latitude file (Binary flat, floating point, single precision)
lonfile='lon.flt'			# Longitude file (Binary flat, floating point, single precision)
wd = 350				# Width (pixels)
ln = 500				# Length (pixels)
h5file = 'WS-PARAMS.h5'			# hdf5 input file

# Reading the Lat and Lon files
lats = np.fromfile(latfile,dtype=np.float32).reshape((ln,wd))
lons = np.fromfile(lonfile,dtype=np.float32).reshape((ln,wd))

# Defining a square geocoded grid
box=[lons.min()-0.05, lons.max()+0.05, lats.min()-0.05, lats.max()+0.05]

# Creating the geocoder object 'samp'
samp = gc.geocode(lats=lats, lons=lons, box=box, spacing=0.00833333333)

# Open the hdf5 file
fin = h5py.File(h5file,'r')

# Read the dataset inside the hdf5 file
data = fin['recons']

# Do whatever you want to that dataset (here, we go from mm to cm)
img = data[-1,:,:]/10.0

# If samp is swath, you can write our non-NaN values as a point VRT file.
#samp.gdal_points(img,base='slice')

# Writes to the grd file called slice.grd
samp.rdr2gmt(img, 'slice.grd',radius=400, name='Deformation', title='Last slice', units='cm')

# Writes the geocoded output to an array 'gimg' and writes gimg to a file called 'slice.flt'
gimg = samp.rdr2geo_nearest(img, radius=50, epsilon=0)
fout = open('slice.flt','wb')
gimg = gimg.astype(np.float32)
gimg.tofile(fout)
fout.close()

# Plot things (uncomment if you want that)
#plt.figure()
#plt.imshow(gimg, extent=[samp.lons[0],samp.lons[-1],samp.lats[0],samp.lats[-1]], origin='lower')
#plt.colorbar()
#plt.show()


############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
