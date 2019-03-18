''' Meyer wavelet transforms in python.
Based on Wavelab850 package from Stanford University.
    
.. Authors:
        
    Piyush Agram   <piyush@gps.caltech.edu>
        
.. Dependencies:
        
    numpy, h5py, scipy.ndimage.filters'''

import numpy as np
import h5py
from scipy.ndimage.filters import convolve1d
import logmgr

logger = logmgr.logger('giant')

######math utils
def pow_1(xin):
    '''Power of -1. Faster.
    
    .. Args:
        
        * xin    -> Input array of integers
        
    .. Returns:
        
        * xout   -> (-1)^xin'''

    xout = (1-2*(xin%2)) 
    return xout

################Utility functions for the transforms#######
def quasi_dct(xin, direc):
    """ Quasi Discrete Conp.sine Transform routine

    .. Args:

        xin   : signal of dyadic length
        direc : direction. 'f' for forward (or) 'i' for inverse

    .. Returns:

        cout  : output array """

    nin = len(xin)-1
    root2 = np.sqrt(2.0)
    if direc in ('f', 'F'):
        xin[0] = xin[0]/root2
        xin[nin] = xin[nin]/root2
        rxin = np.zeros((nin+1, 2))
        rxin[:, 0] = xin
        rxin = rxin.flatten()
        ynin = np.zeros(4*nin)
        ynin[0:2*nin+2] = rxin
        wnin = np.real(np.fft.fft(ynin))
        cout = root2*wnin[0:nin+1:2]/np.sqrt(1.0*nin)
        cout[0] = cout[0]/root2
    elif direc in ('i', 'I'):
        xin[0] = xin[0]/root2
        rxin = np.zeros((nin+1, 2))
        rxin[:, 0] = xin
        rxin = rxin.flatten()
        ynin = rxin
        wnin = np.real(np.fft.fft(ynin))
        cout = root2*wnin[0:nin+2]/np.sqrt(1.0*(nin+1))
        cout[0] = cout[0]/root2
        cout[nin+1] = cout[nin+1]/root2

    return cout

def QuasiDST(x,direc):
    ''' Quasi Discrete Sine Transform routine
        Args:
            x       : signal of dyadic length
            direc   : direction. 'f' for forward (or) 'i' for inverse
        Returns:
            s       : output array'''
    n = len(x)+1
    r2 = np.sqrt(2.0)
    if direc in ('f','F'):
        rx = np.zeros((n-1,2))
        rx[:,1] = x
        rx = rx.flatten()
        y = np.zeros(4*n)
        y[1:2*n-1] = rx
        w = -1.0*np.imag(np.fft.fft(y))
        s = r2*w[2:n+1:2]/np.sqrt(1.0*n)
    elif direc in ('i','I'):
        rx = np.zeros((n-1,2))
        rx[:,1] = x
        rx = rx.flatten()
        y = np.zeros(2*n)
        y[1:2*n-1] = rx
        w = -1.0*np.imag(np.fft.fft(y))
        s = r2*w[1:n]/np.sqrt(1.0*n)

    return s


def dst_i(x):
    ''' Variant of dst - wavelab'''
    n =len(x)+1
    y = np.zeros(2*n)
    y[1:n] = -x
    z = np.fft.fft(y)
    c = np.sqrt(2.0/(1.0*n)) * np.imag(z[1:n])
    return c

def dst_ii(x):
    '''Variant of dst - wavelab'''
    n = len(x)
    rx = np.zeros((n,2))
    rx[:,1] = x
    rx = rx.flatten()
    y = np.concatenate((rx,np.zeros(2*n)))
    w = -np.imag(np.fft.fft(y))
    s = np.sqrt(2.0/(1.0*n))*w[1:n+1]
    s[n-1] = s[n-1]/np.sqrt(2.0)
    return s

def dst_iii(x):
    '''Variant of dst - wavelab'''
    n = len(x)
    x[n-1] = x[n-1]/np.sqrt(2.0)
    y = np.zeros(4*n)
    y[1:n+1] = x
    w = - np.imag(np.fft.fft(y))
    s = np.sqrt(2.0/(1.0*n))*w[1:2*n:2]
    return s

def dct_ii(x):
    '''Variant of dct - wavelab'''
    n = len(x)
    rx = np.zeros((n,2))
    rx[:,1] = x
    rx = rx.flatten()
    y = np.concatenate((rx,np.zeros(2*n)))
    w = np.real(np.fft.fft(y))
    c = np.sqrt(2.0/(1.0*n))*w[0:n]
    c[0] = c[0]/np.sqrt(2.0)
    return c


def dct_iii(x):
    '''Variant of dct - wavelab'''
    n = len(x)
    x[0] = x[0]/np.sqrt(2.0)
    y = np.concatenate((x,np.zeros(3*n)))
    w = np.real(np.fft.fft(y))
    c = np.sqrt(2.0/(1.0*n))*w[1:2*n:2]
    return c


def WindowMeyer(xi,deg):
    ''' xi  - abscissa values for window evaluation
       deg  - degree of the polynomail. 1<=deg<=3'''
# Commented out because we use only deg = 3. For speed.
#       nu = zeros(len(xi))
#       if deg==0:
#               nu = xi
#       elif deg==1:
#               temp = xi*xi
#               nu = temp*(3-2*xi)
#       elif deg==2:
#               temp = xi*xi
#               temp1 = xi*temp
#               nu = temp1*(10-15*xi+6*temp)
#       elif deg==3:
    x = np.clip(xi,0.0,1.0)
    pl = np.array([-20.0,70.0,-84.0,35.0])
    
    nu = np.polyval(pl,x)*np.power(x,4)

    return nu

#############End of Utility functions###################


#############Functions for the Forward Transform########


