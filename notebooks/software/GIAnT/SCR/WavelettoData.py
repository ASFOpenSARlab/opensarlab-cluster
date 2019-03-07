#!/usr/bin/env python
'''Computes the inverse wavelet transform for the estimated 
model parameters and reconstructs the time-series by putting
them together. '''

import numpy as np
import tsinsar as ts
import sys
import matplotlib.pyplot as plt
import scipy.linalg as lm
import h5py
import datetime as dt
import logging
import scipy.signal as ss
import json
import argparse
import os
import multiprocessing as mp

def parse():
    parser = argparse.ArgumentParser(description='Transforms data back into data \
            domain and constructs the time-series estimate.')
    parser.add_argument('-d', action='store', default='data.xml', dest='dxml',
            help='Data XML file. Default: data.xml')
    parser.add_argument('-p', action='store', default='mints.xml', dest='pxml',
            help='MInTS XML file. Default: mints.xml')
    parser.add_argument('-i', action='store', default='WAVELET-INV.h5',
            dest='iname', help='Inverted wavelet coefficients. \
                    Default: WAVELET-INV.h5')
    parser.add_argument('-o', action='store', default='WS-PARAMS.h5',
            dest='oname', help='Final time-series HDF5 file.  \
                    Default: WS-PARAMS.h5') 
    parser.add_argument('-nchunk', action='store', default=40, dest='nchunk', help='Chunk of slices that will be loaded into memory at any given time. Default: 40',type=int)
    parser.add_argument('-nproc', action='store', default=1, dest ='nproc', help='Number of threads. Default: 1',type=int)

    inps = parser.parse_args()
    return inps


class dummy:
    pass

class thread_invert(mp.Process):
    '''Template from Bryan Riel'''
    def __init__(self,par):
        self.wvlt = par.wvlt
        self.minscale = par.minscale
        self.maxscale = par.maxscale
        self.slice = par.slice
        self.igram = par.igram
        self.Ny = par.igram.shape[1]
        self.Nx = par.igram.shape[2]
        self.Nscale = np.int(np.log2(self.Nx))
        self.minlevel = par.minlevel

        mp.Process.__init__(self)

    def run(self):
        for ind in self.slice:
            coeff = self.igram[ind,:,:]

            for scl in xrange(self.minscale):
                for quad in xrange(2,5):
                    ii,jj = ts.meyer.get_corners((self.Ny,self.Nx),self.Nscale-scl,quad)
                    coeff[ii[0]:ii[1],jj[0]:jj[1]] = 0.0

            if (self.maxscale-1) >= 0:
                ii,jj = ts.meyer.get_corners((self.Ny,self.Nx),self.minlevel+self.maxscale-1,1)
                coeff[ii[0]:ii[1],jj[0]:jj[1]] = 0.0
    
            if wvltfn in ('meyer','MEYER'):
                iwt = ts.meyer.iwt2_meyer(coeff,3,3)
            else:
                iwt = ts.wvlt.iwt2(iwt,wvlt=wvltfn)

            self.igram[ind,:,:] = iwt



