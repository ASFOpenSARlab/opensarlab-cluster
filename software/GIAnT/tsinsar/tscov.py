'''Utilities for dealing with covariances in time-series InSAR analysis.

.. authors:

    Romain Jolivet <jolivetr@caltech.edu>
    Piyush Agram <piyush@gps.caltech.edu>
    
.. Dependencies:

    sys, numpy, scipy, matplotlib,tsinsar '''

import sys
import numpy as np
import scipy.optimize as opt
import matplotlib.pyplot as plt
import tsinsar as ts
import random

#-------------------------------------------------------------------
#Structure function
def cov_fn(t,sig,lam):
    '''Evaluates the approximate covariance function with given parameters.

    .. Args:

        * t      -> Array of distances
        * sig    -> Array/ scalar representing amplitude
        * lam    -> Array/ scalar representing scale length

    .. Returns:

        * cov   -> Covariance function evaluated with given parameters.'''
    return sig*(np.exp(-(t**2)/(2*lam**2)))

#-------------------------------------------------------------------
# Orbit shape
def rampcov_fn(t,a,b,c):
    '''Evaluates the ramp polynomial.

    .. Args:

        * t     -> 2D array (x,y)
        * a,b,c -> Ramp polynomial coefficients

    .. Returns:

        * ramp  -> ramp evaluated for all points in t.'''
    dx = t[:,0]
    dy = t[:,1]
    return c+a*dx*dx + b*dy*dy + 2*a*b*dx*dx*dy*dy


#------------------------------------------------
def estramp(phs,poly):
    '''Estimates the ramp polynomial from a 2D matrix.

    .. Args:

        * phs   -> 2D matrix
        * poly  -> Polynomial order 

    .. Returns:

        * ramppoly  -> ramp polynomial'''
    nn = phs.shape[0]
    mm = phs.shape[1]
    [ii,jj] = np.where(np.isfinite(phs) & (phs!=0))
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

    ramp = np.linalg.lstsq(A,gval)
    ramppoly = ramp[0]

    return ramppoly


def deramp(phs,ramppoly):
    '''Deramp a matrix using the given ramp polynomial.

    .. Args:

        * phs       -> 2D matrix to be corrected
        * ramppoly  -> Ramp polynomial

    .. Returns:

        * phsc      -> corrected phase matrix
        * dphs      -> estimated ramp'''
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
    phsc = phs + dphs

    return phsc, dphs


#-------------------------------------------------------------------
# Computes the empirical covariance on an interferogram
def phi2covar(phi,frac,scale,plot=False,ramp_remov=True,maxdist=False):

	'''Empirical covariance estimator

	.. Args: 
	
	   * phi      -> Radar phase array (range, azimuth)
	   * frac     -> Fraction of the total number of pixels used for covariance computing
	   * scale    -> Distance Scaling

	.. Kwargs

	   * plot       -> Turns on plotting (off by default)
	   * ramp_remov -> Turns of ramp_removal (on by default)
	   * maxdist    -> Maximum distance to fit the covariance function

	.. Returns: 
	
	   * par      -> Parameters of the covariance function as defined in cov_fn
	   * qual     -> RMS of the fit'''


        if ramp_remov:
            ramppoly = estramp(phi,3)
            phi, ramp = deramp(phi,ramppoly)
            a = ramppoly[0]
            b = ramppoly[1]
            c = ramppoly[2]

	# Get Samples
	[ii,jj] = np.where(np.isnan(phi) == False)
        val = phi[ii,jj]
	
	assert len(ii) is not 1, 'No pixels'

        num = len(ii)
        Nsamp = np.floor(frac*num)
	
        samp = np.random.random_integers(0,num-1,size=(Nsamp,2))
        s1 = samp[:,0]
        s2 = samp[:,1]
        dx = scale*(ii[s1]-ii[s2])
        dy = scale*(jj[s1]-jj[s2])
        dist = np.sqrt(dx*dx+dy*dy)
        ind = dist.nonzero()
        dist = dist[ind]
        dx = dx[ind]
        dy = dy[ind]
        Nsamp = len(dist)
        dv = val[s1]*val[s2]
        dv = dv[ind]
	
	# Average to get an empirical covariance function
	if maxdist:
		xt = np.arange(0,np.floor(maxdist))
	else:
		xt = np.arange(0,np.floor(dist.max()))
	ecv = []
	x = []
	for i in range(len(xt)):
		ix = np.where((dist<xt[i]+1) & (dist>=xt[i]))
		if ix:
			ecvt = ts.nanmean(dv[ix])
			if not np.isnan(ecvt):
				ecv.append(ecvt)
				x.append(xt[i])

	ecv = np.array(ecv)
	x = np.array(x)

	# Estimate covariance function parameters
	par, pars_cov = opt.curve_fit(cov_fn,x,ecv)
        sig = par[0]
        lam = par[1]

	y = cov_fn(x,par[0],par[1])
	qual = np.sqrt(np.sum((ecv - y)**2)/len(y))

	if plot:
		print 'SIGMA:', par[0]
		print 'LAMBDA:', par[1]
                plt.figure()
		if ramp_remov:
			print 'RAMP:' , a, b
			plt.subplot(221)
			plt.imshow(phi)
			plt.colorbar()
			colorlim = [np.nanmin(phi),np.nanmax(phi)]
			plt.subplot(223)
			plt.imshow(ramp)
			plt.colorbar()
			for im in plt.gca().get_images():
		                im.set_clim(colorlim)
		else:
			plt.subplot(121)
			plt.imshow(phi)
                        plt.colorbar()

		plt.subplot(122)
                plt.hold(True)
                plt.scatter(x,ecv,s=1,c='k')
                plt.plot(x,y)
                plt.xlabel('Normalized Distance')
                plt.ylabel('Phase Variance')
		plt.show()

	return par,qual,x,ecv

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