def FoldMeyer(x,sympts,polarity,window,deg):
    ''' x           - signal vector in frequency domain (length=2^J)
        sympts      - symmetry points of the form [a,b]
        polarity    - string selection for folding polarity
        window      - string selecting window
        deg         - degree of Meyer window'''
    pio2 = np.pi/2
    if window in ('m','M'):
        eps  = np.floor(sympts[0]/3.0)
        epsp = sympts[0] - eps - 1
        lftind = np.arange(sympts[0]-eps,sympts[0],dtype=np.int)
        lmidind = np.arange(sympts[0]+1,sympts[0]+eps+1,dtype=np.int)
        rmidind = np.arange(sympts[1]-epsp,sympts[1],dtype=np.int)
        rghtind = np.arange(sympts[1]+1,sympts[1]+epsp+1,dtype=np.int)
        wind = WindowMeyer(3.0*(lftind/(1.0*sympts[1]))-1,deg)
        lft = x[lftind]*np.sin(pio2*wind)
        wind = WindowMeyer(3.0*(lmidind/(1.0*sympts[1]))-1,deg)
        lmid = x[lmidind]*np.sin(pio2*wind)
        wind = WindowMeyer(1.5*(rmidind/(1.0*sympts[1]))-1,deg)
        rmid = x[rmidind]*np.cos(pio2*wind)
        wind = WindowMeyer(1.5*(rghtind/(1.0*sympts[1]))-1,deg)
        rght = x[rghtind]*np.cos(pio2*wind)
    elif window in ('f','F'):
        n = len(x)
        eps = np.floor(sympts[1]/3.0)
        lftind = np.arange(n+sympts[0]-eps,n+sympts[0],dtype=np.int)
        lmidind = np.arange(n+sympts[0]+1,n+sympts[0]+eps+1,dtype=np.int)
        cntrind = np.concatenate((np.arange(n+sympts[0]+eps+1,n,dtype=np.int),
            np.arange(sympts[1]-eps,dtype=np.int)))
        rmidind = np.arange(sympts[1]-eps,sympts[1],dtype=np.int)
        rghtind = np.arange(sympts[1]+1,sympts[1]+eps+1,dtype=np.int)
        wind = WindowMeyer(3.0*abs((lftind-n)/(2.0*sympts[1]))-1,deg)
        lft = x[lftind]*np.cos(pio2*wind)
        wind = WindowMeyer(3.0*abs((lmidind-n)/(2.0*sympts[1]))-1,deg)
        lmid = x[lmidind]*np.cos(pio2*wind)
        cntr = x[cntrind]
        wind = WindowMeyer(3.0*rmidind/(2.0*sympts[1])-1,deg)
        rmid = x[rmidind]*np.cos(pio2*wind)
        wind = WindowMeyer(3.0*rghtind/(2.0*sympts[1])-1,deg)
        rght = x[rghtind]*np.cos(pio2*wind)
    elif window in ('t','T'):
        eps = np.floor(sympts[0]/3.0)
        epsp = sympts[0]-eps-1
        lftind = np.arange(sympts[0]-eps,sympts[0],dtype=np.int)
        lmidind = np.arange(sympts[0]+1,sympts[0]+eps+1,dtype=np.int)
        rmidind = np.arange(sympts[1]-epsp,sympts[1],dtype=np.int)
        wind = WindowMeyer(3.0*lftind/(1.0*sympts[1]) - 1,deg)
        lft = x[lftind]*np.sin(pio2*wind)
        wind = WindowMeyer(3.0*lmidind/(1.0*sympts[1]) - 1,deg)
        lmid = x[lmidind]*np.sin(pio2*wind)
        rmid = x[rmidind]
        rght = np.zeros(len(rmidind))
    else:
        logger.error('Cannot interpret window Flag')
        sys.exit(1)


    if polarity in ('mp','MP'):
        x1 = np.concatenate((-lft[::-1],rght[::-1],[0]))
        x2 = np.concatenate((lmid,rmid,[x[sympts[1]]]))
    elif polarity in ('pm','PM'):
        x1 = np.concatenate(([0],lft[::-1],-rght[::-1]))
        x2 = np.concatenate(([x[sympts[0]]],lmid,rmid))
    elif polarity in ('pp','PP'):
        x1 = np.concatenate(([x[n+sympts[0]]],lmid,cntr,rmid,
            [x[sympts[1]]]))
        x2 = np.concatenate(([0],lft[::-1],np.zeros(len(cntrind)),
            rght[::-1],[0]))
    elif polarity in ('mm','MM'):
        x1 = np.concatenate((lmid,cntr,rmid))
        x2 = np.concatenate((-lft[::-1],np.zeros(len(cntrind)),-rght[::-1]))
    else:
        logger.error('Cannot interpret polarity Flag')
        sys.exit(1)

    fldx = x1+x2
    return fldx


def CombineCoeff(rtrig,itrig,window,n):
    ''' rtrig       - Trig coeffs of projection of real part
        itrig       - Trig coeffs of projection of imag part
        window      - String selection window for projection
        n           - Length of original signal'''

    ln = len(rtrig)

    if window in ('m','M','t','T'):
        wcoefs = np.concatenate((rtrig+itrig,itrig[::-1]-rtrig[::-1]))
        wcoefs = pow_1(np.arange(1,2*ln+1))*wcoefs/(1.0*n)
    elif window in ('f','F'):
        wcoefs = np.zeros(2*(ln-1))
        wcoefs[0] = rtrig[0]*np.sqrt(2.0)
        wcoefs[1:] = np.concatenate((rtrig[1:]-itrig,rtrig[ln-2:0:-1]
            +itrig[ln-3::-1]))
        wcoefs = pow_1(np.arange(2*ln-2))*wcoefs/(np.sqrt(2.0)*n)
    else:
        logger.error('Cannot interpret window flag.')
        sys.exit(1)

    return wcoefs


def CoarseMeyerCoeff(fhat,C,n,deg):
    ''' fhat        FFT of signal vector, dyadic length
        C           coarse resolution level
        n           length of signal vector
        deg         degree of Meyer window'''

    lendp = - (2**(C-1))
    rendp = (2**(C-1))
    rfh = np.real(fhat)
    ifh = np.imag(fhat)

    fldx = FoldMeyer(rfh,(lendp,rendp),'pp','f',deg)
    rtrigcoefs = quasi_dct(fldx,'f')

    fldx = FoldMeyer(ifh,(lendp,rendp),'mm','f',deg)
    itrigcoefs = QuasiDST(fldx,'f')

    beta = CombineCoeff(rtrigcoefs,itrigcoefs,'f',n)
    return beta

