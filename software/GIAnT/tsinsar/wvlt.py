''' Interface for PyWavelet package.
.. Authors:
    
    Piyush Agram   <piyush@gps.caltech.edu>
    
.. Dependencies:
    
    numpy, h5py, pywt, scipy.ndimage.filters
    
.. Comments:
    
    Pylint checked'''

import numpy as np
import h5py
import pywt
from scipy.ndimage.filters import convolve1d
import logmgr

logger=logmgr.logger('giant')

######################Interface utils############################
def  get_corners(dims, jin, quad):
    ''' Get the 4 corners of the rectangular wavelet coefficient matrix.

    Args:

       * dims     -  The dimensions of the rectangular problem.
       * jin      -  Scale one is interested in. (>=3). Reference to column
       * quad     -  1(Vcoarse,Hcoarse), 2 (VcoarseHfine), 3 (VfineHcoarse), 4(Vfine,Hfine)

    Returns:

        * iii     - Row limits for the quadrant
        * jjj     - Column limits for the quadrant

    .. note::

       We also assume that we are dealing with long rectangles/squares.'''

    nnn = dims[0]
    mmm = dims[1]
    drdiff = np.int(np.log2(nnn/mmm))
    rin = jin+drdiff
    p2j = 2**jin
    p2r = 2**rin
    iii = np.zeros(2, dtype=np.int)
    jjj = np.zeros(2, dtype=np.int)
    if quad == 1:
        iii[0] = 0
        jjj[0] = 0
        iii[1] = p2r
        jjj[1] = p2j
    elif quad == 2:
        iii[0] = 0       #Quadrant 2
        iii[1] = p2r
        jjj[0] = p2j
        jjj[1] = 2*p2j
    elif quad == 3:
        iii[0] = p2r
        iii[1] = 2*p2r
        jjj[0] = 0
        jjj[1] = p2j
    elif quad == 4:
        iii[0] = p2r
        iii[1] = 2*p2r
        jjj[0] = p2j
        jjj[1] = 2*p2j

    return iii, jjj


def packcoeff(hin):
    '''Packs the wavelet coefficients returned in list format from
    pywt in a single 2D array for easy management with h5py.
    
    Args:
        
        * hin   -> Wavelet coefficients in pywt format
        
    Returns:
        
        * res   -> Wavelet coefficients in meeyr format'''
    
    nlevels = len(hin) - 1
    nn0 = hin[0].shape[0]
    mm0 = hin[0].shape[1]
    nnn = np.int(nn0 * (2**nlevels))
    mmm = np.int(mm0 * (2**nlevels))
    res = np.zeros((nnn, mmm))
    
    minlevel = np.int(np.log2(mm0))

    ######Set coarsest value
    [iii, jjj] = get_corners((nnn, mmm), minlevel, 1)
    
    res[iii[0]:iii[1], jjj[0]:jjj[1]] = hin[0]
    
    for kkk in xrange(0, nlevels):
        for qqq in xrange(3):
            [iii, jjj] = get_corners((nnn, mmm), minlevel+kkk, qqq+2)
            res[iii[0]:iii[1], jjj[0]:jjj[1]] = hin[kkk+1][qqq]

    return res

def unpackcoeff(hin, minlevel):
    '''Unpacks the wavelet coefficients in large 2D matrix format into 
    list format needed by pywt.
    
    Args:
        
        * hin      -> Wavelet coefficients in meyer format
        * minlevel -> Minlevel corresponding to wavelet used
        
    Returns:
        
        * res      -> Wavelet coefficients in pywt format'''
    
    nnn = hin.shape[0]
    mmm = hin.shape[1]
    
    nlevels = np.int(np.log2(mmm)-minlevel)
    res = []
    
    [iii, jjj] = get_corners((nnn, mmm), minlevel, 1)
    qnew = hin[iii[0]:iii[1], jjj[0]:jjj[1]]
    res.append(qnew)
    
    for kkk in xrange(nlevels):
        qqq = []
        for quad in xrange(3):
            [iii, jjj] = get_corners((nnn, mmm), minlevel+kkk, quad+2)
            qnew = hin[iii[0]:iii[1], jjj[0]:jjj[1]]
            qqq.append(qnew)
            
        res.append(qqq)
    
    return res

