import numpy as np
import matplotlib.pyplot as plt
import scipy.ndimage.filters as lm
import scipy.stats as ss
import tsinsar as ts
import solver.iterL1 as slv


####Dummy class to serve as a container.
class dummy:
    pass


####Decomposition using Gaussian filter bands.
def Gsmooth(A, rfact, sigma, thresh=0.95):
    '''Gaussian filtering of matrix A.

    Args:

        *  A    -> Input matrix to be smoothed.
        * rfact -> Window size of the filter
        * sigma -> Gaussian function width
        
    Kwargs:
        
        * thresh -> Maximum fraction of missing data in a window'''

    if (rfact%2) != 0:
        raise ValueError('Window size should be an even number.')

    if np.any(rfact > A.shape):
        raise ValueError('Window size greater than input dimensions.')

    nr = A.shape[0] - rfact
    nc = A.shape[1] - rfact

    A[np.isnan(A)] = 0.0
    x = (np.arange(rfact+1)-rfact/2.0)**2
    
    gauss = np.exp(-0.5*(x[:,None] + x[None,:])/(sigma*sigma));
    gauss = gauss / np.sum(gauss)
    filt = np.ones((rfact+1,rfact+1))

    #Number of valid pixels in a filtering window.
    pthresh = np.int(thresh*(rfact+1)*(rfact+1))

    #####Non-Nan values
    mask = 1.0 - np.isnan(A)

    Bmat = lm.convolve(A, gauss, mode='constant', cval=0.0)
    Wmat = lm.convolve(mask, filt, mode='constant', cval=0.0)

    Bmat[Wmat<pthresh] = np.nan
    Bmat[:,0:rfact/2] = np.nan
    Bmat[:,-rfact/2:] = np.nan
    Bmat[0:rfact/2,:] = np.nan
    Bmat[-rfact/2:,:] = np.nan

    return Bmat



class gslice:
    def __init__(self, Amat, ramp=0, looks=1):

        if looks == 1:
            self.data = Amat.copy()
        else:
            self.data = ts.LookDown(Amat, looks, 'MEAN')

        if ramp==0:
            self.deramp = self.data
        else:
            eramp = ts.estramp(self.data, np.isfinite(self.data),poly=3)
            self.deramp = ts.deramp(self.data, eramp)

        self.slist = []
        self.minscale = None
        self.maxscale = None

    def decompose(self, minscale=1, maxscale=None, thresh=0.95, plot=False):
        '''Decompose current data into a list of values at different scales.
        
        Kwargs:
            
            * minscale  -> Minimum scale for filter band decomposition
            * maxscale  -> Maximum scale for filter band decomposition
            * thresh    -> Maximum fraction of missing data in a window
            * plot      -> Boolean flag for plotting'''
        self.slist = []
        self.minscale = minscale

        if maxscale is None:
            dims = np.round(np.min(self.data.shape)/2.0)
            self.maxscale = np.int(np.floor(np.log2(dims)))
        else:
            self.maxscale = maxscale

        for kk in xrange(self.maxscale,self.minscale-1,-1):
            Fs = np.int(2**kk)
            B = Gsmooth(self.data, Fs, Fs/2, thresh=thresh)
            B = B - ss.nanmean(B.flatten())
            self.slist.append(B)