def DetailMeyerCoeff(fhat,j,n,deg):
    ''' fhat         FFT of signal vector, dyadic length
        C            coarse resolution level
        n            length of signal vector
        deg          degree of Meyer window'''

    lendp = 2**(j-1)
    rendp = 2**j
    rfh = np.real(fhat)
    ifh = np.imag(fhat)

    fldx = FoldMeyer(rfh,(lendp,rendp),'mp','m',deg)
    rtrigcoefs = dst_iii(fldx)

    fldx = FoldMeyer(ifh,(lendp,rendp),'pm','m',deg)
    itrigcoefs = dct_iii(fldx)

    beta = CombineCoeff(rtrigcoefs,itrigcoefs,'m',n)
    return beta


def FineMeyerCoeff(fhat,n,deg):
    ''' fhat         FFT of signal vector, dyadic length
        n            length of signal vector
        deg          degree of Meyer window'''
    J = np.log2(n)
    lendp = 2**(J-2)
    rendp = 2**(J-1)
    rfh = np.real(fhat)
    ifh = np.imag(fhat)

    fldx = FoldMeyer(rfh,(lendp,rendp),'mp','t',deg)
    fldx[-1] = fldx[-1]/np.sqrt(2.0)
    rtrig = dst_iii(fldx)

    fldx = FoldMeyer(ifh,(lendp,rendp),'pm','t',deg)
    itrig = dct_iii(fldx)

    falpha = CombineCoeff(rtrig,itrig,'t',n)
    return falpha


def fwt2_ym(xinp,deg,L):
    ''' Forward Wavelet Transform of Square Image
        x           2-d signal; size(x) = [2^J,2^J]
        deg         degree of polynomial window 2 <= deg <= 4
        L           Coarse Level for V_0; L << J'''
    if (L<3):
        logger.error('L must be >= 3')
        sys.exit(1)

    nn = xinp.shape[0]
    w = np.zeros((nn,nn))
    x = np.flipud(xinp)
    J = np.log2(nn)
    powL2 = 2**L

    #Horizontal Transform
    cr = np.zeros((nn,powL2))
    fx = np.fft.fft(x,axis=-1)     #Fourier transform in X-direction (Const).

    for m in xrange(nn):
        cr[m,:] = CoarseMeyerCoeff(fx[m,:],L,nn,deg)
    
    
    #Vertical Transform
    crc = np.zeros((powL2,powL2))
    y = np.fft.fft(cr,axis=0)
    for m in xrange(powL2):
        crc[:,m] = CoarseMeyerCoeff(y[:,m],L,nn,deg)

    w[0:powL2,0:powL2] = np.flipud(crc)

    for j in xrange(L,np.int_(J-1)):
        pow2j = 2**j
        if j==L :
            dr = cr
        else:
            dr = np.zeros((nn,pow2j))
            for m in xrange(nn):
                dr[m,:] = CoarseMeyerCoeff(fx[m,:],j,nn,deg)

            y = np.fft.fft(dr,axis=0)

        drc = np.zeros((pow2j,pow2j))
        for m in xrange(pow2j):
            drc[:,m] = DetailMeyerCoeff(y[:,m],j,nn,deg)

        #Quadrant 2
        w[0:pow2j,pow2j:2*pow2j] = np.flipud(drc)

        for m in xrange(nn):
            dr[m,:] = DetailMeyerCoeff(fx[m,:],j,nn,deg)

        y = np.fft.fft(dr,axis=0)
        for m in xrange(pow2j):
            drc[:,m] = CoarseMeyerCoeff(y[:,m],j,nn,deg)

        #Quadrant 3
        w[pow2j:pow2j*2,0:pow2j] = np.flipud(drc)

        for m in xrange(pow2j):
            drc[:,m] = DetailMeyerCoeff(y[:,m],j,nn,deg)

        #Quadrant 4
        w[pow2j:2*pow2j,pow2j:2*pow2j] = np.flipud(drc)


    pow2j =np.int_(2**(J-1))

    dr = np.zeros((nn,pow2j))
    for m in xrange(nn):
        dr[m,:] = CoarseMeyerCoeff(fx[m,:],(J-1),nn,deg)

    drc = np.zeros((pow2j,pow2j))
    y = np.fft.fft(dr,axis=0)
    for m in xrange(pow2j):
        drc[:,m] = FineMeyerCoeff(y[:,m],nn,deg)

    #Quadrant 2
    w[0:pow2j,pow2j:pow2j*2] = np.flipud(drc)

    for m in xrange(nn):
        dr[m,:] = FineMeyerCoeff(fx[m,:],nn,deg)

    y = np.fft.fft(dr,axis=0)
    for m in xrange(pow2j):
        drc[:,m] = CoarseMeyerCoeff(y[:,m],J-1,nn,deg)

    #Quadrant 3
    w[pow2j:2*pow2j,0:pow2j] = np.flipud(drc)

    for m in xrange(pow2j):
        drc[:,m] = FineMeyerCoeff(y[:,m],nn,deg)

    w[pow2j:pow2j*2,pow2j:2*pow2j] = np.flipud(drc)

    w = nn*w

    return w

############End of functions for the forward transform ################


###########Functions for the inverse transform ########################

def ExtendProj(proj,n,window,sympts,sym):
    ''' proj        - Windowed projection vector
        n           - Length of full signal
        window      - String selecting window
        sympts      - points of symmetry and assymetry
        sym         - symmetry type'''

    if window in ('m','M'):
        nj = sympts[1]
        frontlen = (nj/4) + np.floor(nj/12.0)+1
        backlen = max(((n/2) - (nj+np.floor(nj/3.0)),0))
        pospart = np.concatenate((np.zeros(frontlen),proj,np.zeros(backlen)))
    elif window in ('f','F'):
        frontind = np.arange((len(proj)+1)/2 -1,len(proj),dtype=np.int32)
        backlen = n/2 + 1 - len(frontind)
        pospart = np.concatenate((proj[frontind],np.zeros(backlen)))
    elif window in ('t','T'):
        nj1 = sympts[0]
        frontlen = np.max(((n/2 - (nj1+np.floor(nj1/3.0))),0))
        pospart = np.concatenate((np.zeros(frontlen),proj))
    else:
        logger.error('Window type undefined in ExtendProj')
        sys.exit(1)

    ind = pospart[np.arange(1,n/2)]
    if sym in ('e','E'):
        extproj = np.concatenate((pospart,ind[::-1]))
    elif sym in ('o','O'):
        extproj = np.concatenate((pospart,-ind[::-1]))
    else:
        logger.error('Symmetry type undefined in ExtendProj')
        sys.exit(1)

    return extproj