#####################################################################

##################FWT and IWT utils#############################

def fwt2(hin, wvlt='db12'):
    '''The forward 2D wavelet transform routine.
    
    Args:
        
        * hin   -> Input matrix. Dyadic dimensions.
        * wvlt  -> Wavelet name.
        
    Returns:
        
        * res   -> Wavelet coefficients in meyer format'''
    
#    nn = H.shape[0]
    mmm = hin.shape[1]
    
    wtbasis = pywt.Wavelet(wvlt)
    
    nlevels = pywt.dwt_max_level(mmm, wtbasis)
    
    if nlevels == 0:
        raise ValueError('Wavelet function longer than data')
    
#    minlevel = np.int(np.log2(mmm) - nlevels)
    
    res_pywt = pywt.wavedec2(hin, wvlt, level=nlevels, mode='per')

    res = packcoeff(res_pywt)

    return res


def iwt2(hin, wvlt='db12'):
    '''Inverse 2D Wavelet transform routine.
    
    Args:
        
        * hin    ->  Wavelet coefficients in meyer format. Dyadic dimensions.
        * wvlt   ->  Wavelet name.
        
    Returns:
        
        * res    ->  Inverse wavelet transform. Dyadic dimensions.'''
    
#    nn = H.shape[0]
    mmm = hin.shape[1]
    
#    nlevels = np.int(np.log2(mm)-3)

    wtbasis = pywt.Wavelet(wvlt)
    nlevels = pywt.dwt_max_level(mmm, wtbasis)
    minlevel = np.int(np.log2(mmm) - nlevels)
    
    res_pywt = unpackcoeff(hin, minlevel)
    res = pywt.waverec2(res_pywt, wvlt, mode='per')
    return res

###########################Optimized impulse response computation############
####### Faster more efficient.
####### Uses 1D transforms.

def impulse_resp(dims, fname, wvlt='db12'):
    '''Computes the impulse response for given wavelet and stores
    it in HDF5 format.

    Args:

        * dims       ->  Dyadic dimensions of 2D transform.
        * fname      ->  HDF5 file name for output.
        * wvlt       ->  Wavelet name.

    Returns:

        * None'''

    nnn = dims[0]
    mmm = dims[1]
    
    wtbasis = pywt.Wavelet(wvlt)
    
    nlevels = pywt.dwt_max_level(mmm, wtbasis)
    
    kscl = np.int(np.log2(nnn))
    jscl = np.int(np.log2(mmm))
    
    minlevel = jscl - nlevels
    drdiff = kscl - jscl
    p2dr = 2**drdiff

    fout = h5py.File(fname, 'w')    #Open HDF file for writing

    fout.create_dataset('minlevel', data = minlevel)
    fout.create_dataset('nlevels', data = nlevels)
    logger.info('Wavelet = %s'%(wvlt))
    for wtl in xrange(1, nlevels+1):
        kkk = jscl - wtl
        logger.info('Processing scale: %d'%(kkk))
        p2k = 2**kkk
        p2r = p2k*p2dr
        numl = nnn/p2r
        numw = mmm/p2k
        cxname = 'Cx-%d'% (kkk)
        dxname = 'Dx-%d'% (kkk)
        cyname = 'Cy-%d'% (kkk)
        dyname = 'Dy-%d'% (kkk)

        yct = np.zeros((p2r, numl))
        ydt = np.zeros((p2r, numl))

        if numl == numw:
            for ppp in xrange(numl):
                yyy = np.zeros(nnn)
                yyy[(nnn/2)+ppp] = 1.0
                fwy = pywt.wavedec(yyy, wtbasis, level=wtl, mode='per')
                yct[:, ppp] = fwy[0]
                ydt[:, ppp] = fwy[1]
                
            yct = np.abs(yct)
            ydt = np.abs(ydt)
            fout.create_dataset(cyname, data=yct, dtype='float32')
            fout.create_dataset(dyname, data=ydt, dtype='float32')
        else:
            xct = np.zeros((p2k, numw))
            xdt = np.zeros((p2k, numw))

            for ppp in xrange(numl):
                yyy = np.zeros(nnn)
                yyy[(nnn/2)+ppp] = 1.0
                fwy = pywt.wavedec(yyy, wtbasis, level=wtl, mode='per')
                yct[:, ppp] = fwy[0]
                ydt[:, ppp] = fwy[1]
            
            for qqq in xrange(numw):
                xxx = np.zeros(mmm)
                xxx[(mmm/2)+qqq] = 1.0
                
                fwx = pywt.wavedec(xxx, wtbasis, level=wtl, mode='per')
                xct[:, qqq] = fwx[0]
                xdt[:, qqq] = fwx[1]

            xct = np.abs(xct)
            yct = np.abs(yct)
            xdt = np.abs(xdt)
            ydt = np.abs(ydt)
            fout.create_dataset(cxname, data=xct, dtype='float32')
            fout.create_dataset(dxname, data=xdt, dtype='float32')
            fout.create_dataset(cyname, data=yct, dtype='float32')
            fout.create_dataset(dyname, data=ydt, dtype='float32')


    fout.close()   #Close HDF file
    return


