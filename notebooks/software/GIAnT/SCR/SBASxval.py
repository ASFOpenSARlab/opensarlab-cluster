#!/usr/bin/env python
'''Simple script to estimate uncertainties using a leave one out cross validation approach on the estimated time-series products.

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
    parser.add_argument('-o', action='store', default='LS-xval.h5', dest='oname', help='To override output HDF5 file. Default: LS-xval.h5', type=str)
    parser.add_argument('-d', action='store', default='data.xml', dest='dxml', help='To override the data XML file. Default: data.xml', type=str)
    parser.add_argument('-p', action='store', default='sbas.xml', dest='pxml', help='To override the processing XML file. Default: sbas.xml', type=str)
    inps = parser.parse_args()
    return inps



###########Class for dealing with simple SBAS inversions.
class SBAS:
    '''Class that deals with all computations related to SBAS.'''
    def __init__(self,J,G,H,tims,masterind,demerr=False,filt=None):
        '''Initiates the SBAS class object.
        
        .. Args:
            
            * G       System matrix
            * H       Reconstruction operator
            * tims    SAR time acquisitions
        
        .. Kwargs:
            
            * demerr   If DEM error is estimated
            * filt     Filter duration in years'''
        
        npar = G.shape[1]

	if filt is not None:
	    dt = np.abs(tims[:,None] - tims[None,:])
	    wgt = np.exp(-0.5*dt*dt/(filt*filt))

        self.masterind = masterind

        ########Making subsets
        nifg, nsar = J.shape
        J = np.delete(J,masterind, axis=1)

        self.Gs = []           #####Greens functions
        self.Hs = []           #####Recons functions
        self.inds = []         #####Subset indices
        self.nm = []           #####Number of model params
        self.demerr = demerr
        self.nsar = nsar
    
        for sind in xrange(nsar-1):
            inds = np.delete(np.arange(nifg),np.flatnonzero(Jmat[:,sind]))
            self.inds.append(inds)

            Jt = np.abs(J[inds,:])
            indz = np.flatnonzero(Jt.sum(axis=0))

            sel = np.flatnonzero(indz>=masterind)
            seli = indz.copy()
            seli[sel] += 1
            seli = np.insert(seli,sel[0],masterind)

            self.nm.append(len(indz))

            #Build the recons matrix
            Hnew = H[:,indz].copy()      ###Maintain C-order

            if demerr:
                indz = np.append(indz,npar-1)

            # Build the new Design Matrix
            Gnew = G[:,indz]
            Gnew = Gnew[inds,:].copy()

            self.Gs.append(Gnew) 

            if filt is None:
                self.Hs.append(Hnew)
            else:
                Hnew = Hnew[seli,:]
                fnew = wgt[:,seli]
                norm = np.sum(fnew,axis=1)
                fnew = fnew/norm[:,None]
                self.Hs.append(np.dot(fnew,Hnew))

        self.nset = nsar-1

    def invert(self,data):
        '''numpy lstsq is sufficient. Gain from using other routines seems to be negligible.'''

        npix = data.shape[1]
        parms = np.zeros((self.nset, self.nsar, npix))
        for k in xrange(self.nset):
            [phat,res,n,s] = np.linalg.lstsq(self.Gs[k],data[self.inds[k]],rcond=1.0e-8)
            dhat = np.dot(self.Hs[k], phat[0:self.nm[k],:])
            dhat = dhat - dhat[self.masterind,:]
            parms[k,:,:] = dhat

        mask = np.flatnonzero(np.isfinite(np.sum(data,axis=0)))
        meanv = np.ones((self.nsar,npix))*np.nan
        stdv = np.ones((self.nsar,npix))*np.nan

        pdat = parms[:,:,mask]
        ######Estimating mean and variance of subsets.
        meanv[:,mask] = np.sum(pdat,axis=0)/(1.0*self.nset)
        stdv[:,mask]  = np.std(pdat,axis=0,ddof=1) 
        return meanv,stdv
        
#################End of the SBAS class

if __name__ == '__main__':
    ############Start of the main program
    ############Read parameter file.
    inps = parse()
    logger = ts.logger
    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)

    netramp = (ppars.params.proc.netramp)
    gpsramp = (ppars.params.proc.gpsramp)

    filt   = (ppars.params.proc.filterlen)

    #######Dirs 
    h5dir = (dpars.data.dirs.h5dir)


    if inps.fname is None:
        if netramp:
            fname = os.path.join(h5dir,'PROC-STACK.h5')
        else:
            fname = os.path.join(h5dir,'RAW-STACK.h5')
    else:
        fname = os.path.join(h5dir,inps.fname)

    #####Setting up input objects
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
        masterind = 0
    else:
        masterind = daylist.index(masterdate)

    tmaster = tims[masterind]

    #####To be modified by user as needed.
    rep = [['SBAS',masterind]]   #Differential displacements (add time-normalization???)

    H,mName,regF = ts.Timefn(rep,tims) #Greens function matrix

    #####Removing master scene from parameters to be estimated.
    H = np.delete(H,masterind,axis=1)

    demerr = (ppars.params.proc.demerr)

    outname = os.path.join(h5dir,inps.oname)

    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Removing previous h5file: %s', outname)

    logger.info('Output h5file: %s',outname)
    odat = h5py.File(outname,'w')

    if demerr:
        G = np.column_stack((np.dot(Jmat,H),bperp/1000.0)) #Adding Bperp as the last column
        mName = np.append(mName,'demerr')
    else:
        G = np.dot(Jmat,H)


    mysbas = SBAS(Jmat, G, H, tims, masterind, demerr=demerr, filt = filt) 

    recons = odat.create_dataset('recons',(Nsar,Ny,Nx))
    recons.attrs['help'] = 'Reconstructed time-series' 

    err = odat.create_dataset('error',(Nsar,Ny,Nx))
    err.attrs['help'] = 'Uncertainty in time-series'


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
        meanv,stdv = mysbas.invert(dph)
        recons[:,p,:] = meanv
        err[:,p,:] = stdv
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
