#!/usr/bin/env python

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.widgets import Slider
from matplotlib.ticker import FormatStrFormatter
import sys
import h5py
import datetime as dt
import tsinsar as ts
import argparse
try:
    import json
except:
    try:
        import simplejson as json
    except:
        raise ImportError('No JSON modules found.')

#######Command line parsing.
def parse():
    parser = argparse.ArgumentParser(description='Interactive SBAS time-series viewer')
    parser.add_argument('-e', action='store_true', default=False, dest='plot_err', help='Display error bars if available. Default: False')
    parser.add_argument('-f', action='store', default='Stack/LS-PARAMS.h5', dest='fname', help='Filename to use. Default: Stack/LS-PARAMS.h5', type=str)
    parser.add_argument('-i', action='store', default=None, dest='tind', help='Slice to display. Default: Middle index', type=int)
    parser.add_argument('-m', action='store', default=0.1, dest='mult', help='Scaling factor. Default: 0.1 for mm to cm', type=float)
    parser.add_argument('-y', nargs=2, action='store', default=[-25,25], dest='ylim', help='Y Limits for plotting. Default: [-25,25]',type=float)
    parser.add_argument('-ms', action='store', default=5, dest='msize', help='Marker size. Reduce if error bars are too small. Default: 5', type=float)
    parser.add_argument('-raw',action='store_true', default=False, dest='pltraw', help='Plot Un-Filtered Time Series as well, if available')
    parser.add_argument('-model',action='store_true', default=False, dest='pltmodel', help='Plot the individual model components as well. For NSBAS, Timefn and MInTS.')
    parser.add_argument('-mask', nargs=2, action='store', default=None, dest='mask', help='To mask out values. Need to provide 2 inputs - Mask file in float and xml file with dimensions. Default: None', type=str)
    parser.add_argument('-zf',action='store_true', default=False, dest='zerofirst', help='Changes time-origin to first acquisition for showing time-series.')
    inps = parser.parse_args()
    return inps