def coeff_weight(bmask, rname):
    '''Computes the reliability score of each wavelet coefficient
    by convolving the absolute value of impulse response with 
    data mask.

    Args:

        * bmask   ->  Binary mask [0,1] 
        * rname   ->  HDF5 file with impulse response

    Returns:

        * wts     -> Weights of the coefficients.'''

    nnn = bmask.shape[0]
    mmm = bmask.shape[1]
    jscl = np.int(np.log2(mmm))
    wts = np.zeros((nnn, mmm))
    fin = h5py.File(rname, 'r')
    minlevel = fin['minlevel'].value

    for mind in xrange(minlevel, jscl):
        p2m = 2**mind
        p2r = p2m*(nnn/mmm)
        numi = nnn/p2r
        numj = mmm/p2m
        cxname = 'Cx-%d'% (mind)
        dxname = 'Dx-%d'% (mind)
        cyname = 'Cy-%d'% (mind)
        dyname = 'Dy-%d'% (mind)

        if numi != numj:
            cxx = fin[cxname].value
            dxx = fin[dxname].value
            cyy = fin[cyname].value
            dyy = fin[dyname].value
        else:
            cyy = fin[cyname].value
            dyy = fin[dyname].value
            cxx = cyy
            dxx = dyy

        ####Quadrant 2
        [yy2, xx2] = get_corners((nnn, mmm), mind, 3)
        [yy3, xx3] = get_corners((nnn, mmm), mind, 2)
        [yy4, xx4] = get_corners((nnn, mmm), mind, 4)

        for ppp in xrange(numi):
            for qqq in xrange(numj):
                btemp = bmask[ppp::numi, qqq::numj]
                respy = convolve1d(btemp, cyy[:, ppp], axis=0,
                        mode='wrap')
                respz = convolve1d(respy, dxx[:, qqq], axis=-1,
                        mode='wrap')
                wts[yy2[0]:yy2[1], xx2[0]:xx2[1]] += respz

                if mind == minlevel:
                    respz = convolve1d(respy, cxx[:, qqq], axis=-1,
                            mode='wrap')
                    wts[0:p2r, 0:p2m] += respz

                respy = convolve1d(btemp, dyy[:, ppp], axis=0,
                        mode='wrap')
                respz = convolve1d(respy, cxx[:, qqq], axis=-1,
                        mode='wrap')
                wts[yy3[0]:yy3[1], xx3[0]:xx3[1]] += respz

                respz = convolve1d(respy, dxx[:, qqq], axis=-1,
                        mode='wrap')
                wts[yy4[0]:yy4[1], xx4[0]:xx4[1]] += respz


    fin.close()

    return wts

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
