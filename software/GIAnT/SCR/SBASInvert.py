#!/usr/bin/env python
'''Simple example of a SBAS like inversion. Reads the igram 
stack from a HDF5 file. The results are again written to a 
HDF5 file.
 
 .. note::
 
     This script estimates time-series only for those pixels
    that are coherent in all interferograms. We suggest using
    a low cthresh value (0.2-0.25) to ensure a reasonable number
     of pixels are selected.'''

import numpy as np
import tsinsar as ts
import sys
import matplotlib.pyplot as plt
import scipy.linalg as lm
import h5py
import datetime as dt
import argparse
import os

############Command Line Parser.
def parse():
    parser = argparse.ArgumentParser(description='Simple SBAS inversion script.')
    parser.add_argument('-i', action='store', default=None, dest='fname', help='To override input HDF5 file. Default: Uses default from ProcessStack.py', type=str)
    parser.add_argument('-o', action='store', default='LS-PARAMS.h5', dest='oname', help='To override output HDF5 file. Default: LS-PARAMS.h5', type=str)
    parser.add_argument('-d', action='store', default='data.xml', dest='dxml', help='To override the data XML file. Default: data.xml', type=str)
    parser.add_argument('-p', action='store', default='sbas.xml', dest='pxml', help='To override the processing XML file. Default: sbas.xml', type=str)
    inps = parser.parse_args()
    return inps



###########Class for dealing with simple SBAS inversions.
class SBAS:
    '''Class that deals with all computations related to SBAS.'''
    def __init__(self,G,H,tims,masterind,demerr=False,filt=None):
        '''Initiates the SBAS class object.
        
        .. Args:
            
            * G       System matrix
            * H       Reconstruction operator
            * tims    SAR time acquisitions
        
        .. Kwargs:
            
            * demerr   If DEM error is estimated
            * filt     Filter duration in years'''

        npar = G.shape[1]
        if demerr:
            self.nm = npar-1
        else:
            self.nm = npar

        self.G = G.copy()

        if filt is None:
            self.H = H.copy()
            self.F = self.H
        else:
            dt = np.abs(tims[:,None] - tims[None,:])
            dt = np.exp(-0.5*dt*dt/(filt*filt))
            norm = np.sum(dt,axis=1)
            dt = dt/norm[:,None]
            self.H = H.copy()
            self.F = np.dot(dt,H)

        self.masterind = masterind

    def invert(self,data):
        '''numpy lstsq is sufficient. Gain from using other routines seems to be negligible.'''
        [phat,res,n,s] = np.linalg.lstsq(self.G,data,rcond=1.0e-8)
        dhat = np.dot(self.F, phat[0:self.nm,:])
        dhat = dhat - dhat[self.masterind,:]
        rhat = np.dot(self.H, phat[0:self.nm,:])
        rhat = rhat - rhat[self.masterind,:]
        return phat, dhat, rhat
        
#################End of the SBAS class

if __name__ == '__main__':
    ############Start of the main program
    ############Read parameter file.
    inps = parse()
    logger = ts.logger
    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)

    #######Dirs
    h5dir = (dpars.data.dirs.h5dir)
    figdir = (dpars.data.dirs.figsdir)

    ########Some parameters
    netramp = (ppars.params.proc.netramp)
    gpsramp = (ppars.params.proc.gpsramp)
    filt   = (ppars.params.proc.filterlen)

    if inps.fname is None:
        if netramp or gpsramp:
            fname = os.path.join(h5dir,'PROC-STACK.h5')
        else:
            fname = os.path.join(h5dir,'RAW-STACK.h5')
    else:
        fname = os.path.join(h5dir,inps.fname)

    #######Preparing input objects
    sdat = h5py.File(fname,'r')
    Jmat = sdat['Jmat'].value
    bperp = sdat['bperp'].value
    if netramp or gpsramp:
        igram = sdat['figram']
    else:
        igram = sdat['igram']

    tims = sdat['tims'].value
    dates = sdat['dates']
    cmask = sdat['cmask'].value

    Nifg = Jmat.shape[0]
    Nsar = Jmat.shape[1]
    Nx = igram.shape[2]
    Ny = igram.shape[1]

    #######List of dates.
    daylist = ts.datestr(dates)

    ########Master time and index information
    masterdate = (ppars.params.proc.masterdate)
    if masterdate is None:
        masterind = 0
    else:
        masterind = daylist.index(masterdate)

    tmaster = tims[masterind]


    ##########Report some stats
    logger.info('Number of interferograms = ' + str(Jmat.shape[0]))
    logger.info('Number of unique SAR scenes = ' + str(Jmat.shape[1]))
    nIslands = np.min(Jmat.shape) - np.linalg.matrix_rank(Jmat)
    logger.info('Number of connected components in network: ' + str(nIslands))

    if nIslands > 1:
        logger.warn('The network appears to be contain disconnected components\n' +
                'SBAS uses SVD to resolve the offset between components.')

    #####Setting up the SBAS dictionary
    rep = [['SBAS',masterind]]   #Differential displacements (add time-normalization???)

    H,mName,regF = ts.Timefn(rep,tims) #Greens function matrix

    ####Removing master scene at master time
    ind = np.arange(Nsar)
    ind = np.delete(ind,masterind)

    H = H[:,ind]
    nm = H.shape[1]

    ######## For debugging
