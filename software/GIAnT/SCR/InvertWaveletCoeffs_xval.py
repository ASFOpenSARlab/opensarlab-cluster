''' !!!!!NOT READY FOR REGULARIZED INVERSIONS YET. !!!!!
MInTS inversion using a dictionary  of temporal functions.
Reads the wavelet coeffificnet stack from a HDF5 file and
inverts it using the time  representation string given by
  the user. The results are again written to a HDF5 file.

.. Usage:

    python InvertCoeffsPar.py -h 
		gives you some help
    
.. note::
 
    This script automatically builds the regularization 
    operator based on the number of families of splines 
    used. Deterministic temporal functions like linear, 
    seasonal etc are not regularized.'''

import numpy as np
import tsinsar as ts
import solver.tikh as tikh
import sys
import matplotlib.pyplot as plt
import scipy.linalg as lm
import h5py
import datetime as dt
import logging
import scipy.signal as ss
import json
import multiprocessing as mp
import time
import argparse
import os
import imp

##########Class for dealing with subsets
class WSBAS:
    '''Class that deals with all the computations related to SBAS.'''
    def __init__(self, J, H,tims, masterind, demerr=False):
        '''Initiates the SBAS class object.

        .. Args:

            * J        System connectivity matrix
            * H        Reconstruction operator
            * tims     SAR acquisition times
            * masterind Master scene index

        .. Kwargs:

            * demerr   If DEM error is estimated'''

        self.masterind = masterind
        nifg, nsar = J.shape
        self.Hs = H.copy()
        self.nsar = nsar
        self.nm = H.shape[1]
        self.inds = []

        for sind in xrange(nsar):
            inds = np.delete(np.arange(nifg),np.flatnonzero(J[:,sind]))
            self.inds.append(inds)
           
        self.nset = nsar

    def invert(self,G,data):
        parms = np.zeros((self.nset,self.nm))
        for k in xrange(self.nset):
            [phat,res,n,s] = np.linalg.lstsq(G[self.inds[k],:],data[self.inds[k]],rcond=1.0e-8)
#            dhat = np.dot(self.Hs,phat[0:self.nm,:])
#            dhat = dhat - dhat[self.masterind,:]
            parms[k,:] = phat[0:self.nm]

        return parms


#######Command line parser
def parse():
    parser = argparse.ArgumentParser(description='Performs MInTS inversion if wavelet coefficients.')
    parser.add_argument('-i',action='store', default='WAVELET.h5', dest='iname', help='Input HDF5 file with the wavelet coefficients and weights. Default: WAVELET.h5', type=str)
    parser.add_argument('-o',action='store', default='WAVELET-INV-xval.h5', dest='oname', help='Output HDF5 file with estimated model parameters. Default: WAVELET-INV-xval.h5', type=str)
    parser.add_argument('-nproc', action='store', default=1, dest='nproc', help='Number of parallel threads. Default: 1', type=int)
    parser.add_argument('-d',action='store', default='data.xml', dest='dxml', help='To override the default data xml file. Default: data.xml', type=str)
    parser.add_argument('-p',action='store', default='mints.xml', dest='pxml', help='To override the default mints xml file. Default: mints.xml', type=str)
    parser.add_argument('-u', action='store', default='userfn.py', dest='user', help='To override the default python script with user defined functions. Default: userfn.py', type=str)
    inps = parser.parse_args()
    return inps


#########Can add anything to this class
class dummy:
    pass

#######Parallel inversions.
class thread_invert(mp.Process):
    '''Template from Bryan Riel.'''
    def __init__(self,par):
        self.G = par.G
        self.S = par.S
        self.C = par.C
        self.coeffs = par.coeffs
        self.istart = par.istart
        self.procN = par.procN
        self.coeff = par.coeff
        self.cwts = par.cwts
        self.istart = par.istart
        self.procN = par.procN
        self.alpha = par.alpha

        mp.Process.__init__(self)
        
    def run(self):
        mm = self.coeffs.shape[2]
        for ii in xrange(self.istart, self.istart+self.procN):
            for jj in xrange(mm):
                d = self.coeff[:,ii,jj]
                W = self.cwts[:,ii,jj]
                Zsq = ts.dmultl(W,self.C)
                G = np.dot(Zsq,self.G)
                dw = np.dot(Zsq,d)

                solve = tikh.TIKH(G,self.S)
                penalty = solve.gcv(dw,plot=False)
                res = solve.solve(penalty,dw)

                self.coeffs[:,ii,jj] = res
                self.alpha[ii,jj] = penalty

######Start of the main program
inps = parse()
logger = ts.logger

