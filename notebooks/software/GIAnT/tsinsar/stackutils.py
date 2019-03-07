'''Utilities for dealing with interferogram stacks for time-series 
InSAR analysis.

.. author:

    Piyush Agram.
    
.. Dependencies:
    
    numpy, scipy.linalg, scipy.stats'''


import numpy as np
import scipy.linalg as la
import scipy.stats as st
import matplotlib.pyplot as plt
import matutils as mu

############################Math Utils#################################
##Compute standard deviation of array / matrix
def nanmean(x):
    '''Returns the nan mean of the array.'''
    
    sumv = np.nansum(x)
    denv = np.sum(np.isfinite(x))
    if denv !=0 :
        nm = sumv/(1.0*denv)
    else:
        nm = np.NaN
    return nm

####Regular deramping using a ramp.
def estramp(phs,mask,poly=3):
    '''Estimate the best-fitting ramp parameters for a matrix.
    
    Args:
    
        * phs     -  Input unwrapped phase matrix.
        * mask    -  Mask of reliable values.
        * poly    -  Integer flag for type of correction.
        
                        1 - Constant
                        3 - Plane
                        4 - Plane + cross term
    
    Returns:
    
        * ramppoly - Polynomial corresponding to the rank'''

    nn = phs.shape[0]
    mm = phs.shape[1]
    [ii,jj] = np.where((mask != 0) & np.isfinite(phs))
    y = ii/(1.0*nn)
    x = jj/(1.0*mm)
    numg = len(ii)
    gval = phs[ii,jj] #Good values
    if poly==1:
        A = np.ones(numg)
    elif poly==3:
        A = np.column_stack((np.ones(numg),x,y))
    elif poly==4:
        A = np.column_stack((np.ones(numg),x,y,x*y))


    ramp = la.lstsq(A,gval, cond=1.0e-8)
    ramppoly = ramp[0]

    return ramppoly


#######Get valid pixels in GPS and data
def getvalidpix(igps,minnum=5,neigh=3):
    nn = igps.mask.shape[0]
    mm = igps.mask.shape[1]
    ngps = len(igps.xi)

    minx = (igps.xi-neigh).clip(0,mm-1)
    maxx = (igps.xi+neigh).clip(0,mm-1)
    miny = (igps.yi-neigh).clip(0,nn-1)
    maxy = (igps.yi+neigh).clip(0,nn-1)

    idata = np.zeros(ngps,np.bool)

    for k in xrange(ngps):
        data = igps.mask[miny[k]:maxy[k], minx[k]:maxx[k]]
        idata[k] = (np.nansum(1*data.flatten())>0)

    ind = np.flatnonzero(np.isfinite(igps.gdata) & np.isfinite(igps.gerr) & idata)
    nvalid = len(ind)

    if (nvalid < minnum):
        raise ValueError('Not enough GPS stations.')
    else:
        return nvalid, ind



#######Estimate ramp with GPS
def estramp_gps(phs, gps, poly, minnum=5, neigh=3):
    '''Estimate the best-fitting ramp parameters for a matrix 
    using information in the GPS structure.

    Args:

        * phs   - Input unwrapped phase matrix.
        * poly  - Integer flag for type of correction.
        * gps   - Gps information. (xi,yi,disp,disperr)

    Kwargs:

        * minnum - Minimum number of GPS needed for valid correction.
        * neigh  - Neighborhood of GPS station to match InSAR.

    Returns:

        * ramppoly - Polynomial corresponding to the rank'''

    nn = phs.shape[0]
    mm = phs.shape[1]
    ngps = len(gps.xi)

    idisp = np.zeros(ngps)
    idisperr = np.zeros(ngps)

    minx = (gps.xi-neigh).clip(0,mm-1)
    maxx = (gps.xi+neigh).clip(0,mm-1)
    miny = (gps.yi-neigh).clip(0,nn-1)
    maxy = (gps.yi+neigh).clip(0,nn-1)

    for k in xrange(ngps):
        data = phs[miny[k]:maxy[k], minx[k]:maxx[k]]
        idisp[k] =  nanmean(data)
        idisperr[k] = st.nanstd(data.flatten())

    ddisp = idisp-gps.disp
    dderr = np.sqrt((gps.disperr**2) + (idisperr**2))

    mask = np.isfinite(ddisp) & np.isfinite(dderr)
    numg = mask.sum()
    if (numg >= minnum):
        x = gps.xi[mask]/(1.0*mm)
        y = gps.yi[mask]/(1.0*nn)
        numg = mask.sum()
        gval = ddisp[mask]
        Wval = 1.0/dderr[mask]
        if poly==1:
            A = np.ones(numg)
        elif poly==3:
            A = np.column_stack((np.ones(numg),x,y))
        elif poly==4:
            A = np.column_stack((np.ones(numg),x,y,x*y))

