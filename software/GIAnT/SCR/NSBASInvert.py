#!/usr/bin/env python
'''NSBAS inversion with quadratic constraints. Performs the same set up
as regular SBAS but includes quadratic constraints to join islands of
disconnected interferograms.

.. author:

    Romain Jolivet <rjolivet@caltech.edu>, Piyush Agram <piyush@gps.caltech.edu>

.. References:

    * Doin, M. P., S. Guillaso, R. Jolivet, C. Lasserre, F. Lodge,
    G. Ducret, and R. Gradin (2011), Presentation of the small baseline
    NSBAS processing chain on a case example: The Etna deformation
    monitoring from 2003 to 2010 using Envisat data, paper presented 
    at FRINGE 2011 conference (ESA), Frascati, Italy.
    * Lopez-Quiroz, P. et al., (2009), Time series analysis of Mexico 
    City subsidence constrained by radar interferometry, Journal of 
    Applied Geophysics, pp.1-15
    * Jolivet, R. et al., (2012), Shallow creep on the Haiyuan Fault 
    (Gansu, China) revealed by SAR Interferometry. Journal of Geophysical 
    Research, 117(B6)
    
.. note::

    The script estimates time-series only for those pixels that have atleast
    nvalid number of observations. Can use a moderately high cthresh (0.4-0.5)
    with this script. 
    '''

import numpy as np
import tsinsar as ts
import sys
import matplotlib.pyplot as plt
import scipy.linalg as lm
import scipy.interpolate as interp
import h5py
import datetime as dt
import multiprocessing as mp
import argparse
import os

############Parser.
def parse():
    parser = argparse.ArgumentParser(description='Simple NSBAS inversion script.')
    parser.add_argument('-i', action='store', default=None, dest='fname', help='To override input HDF5 file. Default: Uses default from ProcessStack.py', type=str)
    parser.add_argument('-o', action='store', default='NSBAS-PARAMS.h5', dest='oname', help='To override output HDF5 file. Default: NSBAS-PARAMS.h5', type=str)
    parser.add_argument('-d', action='store', default='data.xml', dest='dxml', help='To override the data XML file. Default: data.xml', type=str)
    parser.add_argument('-p', action='store', default='sbas.xml', dest='pxml', help='To override the processing XML file. Default: sbas.xml', type=str)
    parser.add_argument('-nproc', action='store', default=1, dest='nproc', help='Number of threads. Default: 1', type=int)
    parser.add_argument('-u', action='store', default='userfn.py', dest='user', help='To override the default script with user-defined python functions. Default: userfn.py', type=str)
    parser.add_argument('-gamma', action='store', default = 1.0e-4, dest='gamma', help='Weight of the polynomial constraints. Default: 1.0e-4', type=float)
    inps = parser.parse_args()
    return inps


#######Can add anything to this class
class dummy:
    pass

#######Class for NSBAS inversions.
class NSBAS_invert(mp.Process):
    '''Class dealing with all computations related to SBAS.'''
    def __init__(self, par):
        '''Initiates the class object. Par contains the following fields.

        .. Args:

            * Dmat           SBAS design matrix 
            * Ref            Reference index of the master scene
            * minNum         Minimum number of valid interferograms
            * Z              Polynomial Parameter matrix 
            * LT             SBAS reconstruction matrix
            * Cons           Polynomial constraint matrix
            * gamma          Weight of constraints
            * data           InSAR observations
            * pixinds        Indices of pixels for a thread
            * ifgcnt         Number of interferograms
            * parms          Estimated paramters
            * raw            Raw inverted time-series
            * filt           Filtered time-series
            * Nsar           Number of SAR scenes'''
           
        self.par = par
        mp.Process.__init__(self)

    def run(self):
        npix = len(self.par.pixinds)
        Ref = self.par.Ref
        Nsar = self.par.Nsar
        par = self.par      ###Not copying. Faster access.

        for q in xrange(npix):
            ii = par.pixinds[q]
            dph = par.data[:,q]
            inds = np.flatnonzero(np.isfinite(dph) & (dph!=0))
            
            if len(inds) >= minNum:

                # Select Interferos and Sar Scenes
                Dt = par.Dmat[inds,:]
                indz = np.flatnonzero(np.abs(Dt).sum(axis=0))

                undeux = np.clip(np.arange(Ref-1,Ref+1),0,Nsar-1)

                #Only if it contains the reference acquisition
                if len(np.intersect1d(undeux,indz)):
                    
                    [sel] = np.where(indz>=Ref)
                    seli = indz.copy()
                    seli[sel] += 1
                    seli = np.insert(seli,sel[0],Ref)

                    # Build the new Design Matrix
                    Dt2 = Dt[:,indz]
                    Znew = par.Z[inds,:]
                    Dnew = np.column_stack((Dt2,Znew))

                    # Select Constraints to apply
                    Consnew = par.Cons[seli,:]
                    LTt = par.LT[:,indz]
                    LTnew = LTt[seli,:]
                    Cons2 = np.column_stack((LTnew,Consnew))

                    # Build G and d
                    G = np.row_stack((Dnew,gamma*Cons2))
                    nr = LTnew.shape[0]
                    d = np.hstack( ( dph[inds],np.zeros((nr)) ) )

                    # PseudoInverse to invert G
                    [phat,err,rnk,s] = np.linalg.lstsq(G,d,rcond=1.0e-10)

                    # Write results
                    par.ifgcnt[ii] = len(inds)
                    par.parms[ii,:] = phat[-(npd):]
                    mod = np.dot(LTnew,phat[:-npd])
                    g = np.ones(Nsar)*np.nan
                    g[seli] = mod
                    wts = gauss[seli,:][:,seli]
                    h = np.ones(Nsar)*np.nan
                    h[seli]=np.dot(wts,mod)/np.sum(wts,axis=1)
                    
                    par.raw[:,ii] = g
                    par.filt[:,ii] = h