#    G1 = np.dot(Jmat, H)
#    for kk in xrange(Jmat.shape[0]):
#        master = np.nonzero(Jmat[kk,:] == 1)
#        slave = np.nonzero(Jmat[kk,:] == -1)
#        nzs = np.nonzero(G1[kk,:] != 0)
#        print master, slave, nzs

    demerr = (ppars.params.proc.demerr)


    oname = os.path.join(h5dir,inps.oname)
    if os.path.exists(oname):
        os.remove(oname)
        logger.info('Deleting previous %s'%oname)

    logger.info('Output h5file: %s'%oname)

    odat = h5py.File(oname,'w')
    odat.attrs['help'] = 'Regular SBAS Inversion results. Raw + filtered series.'

    if demerr:
        G = np.column_stack((np.dot(Jmat,H),bperp/1000.0)) #Adding Bperp as the last column
        parms = odat.create_dataset('parms',(Ny,Nx,nm+1),'f')
        parms.attrs['help'] = 'Stores all the relevant parameters from the SBAS inversion.'

        mName = np.append(mName,'demerr')
    else:
        G = np.dot(Jmat,H)
        parms = odat.create_dataset('parms',(Ny,Nx,nm),'f')
        parms.attrs['help'] = 'Stores all the relevant parameters from the SBAS inversion.'


    ########Creating the SBAS operator
    mysbas = SBAS(G, H, tims, masterind, demerr=demerr, filt = filt) 

    recons = odat.create_dataset('recons',(Nsar,Ny,Nx))
    recons.attrs['help'] = 'Reconstructed time-series'

    rawts = odat.create_dataset('rawts',(Nsar,Ny,Nx))
    rawts.attrs['help'] = 'Raw unfiltered time-series'


    progb = ts.ProgressBar(minValue=0,maxValue=Ny)

    #####Only to get pixels that do not have NaN data values.
    #####Even without nmask, we would end up with NaN values
    #####for these pixels.
#    nmask = np.sum(igram,axis=0)
#    nmask = np.isfinite(nmask)
#    cmask = cmask*nmask


    ####Actual SBAS processing
    progb = ts.ProgressBar(minValue=0,maxValue=Ny)
    for p in xrange(Ny):
        dph = igram[:,p,:]
        phat,dhat,rhat = mysbas.invert(dph)
        parms[p,:,:] = phat.T
        recons[:,p,:] = dhat
        rawts[:,p,:] = rhat
        progb.update(p,every=5)

    progb.close()

    ######Other useful information in HDF5 file.
    g = odat.create_dataset('mName',data=mName)
    g.attrs['help'] = 'Unique names for model parameters.'

    g = odat.create_dataset('regF',data=regF)
    g.attrs['help'] = 'regF family indicator for model parameters.'

    g = odat.create_dataset('tims',data=tims)
    g.attrs['help'] = 'SAR acquisition time in years.'

    g = odat.create_dataset('dates',data=dates)
    g.attrs['help'] = 'Ordinal values of SAR acquisition dates.'

    g = odat.create_dataset('cmask',data=cmask,dtype='float32')
    g.attrs['help'] = 'Common pixel mask.'

    g = odat.create_dataset('masterind',data=masterind)
    g.attrs['help'] = 'Master scene index.'
    odat.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
