import numpy as np
import scipy.signal as ss
import matplotlib.pyplot as plt


def makeatmos(dims,scale=None):
    '''Simulates atmospheric phase screen with the exponential autocovariance function. We assume square pixels on the image and scale should be specified in number of pixels, e.g, if pixel spacing is 100m and we want a scale length of 1km, scale = 10. For now dims should be even numbers.
    
    Args:
        
        * dims      -> Array.shape
        * scale     -> Scaling length for atmosphere
        
    Returns:
        
        * atm       -> simulated phase screen'''

    if scale==None:
        raise ValueError('Scale not specified')

    Xsemi = dims[1]/2
    Ysemi = dims[0]/2

    Y = np.arange(dims[0])
    X = np.arange(dims[1])

    randx = np.random.rand(1)
    randy = np.random.rand(1)

    dist = np.sqrt((X[None,:]-Xsemi)**2 + (Y[:,None]-Ysemi)**2)
    expcov = np.exp(-dist/scale)

    ########Centering around zero
    expcov = np.fft.fftshift(expcov)

    ########Power spectral density
    expf = np.fft.fft2(expcov)

    ########Absolute value of spectrum
    expf = np.sqrt(np.abs(expf))
  
    phase = np.zeros(dims)


    ph = np.random.random((Ysemi,Xsemi))
    ph[0,0] = 0.0            ###For real value

    #####Quadrant 1
    phase[0:Ysemi,0:Xsemi] = ph

    #####Quadrant 2
    phase[0:Ysemi,Xsemi+1:] = -np.fliplr(ph[:,1:])
    phase[0:Ysemi,Xsemi] = np.random.rand(Ysemi)
    phase[0,Xsemi] = 0.0


    ####Quadrant 3
    phase[Ysemi+1:,0] = -np.flipud(ph[1:,0])
    phase[Ysemi+1:,1:Xsemi] = -np.flipud(np.fliplr(phase[1:Ysemi,Xsemi+1:]))
    phase[Ysemi,:Xsemi] = np.random.rand(Xsemi)
    phase[Ysemi,0] = 0.0

    ####Quadrant 4
    phase[Ysemi:,Xsemi:] = -np.flipud(np.fliplr(ph))
    phase[Ysemi+1:,Xsemi] =  - phase[1:Ysemi,Xsemi][::-1]
    phase[Ysemi,Xsemi+1:] = - phase[Ysemi,1:Xsemi][::-1]
    phase[Ysemi,Xsemi] = 0.

    phase = phase - phase.sum()/(1.0*dims[0]*dims[1]-4)
    phase[0,0] = 0.
    phase[0,Xsemi] = 0.
    phase[Ysemi,0] = 0.
    phase[Ysemi,Xsemi] = 0.


    cJ = np.complex(0.0,1.0)
    expf = expf * np.exp(cJ*np.pi*2*phase)

    #######
    atm = np.real(np.fft.ifft2(expf))
    atm = np.fft.ifftshift(atm)
   
#    plt.imshow(atm)
#    plt.colorbar()
#    plt.show()

    return atm

#G = makeatmos((500,500),scale=20)


#H = np.fft.fft2(G)
#H = np.abs(H)**2 

#P = np.fft.ifft2(H)
#P = np.fft.ifftshift(np.real(P))
#plt.imshow(P)
#plt.colorbar()
#plt.show()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