if __name__ == '__main__':
    #######Actual code.
    inps = parse()
    logger = ts.logger

    logger.info('Do not close any figures, except to quit the program.')
    #####External Mask
    if inps.mask is not None:
        logger.info('Reading mask file: %s'%(inps.mask))
        pars = ts.TSXML(inps.mask[1],File=True)
        flen = (pars.data.subimage.length)
        fwid = (pars.data.subimage.width)

        fin = open(inps.mask[0],'r')
        num = flen*fwid
        dmask = np.fromfile(file=fin,dtype=np.float32,count = flen*fwid)
        fin.close()
        dmask = dmask.reshape((flen,fwid))


    hfile = h5py.File(inps.fname,'r')
    tims = hfile['tims'].value
    data = hfile['recons']
    masterind = hfile['masterind'].value

    ####Raw Time-series
    raw = None
    if inps.pltraw:
        if 'rawts' in hfile.keys():
            raw = hfile['rawts']
        else:
            logger.info('Input h5 file does not contain raw time-series. Continuing ....')
            inps.pltraw = False

    #####Common mask
    if 'cmask' in hfile.keys():
        cmask = hfile['cmask'].value
    else:
        cmask = np.ones((flen,fwid))

    err = None
    if inps.plot_err: 
        if 'error' in hfile.keys():
            err = hfile['error']
        else:
            logger.info('Input h5file does not contain error estimates. Continuing ....')

    
    ######Dates
    dates = hfile['dates'].value
    t0 = dt.date.fromordinal(np.int(dates[0]))
    t0 = t0.year + t0.timetuple().tm_yday/(np.choose((t0.year % 4)==0,[365.0,366.0]))
    tims = tims+t0

    if inps.mask is not None:
        cmask = cmask*dmask

    if inps.zerofirst:
        dref = data[0,:,:]
    else:
        dref = 0.0

    ######Reading in the model parameters
    parms = None
    if inps.pltmodel:
        if 'ModelMat' in hfile.keys():
            Hmat = hfile['ModelMat'].value
            npar = Hmat.shape[1]
            names = list(str(np.arange(npar)))
            parms = hfile['parms']
            modaxis = 2

        elif 'modelstr' in hfile.keys():
            modstr = json.loads(hfile['modelstr'].value)
            Hmat,names,regf = ts.Timefn(modstr,tims-tims[0])
            npar = Hmat.shape[1]
            parms = hfile['model']
            modaxis=0
        elif 'mName' in hfile.keys():
            Name = hfile['mName'].value
            rep = ts.mName2Rep(Name)
            Hmat, names, regF = ts.Timefn(rep,tims-tims[0])
            npar = Hmat.shape[1]
	    if (Name[-1] in 'demerr'):
		nd = Hmat.shape[0]
		Hmat = np.hstack((Hmat,np.zeros((nd,1))))

            parms = hfile['parms']
            modaxis=2
        else:
            logger.info('No model description in the given hdf5 file. Continuing ....')


    
    if inps.tind is None:
        avgind = np.int(data.shape[0]/2)
    else:
        avgind = inps.tind

    meanv = (data[avgind,:,:]-dref)*cmask*inps.mult

    ######Starting the plotting routines
    pv = plt.figure('Cumulative Displacement')
    #axv = pv.add_subplot(111)
    #axv.set_position([0.125,0.25,0.75,0.65])
    #This works on OSX. Original worked on Linux.
    axv= pv.add_axes([0.125,0.25,0.75,0.65])
    cax=axv.imshow(meanv,clim=inps.ylim)
    dstr = dt.date.fromordinal(np.int(dates[avgind])).strftime('%b-%d-%Y')

    axv.set_title('Time = %s'%dstr)
    axv.set_xlabel('Range')
    axv.set_ylabel('Azimuth')
    cbr=pv.colorbar(cax, orientation='vertical')


    axtim = pv.add_axes([0.2,0.1,0.6,0.07],axisbg='lightgoldenrodyellow',yticks=[])
    tslider = Slider(axtim,'Time',tims[0],tims[-1],valinit=tims[avgind])
    tslider.ax.bar(tims, np.ones(len(tims)), facecolor='black', width=0.01, ecolor=None)
    tslider.ax.set_xticks(np.round(np.linspace(tims[0],tims[-1],num=5)*100)/100)

    def tim_slidupdate(val):
        global pv,cax,axv,cmask,inps,dates
        timein = tslider.val
        timenearest = np.argmin(np.abs(tims-timein))
        dstr =  dt.date.fromordinal(np.int(dates[timenearest])).strftime('%b-%d-%Y')
        axv.set_title('Time = %s'%(dstr))
        newv = (data[timenearest,:,:]-dref)*cmask*inps.mult
        cax.set_data(newv)
        pv.canvas.draw()

    tslider.on_changed(tim_slidupdate)


    pts = plt.figure('Time-series')
    axts=pts.add_subplot(111)
    axts.scatter(tims,np.zeros(len(tims)))

    def printcoords(event):
        #outputting x and y coords to console
        global axv,axts,ts,data,canvas2,pts,inps,err,cmask
        if event.inaxes != axv:
            return

        ii = np.int(np.floor(event.ydata))
        jj = np.int(np.floor(event.xdata))

        if np.isfinite(cmask[ii,jj]):
            dph = inps.mult*data[:,ii,jj]

            if raw is not None:
                    dphraw = inps.mult*raw[:,ii,jj]

            if err is not None:
                derr = np.abs(inps.mult*err[:,ii,jj])

            if parms is not None:
                if modaxis==2:
                    dmodel = inps.mult*np.dot(Hmat,parms[ii,jj,:])
                elif modaxis==0:
                    dmodel = inps.mult*np.dot(Hmat,parms[:,ii,jj])

            if inps.zerofirst:
                dph = dph-dph[0]
                if raw is not None:
                    dphraw = dphraw - dphraw[0]

                if parms is not None:
                    dmodel = dmodel - dmodel[0]

            axts.cla()
            if err is None:
                axts.scatter(tims,dph)
            else:
                axts.errorbar(tims,dph,yerr=derr,fmt='o',ms=inps.msize, barsabove=True)

            if raw is not None:
                axts.scatter(tims,dphraw,c='r')

            if parms is not None:
                axts.scatter(tims,dmodel,c='g')

            axts.set_ylim(inps.ylim)
            axts.set_title('Line = %d, Pix = %d'%(ii,jj))
            axts.set_xlabel('Time in years')
            if np.abs(inps.mult) == 0.1:
                axts.set_ylabel('Displacement in cm')
            else:
                axts.set_ylabel('Scaled Displacement')

        else:
            axts.cla()
            axts.scatter(tims,np.zeros(len(tims)))
            axts.set_title('NaN: L = %d, P = %d'%(ii,jj))

        axts.xaxis.set_major_formatter(FormatStrFormatter('%4.2f'))
        pts.canvas.draw()

    #######Model browser - For going through the parameters.
    if parms is not None:
        pm = plt.figure('Model browser')
        axm = pm.add_subplot(111)
        axm.set_position([0.125,0.25,0.75,0.65])
        if modaxis == 2:
            caxm=axm.imshow(parms[:,:,0])
        elif modaxis==0:
            caxm=axm.imshow(parms[0,:,:])

        axm.set_title('Index = %d, Name = %s'%(0,names[0]))
        axm.set_xlabel('Range')
        axm.set_ylabel('Azimuth')
        cbrm=pm.colorbar(caxm, orientation='vertical')


        axmod = pm.add_axes([0.2,0.1,0.6,0.07],axisbg='lightgoldenrodyellow',yticks=[])
        mslider = Slider(axmod,'Index',0,npar-1,valinit=0)
        mslider.ax.bar(np.arange(npar), np.ones(npar), facecolor='black', width=0.01, ecolor=None)
        mslider.ax.set_xticks(np.round(np.linspace(0,npar-1,num=5)))

        def model_slidupdate(val):
            global pm,caxm,axm,modaxis
            modin = mslider.val
            modnearest = np.round(modin)
            axm.cla()
            if modaxis==2:
                newm = parms[:,:,modnearest]
            elif modaxis==0:
                newm = parms[modnearest,:,:]

            caxm = axm.imshow(newm)
            cbrm.update_bruteforce(caxm)
            axm.set_title('Index = %d, Name = %s'%(modnearest,names[modnearest]))  
            pm.canvas.draw()

        mslider.on_changed(model_slidupdate)




    ######Final linking of the canvas to the plots.
    cid = pv.canvas.mpl_connect('button_press_event', printcoords)
    plt.show()
    pv.canvas.mpl_disconnect(cid)
