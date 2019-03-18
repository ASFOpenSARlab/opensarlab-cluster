#!/usr/bin/python

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure,figaspect
from matplotlib.widgets import Slider
import sys
import h5py
import datetime as dt
import tsinsar as ts
import argparse

#######Command line parsing.
def parse():
    parser = argparse.ArgumentParser(description='Interactive Stack time-series viewer')
    parser.add_argument('-e', action='store_true', default=False, dest='plot_err', help='Display error bars if available. Default: False')
    parser.add_argument('-f', action='store', default='Stack/STACK-PARAMS.h5', dest='fname', help='Filename to use. Default: Stack/STACK-PARAMS.h5', type=str)
    parser.add_argument('-m', action='store', default=0.1, dest='mult', help='Scaling factor. Default: 1 for mm/yr ', type=float)
    parser.add_argument('-y', nargs=2, action='store', default=[-25,25], dest='ylim', help='Y Limits for plotting. Default: [-25,25]',type=float)
    inps = parser.parse_args()
    return inps

#######Actual code.
inps = parse()

hfile = h5py.File(inps.fname,'r')
velo = hfile['parms']
ct = hfile['cumtime']

pv = plt.figure(1)

axv = pv.add_subplot(121)
cax=axv.imshow(velo,clim=inps.ylim)
axv.set_title('Velocity map from Stacking Process')
cbr=pv.colorbar(cax, orientation='horizontal',shrink=0.5)

axc = pv.add_subplot(122)
caxc = axc.imshow(ct)
axc.set_title('Cumulative Time, yrs')
cbr=pv.colorbar(caxc, orientation='horizontal',shrink=0.5)


def printcoords(event):
    global axv,axc
    if event.inaxes==axv or event.inaxes==axc:

	    ii = np.int(np.floor(event.ydata))
	    jj = np.int(np.floor(event.xdata))

	    print 'Average Velocity on pixel %d,%d : %f'%(ii,jj,velo[ii,jj])
	    print 'Cumulative Time  on pixel %d,%d : %f'%(ii,jj,ct[ii,jj])
    else:
	return


cid = pv.canvas.mpl_connect('button_press_event', printcoords)
plt.show()
pv.canvas.mpl_disconnect(cid)

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