def UnfoldMeyer(x,sympts,polarity,window,deg):
    ''' fldx        - Folded version of signal (length=2^J)
        sympts      - symmetry points of the form [a,b]
        polarity    - string selection for folding polarity
        window      - string selecting window
        deg         - degree of Meyer window'''
    pio2 = np.pi/2
    if window in ('m','M'):
        eps  = np.floor(sympts[0]/3.0)
        epsp = sympts[0] - eps - 1
        if polarity in ('mp','MP'):
            xi = np.arange(sympts[0]+1,sympts[1]+1)/(1.0*sympts[1])
            wind = WindowMeyer(3*xi[0:eps]-1,deg)
            lft = x[0:eps]*np.cos(pio2*wind)
            lmid =x[0:eps]*np.sin(pio2*wind)
            wind = WindowMeyer(1.5*xi[eps:eps+epsp]-1,deg)
            rmid = x[eps:eps+epsp]*np.cos(pio2*wind)
            rght =x[eps:eps+epsp]*np.sin(pio2*wind)
            epst = len(lmid)+len(rmid)+len(lft)
            unfldx = np.concatenate((-lft[::-1],[0],lmid,rmid,
                [x[sympts[0]-1]],rght[::-1]))
            
        elif polarity in ('pm','PM'):
            xi = np.arange(sympts[0],sympts[1])/(1.0*sympts[1])
            wind = WindowMeyer(3*xi[1:eps+1]-1,deg)
            lft = x[1:eps+1]*np.cos(pio2*wind)
            lmid = x[1:eps+1]*np.sin(pio2*wind)
            wind = WindowMeyer(1.5*xi[eps+1:eps+epsp+1]-1,deg)
            rmid = x[eps+1:eps+epsp+1]*np.cos(pio2*wind)
            rght = x[eps+1:eps+epsp+1]*np.sin(pio2*wind)
            epst = len(lft)+len(lmid)+len(rmid)
            
            unfldx=np.concatenate((lft[::-1],[x[0]],lmid,rmid,[0],-rght[::-1]))

        else:
            logger.error('Undefined polarity in UnfoldMeyer')
            sys.exit(1)

    elif window in ('f','F'):
        n = len(x)
        eps = np.floor(sympts[1]/3.0)
        innerx = np.arange(sympts[1]-eps,sympts[1])/(2.0*sympts[1])
        outerx = np.arange(sympts[1]+1,sympts[1]+eps+1)/(2.0*sympts[1])
        if polarity in ('pp','PP'):
            wind = WindowMeyer(3*outerx[::-1]-1,deg)
            lft = x[eps:0:-1]*np.cos(pio2*wind)
            wind = WindowMeyer(3*outerx-1,deg)
            rght = x[2*sympts[1]-1:2*sympts[1]-eps-1:-1]*np.cos(pio2*wind)
            wind = WindowMeyer(3*innerx[::-1]-1,deg)
            lmid = x[1:eps+1]*np.cos(pio2*wind)
            wind = WindowMeyer(3*innerx-1,deg)
            rmid = x[2*sympts[1]-eps:2*sympts[1]]*np.cos(pio2*wind)
            epst = len(lft)-1-2*eps+2*sympts[1]+len(lmid)+len(rmid)
            unfldx = np.concatenate((lft,[x[0]],
                lmid,x[1+eps:2*sympts[1]-eps],rmid,[x[2*sympts[1]]],rght))
                       
        elif polarity in ('mm','MM'):
            wind = WindowMeyer(3*outerx[::-1]-1,deg)
            lft = x[eps-1::-1]*np.cos(pio2*wind)
            wind = WindowMeyer(3*outerx-1,deg)
            rght = x[2*sympts[1]-2:2*sympts[1]-eps-2:-1]*np.cos(pio2*wind)
            wind = WindowMeyer(3*innerx[::-1]-1,deg)
            lmid = x[0:eps]*np.cos(pio2*wind)
            wind = WindowMeyer(3*innerx-1,deg)
            rmid = x[2*sympts[1]-eps-1:2*sympts[1]-1]*np.cos(pio2*wind)
            epst = len(lmid)+len(rmid)+len(lft)+2*sympts[1]-2*eps-1
            
            unfldx = np.concatenate((-lft,[0],lmid,
                x[eps:2*sympts[1]-eps-1],rmid,[0],-rght))

        else:
            logger.error('Undefined polarity in UnfoldMeyer')
            sys.exit(1)

    elif window in ('t','T'):
        eps = np.floor(sympts[0]/3.0)
        epsp = sympts[0]-eps-1
        if polarity in ('mp','MP'):
            xi = np.arange(sympts[0]+1,sympts[1]+1)/(1.0*sympts[1])
            wind = WindowMeyer(3*xi[0:eps]-1,deg)
            lft = x[0:eps]*np.cos(pio2*wind)
            lmid = x[0:eps]*np.sin(pio2*wind)
            rmid = x[eps:eps+epsp]
            epst = len(lft)+len(lmid)+len(rmid)
            unfldx = np.concatenate((-lft[::-1],[0],lmid,
                rmid,[np.sqrt(2.0)*x[eps+epsp]]))
            
        elif polarity in ('pm','PM'):
            xi = np.arange(sympts[0],sympts[1])/(1.0*sympts[1])
            wind = WindowMeyer(3*xi[1:eps+1]-1,deg)
            lft = x[1:eps+1]*np.cos(pio2*wind)
            lmid = x[1:eps+1]*np.sin(pio2*wind)
            rmid = x[eps+1:eps+epsp+1]
            epst = len(lft)+len(lmid)+len(rmid)
            unfldx = np.concatenate((lft[::-1],[x[0]],lmid,rmid,[0]))
            
        else:
            logger.error('Undefined polarity in UnfoldMeyer')
            sys.exit(1)

    else:
        logger.error('Cannot interpret window Flag')
        sys.exit(1)


    return unfldx


