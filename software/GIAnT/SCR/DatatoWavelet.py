#!/usr/bin/env python
'''Forward Wavelet Transform the unwrapped data.Inpaints holes, mirrors to dyadic lengths and performs the  wavelet transform. The weights of each of the coefficients is also 
 calculated. The results are stored in a HDF5 file.'''
 
import numpy as np
import tsinsar as ts
import h5py
import sys
import matplotlib.pyplot as plt
import os
import multiprocessing as mp
import argparse

########Command line parsing
def parse():
    parser = argparse.ArgumentParser(description='Reads in the processed stack and computes wavelet coefficients + weights')
    parser.add_argument('-i',action='store', default=None, dest='iname', help='Input HDF5 file with the processed stack. Default: determined in program', type=str)
    parser.add_argument('-o',action='store', default='WAVELET.h5', dest='oname', help='Output HDF5 file with wavelet coeffs and weights. Default: WAVELETS.h5', type=str)
    parser.add_argument('-nchunk',action='store', default=40, dest='nchunk', help='Chunk per set for processing. Default: 40', type=int)
    parser.add_argument('-nproc', action='store', default=1, dest='nproc', help='Number of parallel threads. Default: 1', type=int)
    parser.add_argument('-d',action='store', default='data.xml', dest='dxml', help='To override the default data xml file. Default: data.xml', type=str)
    parser.add_argument('-p',action='store', default='mints.xml', dest='pxml', help='To override the default mints xml file. Default: mints.xml', type=str)
    inps = parser.parse_args()
    return inps

######Dummy class for parallel objects
class dummy:
    pass

####Template from Bryan Riel
class thread_invert(mp.Process):
    '''Class for FWTs in parallel using multiprocessing'''
    def __init__(self,par):
        '''par is a container for all the data needed.'''
	self.rname = par.rname
	self.wtnorm = par.wtnorm
	self.igram = par.igram
	self.wvlt = par.wvlt
	self.wts  = par.wts
	self.slice = par.slice
	self.wname = par.wname
	self.padfrac = par.padfrac
        self.startind = pars.start

	mp.Process.__init__(self)

    def run(self):
        '''Execute the thread.'''
	for ind in self.slice:
	    inp = self.igram[ind,:,:]
	    msk = np.isfinite(inp)

#            idict = {}
#            idict['pre'] = inp.copy()
	    inp = ts.mints.inpaint(inp)
#            idict['post'] = inp
#            ts.imagemany(idict, master='pre', show=False, save='Figs/Inpaint/I%03d.png'%(self.startind+ind+1))

	    outp,trim = ts.mints.Mirrortodyadic(inp,padfrac)
    	    mskp,trim = ts.mints.Mirrortodyadic(msk,padfrac)

#            idict['pre'] = inp
#            idict['post'] = outp
#            ts.imagemany(idict, master='pre', show=False, save='Figs/Mirror/I%03d.png'%(self.startind+ind+1))

	    if self.wname in ('meyer','MEYER'):
		wout = ts.meyer.fwt2_meyer(outp,3,3)
        	wt = ts.meyer.CoeffWeight(mskp,rname)
            else:
		wout = ts.wvlt.fwt2(outp,wvlt=self.wname)
		wt = ts.wvlt.CoeffWeight(mskp,wvlt=self.wname)
        	
	    wt = wt/self.wtnorm
		
	    self.wvlt[ind,:,:] = wout
	    self.wts[ind,:,:] = wt

#            idict['pre'] = wout
#            idict['post'] = wt
#            ts.imagemany(idict,show=False, save='Figs/FWT/I%03d.png'%(self.startind+ind+1))