if __name__ == '__main__':
    ######Start of main program
    inps = parse()
    logger = ts.logger

    ############Read parameter file.
    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)



    Ry0 = (dpars.data.subimage.rymin)
    Ry1 = (dpars.data.subimage.rymax)
    Rx0 = (dpars.data.subimage.rxmin)
    Rx1 = (dpars.data.subimage.rxmax)

    h5dir = (dpars.data.dirs.h5dir)

    inname = os.path.join(h5dir,inps.iname)
    logger.info('Input h5file: %s'%inname) 

    wdat = h5py.File(inname,'r')
    Jmat = wdat['Jmat'].value
    tims = wdat['tims'].value
    dates = wdat['dates'].value
    wvlt = wdat['wvlt']
    model = wdat['model'].value
    crop = wdat['offset'].value

    Nifg = Jmat.shape[0]
    Nsar = Jmat.shape[1]
    Nx = wvlt.shape[2]
    Ny = wvlt.shape[1]
    if crop.max() == 0:
        nn = (dpars.data.subimage.length)
        mm = (dpars.data.subimage.width)
        y0 = np.int((Ny-nn)/2)
        x0 = np.int((Nx-mm)/2)
        crop = np.array([y0,x0,nn,mm])

    ######Number of scales
    Nscale = np.int(np.log2(Nx))

    #######List of dates.
    daylist = ts.datestr(dates)

    ########Master time and index information
    masterdate = (ppars.params.proc.masterdate)
    if masterdate is None:
        masterind = 0
    else:
        masterind = daylist.index(masterdate)


    ######Evaluate the model from JSON form
    rep = json.loads(model)


    H,mName,regF = ts.Timefn(rep,tims) #Greens function matrix

    ######Looking up master index.
    nm = H.shape[1]

    outname = os.path.join(h5dir,inps.oname)
    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Deleting previous h5file: %s'%outname)

    logger.info('Output h5file: %s'%outname)
    odat = h5py.File(outname,'w')
    odat.attrs['help'] = 'Reconstructed time-series from inverted wavelet coefficients'

    imodel = odat.create_dataset('model',(nm,crop[2],crop[3]),'f')
    imodel.attrs['help'] = 'Estimated model parameters'


    its    = odat.create_dataset('recons',(H.shape[0],crop[2],crop[3]),'f')
    its.attrs['help'] = 'Reconstructed time-series.'

    #########Check number of scales to analyze.
    wvltfn = (ppars.params.proc.wavelet)
    if wvltfn in ('meyer','MEYER'):
        minlevel = 3
    else:
        minlevel = wdat['minlevel'].value
        
    minscale = (ppars.params.proc.minscale)
    maxscale = (ppars.params.proc.maxscale)

    pars = dummy()
    pars.minscale = minscale
    pars.maxscale = maxscale
    pars.wvlt = wvltfn
    pars.minlevel = minlevel

    #######Shared memory object
    Warr = mp.Array('f',inps.nchunk*Ny*Nx)
    commonarr = np.reshape(np.frombuffer(Warr.get_obj(),dtype=np.float32),(inps.nchunk,Ny,Nx))
    pars.igram = commonarr

    ngrps = np.arange(0,nm+1,inps.nchunk)
    if ngrps[-1] != nm:
        ngrps = np.append(ngrps,nm)

    nproc = inps.nproc
    progb = ts.ProgressBar(maxValue=nm)

    for grpnum in xrange(len(ngrps)-1):
        pars.start = ngrps[grpnum]
        ninds = ngrps[grpnum+1] - ngrps[grpnum]
        pars.igram[0:ninds,:,:] = wvlt[ngrps[grpnum]:ngrps[grpnum+1],:,:]

        nproc = min(ninds,nproc)
        nlines = np.linspace(0,ninds,num=nproc+1).astype(np.int)

        threads = []
        for k in xrange(nproc):
            pars.slice = np.arange(nlines[k],nlines[k+1])
            threads.append(thread_invert(pars))
            threads[k].start()

        for thrd in threads:
            thrd.join()

        for k in xrange(ninds):
            imodel[ngrps[grpnum]+k,:,:] = commonarr[k,crop[0]:crop[0]+crop[2],crop[1]:crop[1]+crop[3]]

        progb.update(ngrps[grpnum+1])

    progb.close()

    cmask = wdat['cmask'].value
    wdat.close()

    rstack = ts.STACK(its)
    progb = ts.ProgressBar(maxValue=crop[2])
    for k in xrange(crop[2]):
         coeff = imodel[:,k,:]
         iwt = np.dot(H,coeff)
         its[:,k,:] = iwt
         progb.update(k,every=5)

    rstack.setref([Ry0,Ry1,Rx0,Rx1])
    progb.close()
            
    g = odat.create_dataset('tims',data=tims)
    g.attrs['help'] = 'SAR acquisition times in years.'

    g = odat.create_dataset('Jmat',data=Jmat)
    g.attrs['help'] = 'Connectivity matrix [-1,0,1]'

    g = odat.create_dataset('modelstr', data=model)
    g.attrs['help'] = 'String representation of the temporal model.'

    g = odat.create_dataset('dates', data=dates)
    g.attrs['help'] = 'Ordinal values of the SAR acquisition dates.'

    g = odat.create_dataset('cmask', data=cmask)
    g.attrs['help'] = 'Common pixel mask'

    g = odat.create_dataset('masterind', data=masterind)
    g.attrs['help'] = 'Master scene index'
    odat.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