try:
    user = imp.load_source('timedict',inps.user)
except:
    logger.error('No user defined function in %s'%(inps.user))
    sys.exit(1)

############Read parameter file.
dpars = ts.TSXML(inps.dxml, File=True)
ppars = ts.TSXML(inps.pxml, File=True)

#####Read in directory names
h5dir = (dpars.data.dirs.h5dir)


inname = os.path.join(h5dir,inps.iname)
logger.info('Input h5file: %s'%inname)
wdat = h5py.File(inname,'r')
Jmat = wdat['Jmat'].value
bperp = wdat['bperp'].value
tims = wdat['tims'].value
dates = wdat['dates'].value
wvlt = wdat['wvlt']
wts = wdat['wts']
offset = wdat['offset'].value
cmask = wdat['cmask'].value
Nifg = Jmat.shape[0]
Nsar = Jmat.shape[1]
Nx = wvlt.shape[2]
Ny = wts.shape[1]

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

tmaster = tims[masterind]

#####To be modified by user as needed.
rep = user.timedict()
#rep = [['ISPLINES',[3],[48]]]

regu = (ppars.params.proc.regularize)

H,mName,regF = ts.Timefn(rep,tims) #Greens function matrix

######Looking up master index.
Jm = Jmat.copy()
Jmat[:,masterind] = 0.
nm = H.shape[1]

#######Setting up regularization
nReg = np.int(regF.max())

if (nReg==0) & (regu):
    logging.info('Nothing to Regularize')

L = []
if (nReg !=0) & (regu):
    logging.info('Setting up regularization vector')
    for k in xrange(nReg):
        [ind] = np.where(regF==(k+1))
        num = len(ind)
        Lf = ts.laplace1d(num)
        Lfull = np.zeros((num,nm))
        Lfull[:,ind] = Lf
        L.append(Lfull)

L = np.squeeze(np.array(L))

###########Adding DEM Error to inversion.
demerr = (ppars.params.proc.demerr)
if demerr:
    G = np.column_stack((np.dot(Jmat,H),bperp/1000.0)) #Adding Bperp as the last column
    mname = np.append(mname,'demerr')
    if (len(L) != 0):
        L = np.column_stack((L,np.zeros(L.shape[0])))
else:
    G = np.dot(Jmat,H)


##########Adding shape function to regularization
shape = (ppars.params.proc.shape)
if (shape != 0) & (len(L) != 0):
    R = ts.resolution_matrix(G, rank=shape)
    R = np.clip(np.diag(R),0.0,1.0)
    ind = np.flatnonzero(regF)
    wt = np.sqrt(np.abs(1-R[ind]))
    L = ts.dmultl(wt,L)


progb = ts.ProgressBar(minValue=0,maxValue=Ny)


########Setting up covariance
Cihalf = ts.matrix_root(np.dot(Jm,Jm.T),inv=True)
CihG = np.dot(Cihalf,G)


########Output file
model = json.dumps(rep)

outname = os.path.join(h5dir,inps.oname)
if os.path.exists(outname):
    os.remove(outname)
    logger.info('Deleting previous h5file: %s'%outname)

logger.info('Output h5file : %s'%outname)
odat = h5py.File(outname,'w')
odat.attrs['help'] = 'Inverted wavelet coefficients using given time representation.'

iwvlt = odat.create_dataset('wvlt',(Nsar,nm,Ny,Nx),'f')
iwvlt.attrs['help'] = 'Model parameters in wavelet coefficient domain.'

g = odat.create_dataset('model',data=model)
g.attrs['help'] = 'String representation of the temporal model used in the inversion.'

#########Check number of scales to analyze.
wvltfn = (ppars.params.proc.wavelet)
if wvltfn in ('meyer','MEYER'):
    minlevel = 3
else:
    minlevel = wdat['minlevel'].value
    


minscale = (ppars.params.proc.minscale)
maxscale = (ppars.params.proc.maxscale)


Nanalysis = Nscale - minscale


if len(L)==0:   #####Case with nothing to regularize

    oper = WSBAS(Jm, H, tims, masterind ,demerr=demerr)

    for scl in xrange(minlevel+max(maxscale-1,0),Nanalysis):
        if scl == minlevel:
            minq = 1
        else:
            minq = 2
        
        for quad in xrange(minq,5):
            ii,jj = ts.meyer.get_corners((Ny,Nx),scl,quad)
            
            data = wvlt[:,ii[0]:ii[1],jj[0]:jj[1]]
            wgt  = wts[:,ii[0]:ii[1],jj[0]:jj[1]]
            
            nn = ii[1]-ii[0]
            mm = jj[1]-jj[0]
            
            logger.info('Inverting: Scale - %2d , Quad - %1d'%(scl,quad))
            progb = ts.ProgressBar(maxValue=nn)
           
            parms = np.zeros((Nsar,nm,nn,mm))
            for n in xrange(nn):
                for m in xrange(mm):
                    W = wgt[:,n,m]
                    d = data[:,n,m]
                    Gw = ts.dmultl(W,CihG)
                    dw = ts.dmultl(W,np.dot(Cihalf,d))