def SeparateCoeff(wcoefs,window):
    ''' wcoefs      - Wavelet coeffs at a given level
       window       - Window selecting string'''

    nj = len(wcoefs)
    nj1 = nj/2

    if window in ('m','M'):
        ind1 = np.arange(nj1)
        rtrig = pow_1(1+ind1)*(wcoefs[ind1] + wcoefs[nj-1:nj1-1:-1])/2.0
        itrig = pow_1(1+ind1)*(wcoefs[ind1] - wcoefs[nj-1:nj1-1:-1])/2.0
    elif window in ('f','F'):
        ind1 = np.arange(nj-1)+1
        rtrig = np.zeros(len(ind1)+1)
        rtrig[1:]= pow_1(ind1)*(wcoefs[ind1] + wcoefs[nj-1:0:-1])/np.sqrt(2.0)
        rtrig[0] = wcoefs[0]*2
        itrig = pow_1(ind1+1)*(wcoefs[ind1]-wcoefs[nj-1:0:-1])/np.sqrt(2.0)
    elif window in ('t','T'):
        ind1 = np.arange(nj1)
        rtrig = pow_1(ind1+1)*(wcoefs[ind1]+wcoefs[nj-1:nj1-1:-1])/2.0
        itrig = pow_1(ind1+1)*(wcoefs[ind1]-wcoefs[nj-1:nj1-1:-1])/2.0
    else:
        'Window string in SeparateCoeff unclear'
        sys.exit(1)

    return rtrig,itrig


def CoarseMeyerProj(beta,C,n,deg):
    ''' beta         Father Meyer Coeffs, dyadic length
        C            coarse resolution level
        n           length of signal vector
        deg          degree of Meyer window'''

    lendp = - (2**(C-1))
    rendp = (2**(C-1))

    rtrig,itrig = SeparateCoeff(beta,'f')

    rtrigrec = quasi_dct(rtrig,'i')
    unflde   = UnfoldMeyer(rtrigrec,(lendp,rendp),'pp','f',deg)
    eextproj = ExtendProj(unflde,n,'f',(lendp,rendp),'e')
    
    itrigrec = QuasiDST(itrig,'i')
    unfldo   = UnfoldMeyer(itrigrec,(lendp,rendp),'mm','f',deg)
    oextproj = ExtendProj(unfldo,n,'f',(lendp,rendp),'o')

    cpjf = (eextproj + (1j)*oextproj)*0.5

    return cpjf


def DetailMeyerProj(alpha,k,n,deg):
    ''' alpha        Meyer Coeffs, dyadic length
        k            resolution level
        n            length of signal vector
        deg          degree of Meyer window'''

    lendp = (2**(k-1))
    rendp = (2**k)

    rtrig,itrig = SeparateCoeff(alpha,'m')

    rtrigrec = dst_ii(rtrig)
    unflde   = UnfoldMeyer(rtrigrec,(lendp,rendp),'mp','m',deg)
    eextproj = ExtendProj(unflde,n,'m',(lendp,rendp),'e')

    itrigrec = dct_ii(itrig)
    unfldo   = UnfoldMeyer(itrigrec,(lendp,rendp),'pm','m',deg)
    oextproj = ExtendProj(unfldo,n,'m',(lendp,rendp),'o')
    dpjf = (eextproj + (1j)*oextproj)

    return dpjf


def FineMeyerProj(alpha,k,n,deg):
    ''' alpha        Meyer Coeffs, dyadic length
        k            resolution level
        n            length of signal vector
        deg          degree of Meyer window'''

    lendp = (2**(k-1))
    rendp = (2**k)

    rtrig,itrig = SeparateCoeff(alpha,'t')

    rtrigrec = dst_ii(rtrig)
    unflde   = UnfoldMeyer(rtrigrec,(lendp,rendp),'mp','t',deg)
    eextproj = ExtendProj(unflde,n,'t',(lendp,rendp),'e')

    itrigrec = dct_ii(itrig)
    unfldo   = UnfoldMeyer(itrigrec,(lendp,rendp),'pm','t',deg)
    oextproj = ExtendProj(unfldo,n,'t',(lendp,rendp),'o')

    dpjf = (eextproj + (1j)*oextproj)

    return dpjf