#        B0 = self.data - ss.nanmean(self.data.flatten())
#        self.slist.append(B0)

        prev = self.slist[0]
        for kk in xrange(1,len(self.slist)):
            now = self.slist[kk]-prev
            prev = self.slist[kk].copy()
            self.slist[kk] = now
         
            if plot:
                plt.imshow(now)
                plt.colorbar()
                plt.title('%d'%(kk))
                plt.show()

    def fitscales(self, Tobj, scale=4, tolr=1.0e-5, tolx = 1.0e-5, ngroup=50, niter=30):
        '''Linear fit between a band-filtered dataset and another band filtered dataset at various scales.

        Args:
            
            * Tobj     -> Another gslice object created with same parameters

        Kwargs:

            * scale    -> Scaling value for Iterative L1 solver. 
            * tolr     -> Tolerance for residuals
            * tolx     -> Tolerance for model fit
            * ngroup   -> Number of subgroups 
            * niter    -> Number of iterations'''

        maxscale = self.maxscale
        minscale = self.minscale
        stride = 2**(np.arange(maxscale, minscale-1,-1)-1)
        stride = np.append(stride,stride[-1])
        stride = np.clip(stride,1,stride.max())

        if len(self.slist) != len(Tobj.slist):
            raise ValueError('The number of scales do not match.')

        nscale = maxscale-minscale+1

        K = np.zeros(nscale)
        B = np.zeros(nscale)
        Ksigma = np.zeros(nscale)
        Bsigma = np.zeros(nscale)
        R = np.zeros(nscale)

        Tsample = []
        Asample = []
        for kk in xrange(nscale):
            A = self.slist[kk]
            T = Tobj.slist[kk]

            mask = np.isfinite(A) & np.isfinite(T)

            G = T[mask]
            y = A[mask]

            Tsample.append(G)
            Asample.append(y)

            G = np.column_stack((G,np.ones(len(G))))
            
            if len(y)<=12:
                scale_in = 2
            else:
                scale_in = scale

            m, KBsigma = slv.L1error_BS(G,y, tolr=tolr, tolx=tolx, niter = niter, ngroup=ngroup, scale=scale_in)
            K[kk] = m[0]
            B[kk] = m[1]
            Ksigma[kk] = KBsigma[0]
            Bsigma[kk] = KBsigma[1]
            R[kk] = 1 - np.sum((y - np.dot(G,m))**2)/(np.var(y)*len(y))

        ####Fitting deramped original interferogram

        Tderamp = Tobj.deramp
        Aderamp = self.deramp - ss.nanmean(self.deramp.flatten())
        mask = np.isfinite(Aderamp) & np.isfinite(Tderamp)

        G = Tderamp[mask]
        y = Aderamp[mask]

        G = np.column_stack((G,np.ones(len(G))))
        if len(y)<=12:
            scale_in = 2
        else:
            scale_in = scale
        

        m, KBSigma = slv.L1error_BS(G,y,tolr=tolr, tolx=tolx, niter=niter, ngroup=ngroup, scale=scale_in)
        
        K_deramp = m[0]
        B_deramp = m[1]
        Ksigma_deramp = KBsigma[0]
        Bsigma_deramp = KBsigma[1]
        R_deramp = 1 - np.sum((y - np.dot(G,m))**2)/(np.var(y)*len(y))

        #######Putting the channels together
        G = np.concatenate(Tsample)
        y = np.concatenate(Asample)

        G = np.column_stack((G, np.ones(len(G))))
        m, KBsigma = slv.L1error_BS(G,y, tolr=tolr, tolx=tolx, niter = niter, ngroup=ngroup, scale=scale_in)
        K = np.append(K,m[0])
        B = np.append(B,m[1])
        Ksigma = np.append(Ksigma, KBsigma[0])
        Bsigma = np.append(Bsigma, KBsigma[1])
        Resg = 1 - np.sum((y - np.dot(G,m))**2)/(np.var(y)*len(y))
        R = np.append(R,Resg)

        match = dummy()

        #####Taking out the largest scale. Not always good.
        match.K = K[1:] 
        match.B = B[1:]
        match.Ksigma = Ksigma
        match.Bsigma = Bsigma
        match.R = R 
        match.K_deramp = K_deramp
        match.B_deramp = B_deramp
        match.Ksigma_deramp = Ksigma_deramp
        match.Bsigma_deramp = Bsigma_deramp
        match.R_deramp = R_deramp
        return match


def netinvert(mlist, G):
    Nifg = len(mlist)

    Kobs = []
    bobs = []

    for kk in xrange(Nifg):
        Kobs.append(mlist[kk].K)
        bobs.append(mlist[kk].B)

    Kobs = np.row_stack(Kobs)
    bobs = np.row_stack(bobs)

    m1, Sk_multi = slv.L1error_BS(G, Kobs)
    m2, Sb_multi = slv.L1error_BS(G, bobs)

    fn = np.column_stack((m1,m2))
    return fn



############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
