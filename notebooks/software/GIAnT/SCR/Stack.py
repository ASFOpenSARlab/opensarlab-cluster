'''Simple example of a Stacking process. Reads the igram stack 
from a HDF5 file and inverts for a constant velocity. The results 
are again written to a HDF5 file.'''

import numpy as np
import tsinsar as ts
import sys
import matplotlib.pyplot as plt
import scipy.linalg as lm
import h5py
import datetime as dt
import logging
import argparse
import multiprocessing as mp
import os
import imp

############Parser.
def parse():
    parser = argparse.ArgumentParser(description='SBAS like inversion using time functions.')
    parser.add_argument('-i', action='store', default=None, dest='fname', help='To override input HDF5 file. Default: Use default from ProcessStack.py', type=str)
    parser.add_argument('-o', action='store', default='STACK-PARAMS.h5', dest='oname', help='To override output HDF5 file. Default: STACK-PARAMS.h5', type=str)
    parser.add_argument('-d', action='store', default='data.xml', dest='dxml', help='To override the data XML file. Default: data.xml', type=str)
    parser.add_argument('-p', action='store', default='sbas.xml', dest='pxml', help='To override the processing XML file. Default: sbas.xml', type=str)
    inps = parser.parse_args()
    return inps


if __name__ == '__main__':
    ############Read parameter file.
    inps=parse()
    logger = ts.logger

    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)


    ######Dirs
    h5dir = (dpars.data.dirs.h5dir)
    figdir = (dpars.data.dirs.figsdir)

    netramp = (ppars.params.proc.netramp)
    gpsramp = (ppars.params.proc.gpsramp)

    nvalid = (ppars.params.proc.nvalid)

    if inps.fname is None:
        if netramp:
            fname = os.path.join(h5dir,'PROC-STACK.h5')
        else:
            fname = os.path.join(h5dir,'RAW-STACK.h5')
    else:
        fname = os.path.join(h5dir,inps.fname)

    logger.info('Input h5file: %s'%fname)
    sdat = h5py.File(fname,'r')
    Jmat = sdat['Jmat'].value
    bperp = sdat['bperp'].value
    if netramp or gpsramp:
        igram = sdat['figram']
    else:
        igram = sdat['igram']

    tims = sdat['tims'].value
    dates = sdat['dates']
    cmask = sdat['cmask']

    Nifg = Jmat.shape[0]
    Nsar = Jmat.shape[1]
    Nx = igram.shape[2]
    Ny = igram.shape[1]

    #######List of dates.
    daylist = ts.datestr(dates)

    ########Master time and index information
    masterdate = (ppars.params.proc.masterdate)
    if masterdate is None:
        masterind= 0
    else:
        masterind = daylist.index(masterdate)

    tmaster = tims[masterind]

    #######Functional form for the stack
    rep = [['Linear',[0]]]
    H,mName,regF = ts.Timefn(rep,tims) #Greens function matrix

    outname = os.path.join(h5dir,inps.oname)
    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Deleting previous h5file %s'%outname)

    logger.info('Output h5file: %s'%outname)
    odat = h5py.File(outname,'w')
    odat.attrs['help'] = 'Results from Stacking Process'

    G = np.dot(Jmat,H)
    parms = odat.create_dataset('parms',(Ny,Nx),'f')
    parms.attrs['help'] = 'Estimated velocity'

    #########Insert master scene back for reconstruction.
    cumtime = odat.create_dataset('cumtime',(Ny,Nx),'f')
    cumtime.attrs['help'] = 'Cumulative time'

    ######  Computing the Stack
    logger.info('Computing the stack if more than %d int valid'%nvalid)

    progb = ts.ProgressBar(maxValue=Ny)
    for k in xrange(Ny):
        data = igram[:,k,:]
        XX = np.isfinite(data)
        Num = XX.sum(axis=0)
        All = np.multiply(G,data)
        Up = np.nansum(All,axis=0)

        Do = np.ones(data.shape)*np.nan
        Do[XX]=1.0
        Do = np.multiply(G**2,Do)
        Do = np.nansum(Do,axis=0)
        flags = np.ones(Nx)*np.nan
        flags[Num>=nvalid] = 1.0
        parms[k,:] = Up/Do
       
        flags = flags*np.abs(G)
        cumtime[k,:] = Num
        progb.update(k,every=5)

    progb.close()

    logger.info('Stack is done')

    #####Additional datasets

    g = odat.create_dataset('mName',data=mName)
    g.attrs['help'] = 'Unique names for model parameters.'

    g = odat.create_dataset('tims',data=tims)
    g.attrs['help'] = 'SAR acquisition times in years.'

    g = odat.create_dataset('dates',data=dates)
    g.attrs['help'] = 'Ordinal values for SAR acquisition dates.'

    g = odat.create_dataset('cmask',data=cmask)
    g.attrs['help'] = 'Common pixel mask.'

    g = odat.create_dataset('masterind',data=masterind)
    g.attrs['help'] = 'Index of the master SAR acquisition.'

    odat.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