def iwt2_ym(x,L,deg):
    '''Inverse 2D Wavelet Transform of a square image.
       x    2-d signal; size(x) = [2^J,2^J]
       deg  degree of polynomial window 2 <= deg <= 4
       L    Coarse Level for V_0; L << J '''
    if (L<3):
        logger.error('L must be >= 3')
        sys.exit(1)

    nn = x.shape[0]
    ymat = np.zeros((nn,nn))
    J = np.log2(nn)
    powL2 = 2**L

    crc = np.flipud(x[0:powL2,0:powL2])
    cr = np.zeros((nn,powL2))

    #Quadrant 1. Coarse.
    for m in xrange(powL2):
        w = CoarseMeyerProj(crc[:,m],L,nn,deg)
        y = np.real(np.fft.ifft(w))
        cr[:,m] = y

    for m in xrange(nn):
        w = CoarseMeyerProj(cr[m,:],L,nn,deg)
        ymat[m,:] = np.real(np.fft.ifft(w))

    for j in xrange(L,np.int_(J-1)):
        pow2j = 2**j

        #Quadrant 2. Horizontal.
        drc =np.flipud(x[0:pow2j,pow2j:2*pow2j])
        dr = np.zeros((nn,pow2j))

        for m in xrange(pow2j):
            w = DetailMeyerProj(drc[:,m],j,nn,deg)
            dr[:,m] = np.real(np.fft.ifft(w))

        for m in xrange(nn):
            w  = CoarseMeyerProj(dr[m,:],j,nn,deg)
            ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

        #Quadrant 3. Vertical.
        drc = np.flipud(x[pow2j:2*pow2j,0:pow2j])
        for m in xrange(pow2j):
            w = CoarseMeyerProj(drc[:,m],j,nn,deg)
            dr[:,m] = np.real(np.fft.ifft(w))


        for m in xrange(nn):
            w = DetailMeyerProj(dr[m,:],j,nn,deg)
            ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

        #Quadrant 4. Diagonal.
        drc = np.flipud(x[pow2j:2*pow2j,pow2j:2*pow2j])

        for m in xrange(pow2j):
            w = DetailMeyerProj(drc[:,m],j,nn,deg)
            dr[:,m] = np.real(np.fft.ifft(w))

        for m in xrange(nn):
            w = DetailMeyerProj(dr[m,:],j,nn,deg)
            ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))



    pow2j = np.int_(2**(J-1))

    # Quadrant 2.Horizontal.
    drc = np.flipud(x[0:pow2j,pow2j:2*pow2j])
    dr = np.zeros((nn,pow2j))
    for m in xrange(pow2j):
        w = FineMeyerProj(drc[:,m],J-1,nn,deg)
        dr[:,m] = np.real(np.fft.ifft(w))

    for m in xrange(nn):
        w = CoarseMeyerProj(dr[m,:],J-1,nn,deg)
        ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

    #Quadrant 3.Vertical.
    drc = np.flipud(x[pow2j:2*pow2j,0:pow2j])
    for m in xrange(pow2j):
        w = CoarseMeyerProj(drc[:,m],J-1,nn,deg)
        dr[:,m] = np.real(np.fft.ifft(w))

    for m in xrange(nn):
        w = FineMeyerProj(dr[m,:],J-1,nn,deg)
        ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

    #Quadrant 4. Diagonal.
    drc = np.flipud(x[pow2j:2*pow2j,pow2j:2*pow2j])
    for m in xrange(pow2j):
        w = FineMeyerProj(drc[:,m],J-1,nn,deg)
        dr[:,m] = np.real(np.fft.ifft(w))

    for m in xrange(nn):
        w = FineMeyerProj(dr[m,:],J-1,nn,deg)
        ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))


    ymat = nn*np.flipud(ymat)
    return ymat

##########End of inverse transform functions############



#########My functions for Mints#########################
def fwt2_meyer(xinp,deg,L):
    ''' Forward 2D wavelet transform of rectangular image.
       x    2-d signal; size(x) = [2^J,2^K]
       deg  degree of polynomial window 2 <= deg <= 4
       L    Coarse Level for V_0; L << K < J
       Designed for multiple frames stitched together.'''
    if (L<3):
        logger.error('L must be >= 3')
        sys.exit(1)

    nn = xinp.shape[0]
    mm = xinp.shape[1]
    w = np.zeros((nn,mm))

    x = np.flipud(xinp)

    K = np.log2(nn)
    J = np.log2(mm)

    dR = K-J
    R = np.int_(L+dR)       #Matching levels to J
    powL2 = 2**L
    powR2 = 2**R

    #Horizontal Transform
    cr = np.zeros((nn,powL2))
    fx = np.fft.fft(x,axis=-1)     #Fourier transform in X-direction (Const).
    for m in xrange(nn):
        cr[m,:] = CoarseMeyerCoeff(fx[m,:],L,mm,deg)  #From nn to mm

    #Vertical Transform
    crc = np.zeros((powR2,powL2))     ####From L2 to R2
    y = np.fft.fft(cr,axis=0)
    for m in xrange(powL2):
        crc[:,m] = CoarseMeyerCoeff(y[:,m],R,nn,deg) #J to R

    w[0:powR2,0:powL2] = np.flipud(crc)

    for j in xrange(L,np.int_(J-1)):
        r = j+dR
        pow2j = 2**j
        pow2r = 2**(j+dR)

        if j==L :
            dr = cr
        else:
            # Horizontal again
            dr = np.zeros((nn,pow2j))
            for m in xrange(nn):
                dr[m,:] = CoarseMeyerCoeff(fx[m,:],j,mm,deg) #nn to mm

            y = np.fft.fft(dr,axis=0)

        #Vertical
        drc = np.zeros((pow2r,pow2j))  #pow2j to pow2r
        for m in xrange(pow2j):
            drc[:,m] = DetailMeyerCoeff(y[:,m],r,nn,deg) #j to r

        #Quadrant 2
        w[0:pow2r,pow2j:2*pow2j] = np.flipud(drc)    #pow2j to pow2r

        #Horizontal
        for m in xrange(nn):
            dr[m,:] = DetailMeyerCoeff(fx[m,:],j,mm,deg)  #nn to mm

        #Vertical
        y = np.fft.fft(dr,axis=0)
        for m in xrange(pow2j):
            drc[:,m] = CoarseMeyerCoeff(y[:,m],r,nn,deg)  #j to r

        #Quadrant 3
        w[pow2r:pow2r*2,0:pow2j] = np.flipud(drc)   #pow2j to pow2r

        #Vertical
        for m in xrange(pow2j):
            drc[:,m] = DetailMeyerCoeff(y[:,m],r,nn,deg) #j to r

        #Quadrant 4
        w[pow2r:2*pow2r,pow2j:2*pow2j] = np.flipud(drc)   #pow2j to pow2r


    pow2j = np.int_(2**(J-1))
    pow2r = np.int_(2**(K-1))

    dr = np.zeros((nn,pow2j))

    #Horizontal
    for m in xrange(nn):
        dr[m,:] = CoarseMeyerCoeff(fx[m,:],(J-1),mm,deg)  #nn to mm

    drc = np.zeros((pow2r,pow2j))   #pow2j to pow2r

    #Vertical
    y = np.fft.fft(dr,axis=0)
    for m in xrange(pow2j):
        drc[:,m] = FineMeyerCoeff(y[:,m],nn,deg)

    #Quadrant 2
    w[0:pow2r,pow2j:pow2j*2] = np.flipud(drc)    #pow2j to pow2r

    #Horizontal
    for m in xrange(nn):
        dr[m,:] = FineMeyerCoeff(fx[m,:],mm,deg)   #nn to mm

    #Vertical
    y = np.fft.fft(dr,axis=0)
    for m in xrange(pow2j):
        drc[:,m] = CoarseMeyerCoeff(y[:,m],K-1,nn,deg) # J to K

    #Quadrant 3
    w[pow2r:2*pow2r,0:pow2j] = np.flipud(drc)

    #Vertical
    for m in xrange(pow2j):
        drc[:,m] = FineMeyerCoeff(y[:,m],nn,deg)

    w[pow2r:pow2r*2,pow2j:2*pow2j] = np.flipud(drc)    #j to r

    w = np.sqrt(nn*mm)*w

    return w



