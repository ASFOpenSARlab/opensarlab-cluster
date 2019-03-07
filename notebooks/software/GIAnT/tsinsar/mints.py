'''MInTS utilities for time-series InSAR analysis.

.. Authors:

    Piyush Agram <piyush@gps.caltech.edu>

.. Dependencies:

    numpy, scipy.sparse, scipy.sparse.linalg, tsutils
    
.. Comments:
    
    Pylint checked'''

import numpy as np
import scipy.sparse as sp
import tsutils as tu
import logmgr

logger = logmgr.logger('giant')

### A - n x m Array with some NaNs to be filled in
### I have only translated the spring metaphor, method = 4.
### The original matlab inpaint_nans package by John D'Errico can
### be downloaded from
### http://www.mathworks.com/matlabcentral/fileexchange/4551-inpaintnans

def inpaint(ain):
    '''Returns the inpainted matrix using the spring metaphor.
       All NaN values in the matrix are filled in.
       
       Based on the original inpaintnans package by John D'Errico.
       http://www.mathworks.com/matlabcentral/fileexchange/4551-inpaintnans'''

    dims = ain.shape
    bout = ain.copy()
    nnn = dims[0]
    mmm = dims[1]
    nnmm = nnn * mmm
    flag = np.isnan(ain)

    [iii, jjj] = np.where(flag == False)
    [iin, jjn] = np.where(flag == True)
    del flag
    nnan = len(iin)    #Number of nan.
   
    if nnan == 0:
        return bout
    
    logger.debug('Inpainting : %d percent'% (np.round(nnan * 100/(nnmm * 1.0))))
        
    hv_springs = np.zeros((4 * nnan, 2), dtype=np.int)
    cnt = 0
    for kkk in xrange(nnan):
        ypos = iin[kkk]
        xpos = jjn[kkk]
        indc = ypos * mmm + xpos
        if(ypos > 0):
            hv_springs[cnt, :]   = [indc - mmm, indc]   #Top
            cnt = cnt + 1

        if(ypos < (nnn - 1)):
            hv_springs[cnt, :] = [indc, indc + mmm]  #Bottom
            cnt = cnt + 1

        if(xpos>0):
            hv_springs[cnt, :] = [indc - 1, indc]  #Left
            cnt = cnt + 1

        if(xpos < (mmm - 1)):
            hv_springs[cnt, :] = [indc, indc + 1]  #Right
            cnt = cnt + 1

    hv_springs = hv_springs[0:cnt, :]

    tempb = tu.unique_rows(hv_springs)
#    tempb = np.unique(hv_springs.view([('', hv_springs.dtype)] * 
#        hv_springs.shape[1])).view(hv_springs.dtype).reshape(-1,
#                hv_springs.shape[1])

    cnt = tempb.shape[0]
    
    alarge = sp.csc_matrix((np.ones(cnt), (np.arange(cnt), tempb[:, 0])),
            shape=(cnt, nnmm))
    alarge = alarge + sp.csc_matrix((-np.ones(cnt), (np.arange(cnt)
        , tempb[:, 1])), shape=(cnt, nnmm))

    indk = iii * mmm + jjj
    indu = iin * mmm + jjn
    dkk  = -ain[iii, jjj]
    del iii
    del jjj

    aknown = sp.csc_matrix(alarge[:, indk])
    rhs = sp.csc_matrix.dot(aknown, dkk)
    del aknown
    del dkk
    anan = sp.csc_matrix(alarge[:, indu])
    dku = sp.linalg.lsqr(anan, rhs)
    bout[iin, jjn] = dku[0]
    return bout


def Mirrortodyadic(ain, frac):
    '''Mirror the input matrix to a dyadic size.

    Args:

        * ain            Input Matrix
        * frac           Minimum fraction of mirroring.
        
        
    Returns:
        
        * mmat           Mirrored matrix
        * coords         Coords of original data'''
    
    nnn = ain.shape[0]
    mmm = ain.shape[1]
    newn = np.round(nnn + frac*mmm)
    newm = np.round((1+frac) * mmm)

    nrow = np.int(2**np.ceil(np.log2(newn)))
    ncol = np.int(2**np.ceil(np.log2(newm)))
    mmat = np.zeros((nrow, ncol))
    otop = np.int((nrow - nnn) / 2)
    obot = nrow - otop - nnn
    olef = np.int( (ncol - mmm) / 2)
    orig = ncol - olef - mmm

    mmat[otop:otop + nnn, olef:olef + mmm] = ain   #Core
    mmat[0:otop, olef:olef + mmm] = np.flipud(ain[0:otop, :])
    mmat[-obot:, :] = np.flipud(mmat[otop + nnn - obot:otop + nnn, :]) 

    mmat[:, 0:olef] = np.fliplr(mmat[:, olef:2 * olef]) 
    mmat[:, -orig:] = np.fliplr(mmat[:, olef + mmm - orig:olef + mmm]) 
    coords = [otop, olef, nnn, mmm]
    return mmat, coords



###############################End of math utils#############################

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