if __name__ == '__main__':
    #######Main program
    inps = parse()
    logger = ts.logger

    #######Read in parameters from xml files
    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)

    #######Create directories as required
    ts.makedir(['Figs/Mirror','Figs/Inpaint','Figs/FWT'])

    ########Read in the directories
    h5dir = (dpars.data.dirs.h5dir)
    respdir = (dpars.data.dirs.respdir)

    ts.makedir([respdir])

    ######Read in processing flags
    netramp = (ppars.params.proc.netramp)
    gpsramp = (ppars.params.proc.gpsramp)

    if inps.iname is None:
        if netramp or gpsramp:
            stackname = os.path.join(h5dir,'PROC-STACK.h5')
        else:
            stackname = os.path.join(h5dir,'RAW-STACK.h5')
    else:
        stackname = os.path.join(h5dir,inps.iname)

    ######FWT and mirroring parameters
    wvt = (ppars.params.proc.wavelet)
    padfrac = (ppars.params.proc.minpad)

    ########Check if impulse response exits. Else create.
    Ny   = (dpars.data.subimage.length)
    Nx   = (dpars.data.subimage.width)

    Nrow = np.int(2**np.ceil(np.log2(Ny+padfrac*Nx)))
    Ncol = np.int(2**np.ceil(np.log2(Nx+padfrac*Nx)))

    ########Create impulse response if needed
    rname = os.path.join(respdir,'RESP-%s-%d-%d.h5'%(wvt,Nrow,Ncol))
    if not os.path.exists(rname):
        logger.info('Creating Impulse Response of size %d x %d'%(Nrow,Ncol))
        if wvt in ('meyer','MEYER'):
            ts.meyer.impulse_resp((Nrow,Ncol),rname)
        else:
            ts.wvlt.impulse_resp((Nrow,Ncol),rname,wvlt=wvt)
    else:
        logger.info('Precomputed impulse response found: %s'%rname)


    #######Setup the input stack.
    logger.info('Input h5file: %s'%stackname)
    fin =  h5py.File(stackname,'r')
    if netramp or gpsramp:
        igram = fin['figram']
    else:
        igram = fin['igram']

    Nifg = igram.shape[0]
    nn = igram.shape[1]
    mm = igram.shape[2]

    #######Set up the output wavelet stack.
    outname = os.path.join(h5dir,inps.oname)
    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Removing previous h5file: %s'%outname)

    #######Prepare output objects
    logger.info('Output h5file: %s'%outname)
    fout = h5py.File(outname,'w')
    fout.attrs['help'] = 'Forward Wavelet Transform coefficients and reliability measure.'

    wvlt = fout.create_dataset('wvlt',(Nifg,Nrow,Ncol),'f')
    wvlt.attrs['help'] = 'Wavelet coefficients of all the interferograms.'

    wts  = fout.create_dataset('wts',(Nifg,Nrow,Ncol),'f')
    wts.attrs['help'] = 'Weights associated with the wavelet coefficients.'


    ######Normalization factors
    if wvt in ('meyer','MEYER'):
        wtnorm = ts.meyer.CoeffWeight(np.ones((Nrow,Ncol)),rname)
    else:
        wtnorm = ts.wvlt.CoeffWeight(np.ones((Nrow,Ncol)),rname)


    nchunk = min(inps.nchunk,Nifg)

    #############Multiprocessing shared memory objects
    Warr = mp.Array('f',nchunk*Nrow*Ncol)   #Only created once and reused
    Wtarr = mp.Array('f',nchunk*Nrow*Ncol)  
    Iarr = mp.Array('f',nchunk*Ny*Nx)

    #######Initialize container
    pars = dummy()
    pars.igram = np.reshape(np.frombuffer(Iarr.get_obj(),dtype=np.float32),(nchunk,Ny,Nx))
    pars.wtnorm = wtnorm
    pars.rname = rname
    pars.wvlt = np.reshape(np.frombuffer(Warr.get_obj(),dtype=np.float32),(nchunk,Nrow,Ncol))
    pars.wts = np.reshape(np.frombuffer(Wtarr.get_obj(),dtype=np.float32),(nchunk,Nrow,Ncol))
    pars.wname = wvt
    pars.padfrac = padfrac

    #######Partitioning data
    ngrps = np.arange(0,Nifg+1,nchunk)
    if ngrps[-1] != Nifg:
        ngrps = np.append(ngrps,Nifg)

    logger.info('Computing Wavelet Transforms')

    #######Break stack into groups that fit in memory
    nproc = inps.nproc
    progb = ts.ProgressBar(maxValue=Nifg)
    for grpnum in xrange(len(ngrps)-1):
        pars.start = ngrps[grpnum]
        ninds = ngrps[grpnum+1] - ngrps[grpnum]      #Number of IFGs
        pars.igram[0:ninds,:,:] = igram[ngrps[grpnum]:ngrps[grpnum+1],:,:]        #From H5 file

        nproc = min(ninds,nproc)
        nlines = np.linspace(0,ninds,num=nproc+1).astype(np.int)
        threads = []

        ######Break a group into threads
        for k in xrange(nproc):
            pars.slice = np.arange(nlines[k],nlines[k+1])
            threads.append(thread_invert(pars))
            threads[k].start()

        for thrd in threads:
            thrd.join() 

        ######Write to file
        wvlt[ngrps[grpnum]:ngrps[grpnum+1],:,:] = pars.wvlt[0:ninds,:,:]
        wts[ngrps[grpnum]:ngrps[grpnum+1],:,:] = pars.wts[0:ninds,:,:]
        progb.update(ngrps[grpnum+1])

    progb.close()

    nn = igram.shape[1]
    mm = igram.shape[2]
    y0 = np.int((Nrow-nn)/2)
    x0 = np.int((Ncol-mm)/2)

    ######Crop region
    trim = np.array([y0,x0,nn,mm])
    g = fout.create_dataset('offset',data=trim)
    g.attrs['help'] = 'Crop information to recover the original data before padding.'


    ######Other useful data for writing to HDF5 file
    Jmat = fin['Jmat'].value
    bperp = fin['bperp'].value
    tims = fin['tims'].value
    dates = fin['dates'].value
    cmask = fin['cmask'].value

    fin.close()

    #######Writing other data
    g = fout.create_dataset('Jmat',data=Jmat)
    g.attrs['help'] = 'Connectivity matrix [-1,0,1]'

    g = fout.create_dataset('bperp',data=bperp)
    g.attrs['help'] = 'Array of perpendicular baseline values.'

    g = fout.create_dataset('tims',data=tims)
    g.attrs['help'] = 'SAR acquisition times in years.'

    g = fout.create_dataset('dates',data=dates)
    g.attrs['help'] = 'Ordinal values of SAR acquisition dates.'

    g = fout.create_dataset('cmask', data=cmask)
    g.attrs['help'] = 'Common pixel mask.'
    fout.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