if __name__ == '__main__':
    #--------------------------------------------------------------
    #Parse command line
    inps = parse()
    logger = ts.logger

    #--------------------------------------------------------------
    # Read parameter file.
    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)


    #-------------------------------------------------------------
    h5dir = (dpars.data.dirs.h5dir)
    figdir = (dpars.data.dirs.figsdir)


    #--------------------------------------------------------------
    # Weight for the constraints lines.
    gamma = inps.gamma

    # Reference
    masterdate = (ppars.params.proc.masterdate)

    ####Time filtering
    tau = (ppars.params.proc.filterlen) # yrs, temporal gaussian smoothing

    # Minimum number of ifg to do the process
    minNum = (ppars.params.proc.nvalid)

    #--------------------------------------------------------------

    netramp = (ppars.params.proc.netramp)
    gpsramp = (ppars.params.proc.gpsramp)


    if inps.fname is None:
        if netramp:
            fname = os.path.join(h5dir,'PROC-STACK.h5')
        else:
            fname = os.path.join(h5dir,'RAW-STACK.h5')
    else:
        fname = os.path.join(h5dir,inps.fname)


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

    if minNum > Nifg:
        logger.info('Number of minimum scenes is larger than number of interferograms.')
        
    ######Get reference index.
    daylist = ts.datestr(dates)

    ########Master time and index information
    if masterdate is None:
        Ref=0
    else:
        Ref = daylist.index(masterdate)

    tmaster = tims[Ref]

    #--------------------------------------------------------------
    # Build the Increments as a function of the Reference

    rep = [['SBAS',Ref]]
    LT,mName,regF = ts.Timefn(rep,tims) #Greens function matrix
    LT = np.delete(LT,Ref,axis=1)
    Dmat = np.dot(Jmat,LT)

    #--------------------------------------------------------------
    # build the Constraint Part of the matrix

    # Constraint
    import imp
    try:
            user=imp.load_source('NSBASdict',inps.user)
            rep = user.NSBASdict()
    except:
            logger.info('No modification in the NSBAS constraint functional from')
            logger.info('Assuming a quadratic polynomial form')
            rep = [['POLY',[2],[tims[Ref]]]]

    Cons,mName,regF = ts.Timefn(rep,tims)
    Cons = -1*Cons
    npc = Cons.shape[1]  # Number of parameters in the constraint function

    # If DEM Correction
    demerr = (ppars.params.proc.demerr)
    if demerr:
        # Re-estimate the Baselines in network sense to have absolute bperps
        Jinv = np.linalg.pinv(Jmat)
        mperp = np.dot(Jinv,bperp)
        refm = mperp[0]
        mperp = mperp - refm
        Cons = np.column_stack((Cons,-1*(mperp)/1000.0))
        mName = np.append(mName,'demerr')
        Z = np.zeros((Nifg,npc+1))
    else:
        Z = np.zeros((Nifg,npc))

    #--------------------------------------------------------------
    # Build the Gaussian Kernel for smoothing
    gauss = (tims[None,:] - tims[:,None])**2
    gauss = np.exp(-0.5*gauss/(tau*tau))

    #--------------------------------------------------------------
    # open output file
    outname = os.path.join(h5dir,inps.oname)

    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Deleting previous h5file %s'%outname)

    logger.info('Output h5file %s'%outname)
    odat = h5py.File(outname,'w')
    odat.attrs['help'] = 'Results from the NSBAS Inversion of the processed Stack'

    #--------------------------------------------------------------
    # Create output variables
    if demerr:
        npd = npc+1
    else:
        npd = npc

    parms = odat.create_dataset('parms',(Ny,Nx,npd),'f')
    parms.attrs['help'] = 'The polynomial function parameters used to tie isolated subnetworks'


    rawts = odat.create_dataset('rawts',(Nsar,Ny,Nx),'f')
    rawts.attrs['help'] = 'Raw time-series from the NSBAS algorithm'
    rawts[:,:,:] = np.NaN

    recons = odat.create_dataset('recons',(Nsar,Ny,Nx),'f')
    recons.attrs['help'] = 'Reconstructed filtered time-series'
    recons[:,:,:] = np.NaN

    ifgcnt = odat.create_dataset('ifgcnt',(Ny,Nx),'i')
    ifgcnt.attrs['help'] = 'Number of interferograms used for every pixel.'


    #######Setting up NSBAS parameter structure
    par = dummy()
    par.Dmat = Dmat 
    par.Z = Z
    par.LT = LT
    par.Cons = Cons
    par.gamma = gamma
    par.minNum = minNum
    par.Nsar = Nsar
    par.Ref = Ref

    ######Shared memory objects
    cntarr = mp.Array('d',Nx)
    par.ifgcnt = np.reshape(np.frombuffer(cntarr.get_obj()),Nx)

    parr = mp.Array('d',Nx*npd)
    par.parms = np.reshape(np.frombuffer(parr.get_obj()),(Nx,npd))

    rarr = mp.Array('d',Nx*Nsar)
    par.raw = np.reshape(np.frombuffer(rarr.get_obj()),(Nsar,Nx))

    farr = mp.Array('d',Nx*Nsar)
    par.filt = np.reshape(np.frombuffer(farr.get_obj()),(Nsar,Nx))


    #--------------------------------------------------------------
    # loop on lines

    nproc = min(inps.nproc,Nx)

    logger.info('Number of parallel processes: %d'%(nproc))
    logger.info('Relative weight of polynomial constraint : %e'%(gamma))

    pinds = np.int_(np.linspace(0,Nx,num=nproc+1))
    progb = ts.ProgressBar(maxValue=Ny)

    for p in xrange(Ny):        #For every line
        threads = []
        par.raw[:,:] = np.nan
        par.parms[:,:] = np.nan
        par.filt[:,:] = np.nan
        par.ifgcnt[:] = 0

        if nproc == 1:
            inds = np.arange(Nx)
            par.pixinds = inds
            par.data = igram[:,p,inds]
            nb = NSBAS_invert(par)
            nb.run()

        else:
            for q in xrange(nproc):
                inds = np.arange(pinds[q],pinds[q+1])
                par.pixinds = inds
                par.data   = igram[:,p,inds]
                threads.append(NSBAS_invert(par))
                threads[q].start()

            for thrd in threads:
                thrd.join()

        parms[p,:,:] = par.parms
        ifgcnt[p,:] = par.ifgcnt
        rawts[:,p,:] = par.raw
        recons[:,p,:] = par.filt
        progb.update(p, every=5)
        
    progb.close()


    ######Auxiliary information
    g = odat.create_dataset('masterind',data=Ref)
    g.attrs['help'] = 'Master scene index.'

    g = odat.create_dataset('mName',data=mName)
    g.attrs['help'] = 'Unique name for the model parameters'

    g = odat.create_dataset('bperp',data=bperp)
    g.attrs['help'] = 'Absolute perpendicular baseline'

    g = odat.create_dataset('regF',data=regF)
    g.attrs['help'] = 'Regularization flag of each model parameter'

    g = odat.create_dataset('tims',data=tims)
    g.attrs['help'] = 'SAR acquisition times in years.'

    g = odat.create_dataset('dates',data=dates)
    g.attrs['help'] = 'Ordinal values of the SAR acquisition dates'

    g = odat.create_dataset('cmask',data=cmask)
    g.attrs['help'] = 'Common pixel mask used for analysis'

    g = odat.create_dataset('gamma', data=gamma)
    g.attrs['help'] = 'Weight of the polynomial constraints'
    odat.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