#        A1 = mu.dmultl(Wval,A)
#        gval1 = gval*Wval

        ramp = la.lstsq(A,gval, cond=1.0e-8)
        ramppoly = ramp[0]

        return ramppoly

    else:
        raise ValueError('Not enough GPS stations.')



def deramp(phs,ramppoly):
    '''Deramp a matrix with the given ramp polynomial.
    
    .. Args:
    
        * phs             Input matrix
        * ramppoly        Ramp polynomial
        
    .. Returns:
    
        * dphs            Deramped phase matrix.'''
    
    
    nn = phs.shape[0]
    mm = phs.shape[1]
    X,Y = np.meshgrid(np.arange(mm)*1.0,np.arange(nn)*1.0)
    X = X.flatten()/(mm*1.0)
    Y = Y.flatten()/(nn*1.0)

    poly = len(ramppoly)
    if poly==1:
        A = np.ones(nn*mm)
    elif poly==3:
        A=np.column_stack((np.ones(nn*mm),X,Y))
    elif poly==4:
        A=np.column_stack((np.ones(nn*mm),X,Y,X*Y))

    dphs = np.dot(-A,ramppoly)
    del A
    dphs = np.reshape(dphs,(nn,mm))
    dphs = phs + dphs

    return dphs


def LookDown(A,n,method,var=False):
    '''Lookdown the matrix by an integer factor.
    
    .. Args:
    
        * A                Input matrix
        * n                Integer multi-looking factor
        * method           Can be 'MEAN' or 'MEDIAN'
    
    .. Kwargs:
    
        * var             Should output include variance.
        
    .. Returns:
    
        * B                Multi-looked image.
        * sB               Standard deviation of the looked image.'''
    
    nn = A.shape[0]
    mm = A.shape[1]

    newn = np.int_(np.floor(nn/(n*1.0)))
    newm = np.int_(np.floor(mm/(n*1.0)))

    B = np.zeros((newn,newm))*np.nan       #Initialize with NaNs
    if var:
        sB = np.zeros((newn,newm))*np.nan

    if method in ('MEAN'):
        for y in xrange(0,newn):
            miny= y*n
            maxy= np.min((nn,(y+1)*n))
            for x in xrange(0,newm):
                minx = x*n
                maxx = np.min((mm,(x+1)*n))
                Asub = A[miny:maxy,minx:maxx]
                mean = nanmean(Asub)
                if mean is not None:
                    B[y,x] = mean

                    if var:
                        sB[y,x] = st.nanstd(Asub.flatten())

    elif method in ('MEDIAN'):
        for y in xrange(0,newn):
            miny= y*n
            maxy= np.min((nn,(y+1)*n))
            for x in xrange(0,newm):
                minx = x*n
                maxx = np.min((mm,(x+1)*n))
                Asub = A[ymin:ymax,xmin:xmax]
                mean = st.nanmedian(Asub.flatten())

                if mean is not None:
                    B[y,x] = mean

                    if var:  #Possibly use median diff
                        sB[y,x] = st.nanstd(Asub.flatten())

    else:
        raise ValueError('Undefined method %s in LookDown'%(method))

    if var:
        return B,sB
    else:
        return B

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
