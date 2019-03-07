'''Plotting routines to be called from the time-series scripts.

.. Dependencies:

    numpy, matplotlib.pyplot'''

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable

def imageone(arr,title=None,save=None):
    '''Plot a single array using imshow.
    
    Args:
    
        * arr          Array to be visualized
        
    Kwargs:
    
        * title        String with title
        * save         File name to store the output image.
        * show         Keep image on screen'''
    
    
    plt.figure('Displacement')
    plt.imshow(arr)
#    plt.colorbar(aspect=8,shrink=0.5)
    plt.colorbar()
    if title is not None:
        plt.title(title)
        
    if save is not None:
        plt.draw()
        plt.savefig(save)
    
    if show:
        plt.clf()
    
def imagemany(arrdict,save=None,horz=True,master=None,show=False,format='png', ion=False,title=None):
    '''Plot all the images in dictionary on same plot.
    
    Args:
    
        * arrdict        Dictionary of images. The keys automatically become titles.
        
    Kwargs:
    
        * save            Output file name if needed
        * horz            Horizontal sub plots
        * master          Should be one of the keys. Same color map used for all plots.
        * show            Keep image on screen'''
    
    if show and ion:
        plt.ion()
        
    num = len(arrdict.keys())
    shrfac = 1.0/(1.0*num)
    keys = arrdict.keys()
    

    if master is not None:
        mas = arrdict[master]
        colorlim = [np.nanmin(mas),np.nanmax(mas)]
    
    plt.figure('Displacement')
    for k in xrange(num):
        if horz:
            frame = 100+num*10+(k+1)
        else:
            frame = num*100+10+(k+1)
        
        arr = arrdict[keys[k]]
        plt.subplot(frame)
        if arr.dtype == 'bool':
            im = plt.imshow(arr, vmin=0., vmax=1.)
        else:
            im = plt.imshow(arr)

        im=plt.imshow(arr)
	if title is not None:
	        plt.title('%s %s'%(keys[k],title))
	else:
		plt.title(keys[k])
        if k>0:
            plt.yticks([])
        else:
            plt.yticks(np.round(np.arange(4)*arr.shape[0]/3.0))

        plt.xticks(np.round(np.arange(4)*arr.shape[1]/3.0))
        if master is not None:
            for im in plt.gca().get_images():
                im.set_clim(colorlim)
        

        divider = make_axes_locatable(plt.gca())
        cax = divider.append_axes("right", "5%", pad="3%")
        plt.colorbar(im, cax=cax)


    plt.tight_layout()
    if save is not None:
        plt.draw()
        plt.savefig(save,format=format)
 
    if show and not ion:
        plt.show()
    else:
        plt.clf()

    plt.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