def iwt2_meyer(x,L,deg):
    ''' Inverse 2D Wavelet Transform of rectangular image.
       x    2-d signal; size(x) = [2^K,2^J]
       deg  degree of polynomial window 2 <= deg <= 4
       L    Coarse Level for V_0; L << J < K
       This has been designed to handle multiple frames stitched together.'''
    if (L<3):
        logger.error('L must be >= 3')
        sys.exit(1)

    nn = x.shape[0]
    mm = x.shape[1]
    ymat = np.zeros((nn,mm))
    J = np.log2(mm)
    K = np.log2(nn)
    dR = np.int(K-J)
    R = L+dR
    powL2 = 2**L
    powR2 = 2**R

    crc = np.flipud(x[0:powR2,0:powL2])     #powL2 to powR2
    w = np.zeros((nn,powL2),dtype=np.complex)

    #Quadrant 1. Coarse.
    #Vertical.
    for m in xrange(powL2):
        w[:,m] = CoarseMeyerProj(crc[:,m],R,nn,deg)   #L to R
    
    cr = np.real(np.fft.ifft(w,axis=0))

    w = np.zeros((nn,mm))
    #Horizontal
    for m in xrange(nn):
        w = CoarseMeyerProj(cr[m,:],L,mm,deg)    #nn to mm
        ymat[m,:] = np.real(np.fft.ifft(w))

    for j in xrange(L,np.int(J-1)):
        r = np.int(j+dR)
        pow2j = 2**j
        pow2r = 2**r

        #Quadrant 2. Horizontal.
        drc =np.flipud(x[0:pow2r,pow2j:2*pow2j])   #pow2j to pow2r
        dr = np.zeros((nn,pow2j))

        #Vertical
        for m in xrange(pow2j):
            w = DetailMeyerProj(drc[:,m],r,nn,deg)  #j to r
            dr[:,m] = np.real(np.fft.ifft(w))

        #Horizontal
        for m in xrange(nn):
            w  = CoarseMeyerProj(dr[m,:],j,mm,deg)  #nn to mm
            ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

        #Quadrant 3. Vertical.
        drc = np.flipud(x[pow2r:2*pow2r,0:pow2j])     #pow2j to pow2r
        for m in xrange(pow2j):
            w = CoarseMeyerProj(drc[:,m],r,nn,deg)  #j to r
            dr[:,m] = np.real(np.fft.ifft(w))

        #Horizontal
        for m in xrange(nn):
            w = DetailMeyerProj(dr[m,:],j,mm,deg)  #nn to mm
            ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

        #Quadrant 4. Diagonal.
        drc = np.flipud(x[pow2r:2*pow2r,pow2j:2*pow2j])  #pow2j to pow2r

        #Vertical
        for m in xrange(pow2j):
            w = DetailMeyerProj(drc[:,m],r,nn,deg) #j to r
            dr[:,m] = np.real(np.fft.ifft(w))

        #Horizontal
        for m in xrange(nn):
            w = DetailMeyerProj(dr[m,:],j,mm,deg)   #nn to mm
            ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))



    pow2j = np.int_(2**(J-1))
    pow2r = np.int_(2**(K-1))

    # Quadrant 2.Horizontal.
    drc = np.flipud(x[0:pow2r,pow2j:2*pow2j])
    dr = np.zeros((nn,pow2j))
    #Vertical
    for m in xrange(pow2j):
        w = FineMeyerProj(drc[:,m],K-1,nn,deg)   #J to K
        dr[:,m] = np.real(np.fft.ifft(w))

    #Horizontal
    for m in xrange(nn):
        w = CoarseMeyerProj(dr[m,:],J-1,mm,deg)  #nn to mm
        ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

    #Quadrant 3.Vertical.
    drc = np.flipud(x[pow2r:2*pow2r,0:pow2j])
    #Vertical
    for m in xrange(pow2j):
        w = CoarseMeyerProj(drc[:,m],K-1,nn,deg)  #J to K
        dr[:,m] = np.real(np.fft.ifft(w))

    #Horizontal
    for m in xrange(nn):
        w = FineMeyerProj(dr[m,:],J-1,mm,deg)    #nn to mm
        ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))

    #Quadrant 4. Diagonal.
    drc = np.flipud(x[pow2r:2*pow2r,pow2j:2*pow2j])

    #Vertical
    for m in xrange(pow2j):
        w = FineMeyerProj(drc[:,m],K-1,nn,deg)  #J to K
        dr[:,m] = np.real(np.fft.ifft(w))

    #Horizontal
    for m in xrange(nn):
        w = FineMeyerProj(dr[m,:],J-1,mm,deg) #nn to mm
        ymat[m,:] = ymat[m,:] + np.real(np.fft.ifft(w))


    ymat = np.sqrt(nn*mm)*np.flipud(ymat)
    return ymat


def  get_corners(dims,j,quad):
    ''' Get the 4 corners of the rectangular wavelet coefficient matrix.
       dims         -  The dimensions of the rectangular problem.
       j            -  Scale one is interested in. (>=3). Reference to column
       Quadrant     -  1(Vcoarse,Hcoarse), 2 (VcoarseHfine), 3 (VfineHcoarse), 4(Vfine,Hfine)
       We also assume that we are dealing with long rectangles/squares.'''
    nn = dims[0]
    mm = dims[1]
    dR = np.int_(np.log2(nn/mm))
    r = j+dR
    p2j = 2**j
    p2r = 2**r
    ii = np.zeros(2,dtype=np.int)
    jj = np.zeros(2,dtype=np.int)
    if quad==1:
        ii[0] = 0
        jj[0] = 0
        ii[1] = p2r
        jj[1] = p2j
    elif quad==2:
        ii[0] = 0       #Quadrant 2
        ii[1] = p2r
        jj[0] = p2j
        jj[1] = 2*p2j
    elif quad==3:
        ii[0] = p2r
        ii[1] = 2*p2r
        jj[0] = 0
        jj[1] = p2j
    elif quad==4:
        ii[0] = p2r
        ii[1] = 2*p2r
        jj[0] = p2j
        jj[1] = 2*p2j

    return ii,jj