#                    [mhat,rs,rnk,s] = np.linalg.lstsq(Gw,dw)
#                    parms[:,n,m] = mhat[0:nm]
                    vals = oper.invert(Gw,dw)
                    parms[:,:,n,m] = vals
                
                progb.update(n,every=5)
                
            progb.close()
                
            iwvlt[:,:,ii[0]:ii[1],jj[0]:jj[1]] = parms
                    
else:    #####Use regularized inversions
   
    regualpha = odat.create_dataset('alpha',(Ny,Nx),'f')
    regualpha.attrs['help'] = 'The smoothing parameters estimated using gcv'

    ########Window for smoothing coefficients.
    smooth = (ppars.params.proc.smooth)
    skip0 = (ppars.params.proc.smoothskip)
    Ncons = L.shape[0]

    ######Setting up object for parallel processing.    
    pars = dummy()
    pars.G = G
    pars.S = L
    pars.C = Cihalf

    for scl in xrange(minlevel+max(maxscale-1,0),Nanalysis):
        if scl==minlevel:
            minq = 1
        else:
            minq = 2

        ii,jj = ts.meyer.get_corners((Ny,Nx),scl,2)
        nn = ii[1]-ii[0]
        mm = jj[1]-jj[0]

        ######Create shared memory objects for output
        carr = mp.Array('d',nn*mm*nm)
        pars.coeffs = np.reshape(np.frombuffer(carr.get_obj()), (nm,nn,mm))

        sarr = mp.Array('d',nn*mm)
        pars.alpha = np.reshape(np.frombuffer(sarr.get_obj()),(nn,mm))
        
        #####Create shared memory objects for input
        coarr = mp.Array('d',nn*mm*Nifg)
        pars.coeff = np.reshape(np.frombuffer(coarr.get_obj()), (Nifg,nn,mm))

        soarr = mp.Array('d',nn*mm*Nifg)
        pars.cwts = np.reshape(np.frombuffer(soarr.get_obj()), (Nifg,nn,mm))

        for quad in xrange(minq,5):
            ss = time.time()
            ii,jj = ts.meyer.get_corners((Ny,Nx),scl,quad)
            pars.coeff[:,:,:] = wvlt[:,ii[0]:ii[1],jj[0]:jj[1]]
            pars.cwts[:,:,:]  = wts[:,ii[0]:ii[1],jj[0]:jj[1]]
            
            n_proc = min(inps.nproc,nn)
            
            nlines = np.linspace(0,nn,num=(n_proc+1)).astype(np.int)
            
            
            logger.info('Estimating: Scale - %2d , Quad - %1d'%(scl,quad))
            progb = ts.ProgressBar(maxValue=nn)
           
            threads = []
            for pid in xrange(n_proc):
                pars.istart = nlines[pid]
                pars.procN = nlines[pid+1] - nlines[pid]
                
                threads.append(thread_invert(pars))
                threads[pid].start()
            
            for thrd in threads:
                thrd.join()
            
    
            iwvlt[:,ii[0]:ii[1],jj[0]:jj[1]] = pars.coeffs
            regualpha[ii[0]:ii[1],jj[0]:jj[1]] = pars.alpha

            ee = time.time()
            logger.info('Time: %f Seconds'%(ee-ss))

wdat.close()

g = odat.create_dataset('Jmat', data=Jmat)
g.attrs['help'] = 'Connectivity matrix [-1,1,0]'

g = odat.create_dataset('bperp', data=bperp)
g.attrs['help'] = 'Perpendicular baseline values'

g = odat.create_dataset('tims', data=tims)
g.attrs['help'] = 'SAR acquisition time in years.'

g = odat.create_dataset('dates', data=dates)
g.attrs['help'] = 'Ordinal values of SAR acquisition dates.'

g = odat.create_dataset('offset', data=offset)
g.attrs['help'] = 'Crop information to retrieve original data.'

g = odat.create_dataset('cmask', data=cmask)
g.attrs['help'] = 'Common pixel mask'

odat.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