###########################Optimized impulse response computation############
####### Faster more efficient.
####### Uses 1D transforms.

def impulse_resp(dims,fname):
    ''' Creates the impulse response for matrix of given dimensions.
        Output is stored in HDF5 file.
        Minimum size 32 x 32 pixels.'''
    nn = dims[0]
    mm = dims[1]
    K = np.int_(np.log2(nn))
    J = np.int_(np.log2(mm))
    dR = K-J
    p2dr = 2**dR


    f = h5py.File(fname,'w')    #Open HDF file for writing


    for k in xrange(3,J-1):
        logger.info('Processing scale: %d'%(k))
        p2k = 2**k
        p2r = p2k*p2dr
        numl = nn/p2r
        numw = mm/p2k
        cxname = 'Cx-%d'%(k)
        dxname = 'Dx-%d'%(k)
        cyname = 'Cy-%d'%(k)
        dyname = 'Dy-%d'%(k)

        yt = np.zeros((p2r,numl))
        ydt = np.zeros((p2r,numl))
        xt = np.zeros((p2k,numw))
        xdt = np.zeros((p2k,numw))

        
        for p in xrange(numl):
            y = np.zeros(nn)
            y[(nn/2)+p] = 1.0
            fy = np.fft.fft(y[::-1])
            yt[:,p] = CoarseMeyerCoeff(fy,k+dR,nn,3)
            ydt[:,p] = DetailMeyerCoeff(fy,k+dR,nn,3)
            
        for q in xrange(numw):
            x = np.zeros(mm)
            x[(mm/2)+q] = 1.0
            fx = np.fft.fft(x)
            xt[:,q] = CoarseMeyerCoeff(fx,k,mm,3)
            xdt[:,q] = DetailMeyerCoeff(fx,k,mm,3)


        xt=np.abs(xt)
        yt=np.flipud(np.abs(yt))
        xdt = np.abs(xdt)
        ydt = np.flipud(np.abs(ydt))
        f.create_dataset(cxname,data=xt)
        f.create_dataset(dxname,data=xdt)
        f.create_dataset(cyname,data=yt)
        f.create_dataset(dyname,data=ydt)

####Processing the last scale with Fine Coeffs
    k = J-1
    logger.info('Processing scale: %d'%(k))
    p2k = 2**k
    p2r = p2k*p2dr
    numl = nn/p2r
    numw = mm/p2k

    cxname = 'Cx-%d'%(k)
    dxname = 'Dx-%d'%(k)
    cyname = 'Cy-%d'%(k)
    dyname = 'Dy-%d'%(k)

    yt = np.zeros((p2r,numl))
    ydt = np.zeros((p2r,numl))
    xt = np.zeros((p2k,numw))
    xdt = np.zeros((p2k,numw))
    
    for p in xrange(numl):
        y = np.zeros(nn)
        y[(nn/2)+p] = 1.0
        fy = np.fft.fft(y[::-1])
        yt[:,p] = CoarseMeyerCoeff(fy,k+dR,nn,3)
        ydt[:,p] = FineMeyerCoeff(fy,nn,3)
        
    for q in xrange(numw):
        x = np.zeros(mm)
        x[(mm/2)+q] = 1.0
        fx = np.fft.fft(x)
        xt[:,q] = CoarseMeyerCoeff(fx,k,mm,3)
        xdt[:,q] = FineMeyerCoeff(fx,mm,3)    

    xt=np.abs(xt)
    yt=np.flipud(np.abs(yt))
    xdt = np.abs(xdt)
    ydt = np.flipud(np.abs(ydt))
    f.create_dataset(cxname,data=xt)
    f.create_dataset(dxname,data=xdt)
    f.create_dataset(cyname,data=yt)
    f.create_dataset(dyname,data=ydt)

    f.close()   #Close HDF file
    return

def CoeffWeight(b,rname):
    '''Compute the weight/reliability of coefficients.
       b     - [0/1] mask for pixels used in the dataset
       dims  - Dimensions of the dataset
       rname - RESP file for the dimensions of the dataset.'''

    nn = b.shape[0]
    mm = b.shape[1]
    J = np.int_(np.log2(mm))
    Wts = np.zeros((nn,mm))
    wmode = 'wrap'
    
    f = h5py.File(rname,'r')

    for m in range(3,J):
        p2m = 2**m
        p2r = p2m*(nn/mm)
        Numi = nn/p2r
        Numj = mm/p2m
        cxname = 'Cx-%d'%(m)
        dxname = 'Dx-%d'%(m)
        cyname = 'Cy-%d'%(m)
        dyname = 'Dy-%d'%(m)


        Cx = f[cxname].value
        Dx = f[dxname].value
        Cy = f[cyname].value
        Dy = f[dyname].value

        ####Quadrant 2
        [yy2,xx2] = get_corners((nn,mm),m,3)
        [yy3,xx3] = get_corners((nn,mm),m,2)
        [yy4,xx4] = get_corners((nn,mm),m,4)

        for p in xrange(Numi):
            for q in xrange(Numj):
                btemp=b[p::Numi,q::Numj]

                ind = p*Numj+q
                respy=convolve1d(btemp,Cy[:,p],axis=0,mode=wmode)
                respz=convolve1d(respy,Dx[:,q],axis=-1,mode=wmode)
                Wts[yy2[0]:yy2[1],xx2[0]:xx2[1]] += respz

                if m==3:
                    respz=convolve1d(respy,Cx[:,q],axis=-1,mode=wmode)
                    Wts[0:p2r,0:p2m] += respz

                respy=convolve1d(btemp,Dy[:,p],axis=0,mode=wmode)
                respz=convolve1d(respy,Cx[:,q],axis=-1,mode=wmode)
                Wts[yy3[0]:yy3[1],xx3[0]:xx3[1]] += respz

                respz=convolve1d(respy,Dx[:,q],axis=-1,mode=wmode)
                Wts[yy4[0]:yy4[1],xx4[0]:xx4[1]] += respz


    f.close()

    return Wts

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
