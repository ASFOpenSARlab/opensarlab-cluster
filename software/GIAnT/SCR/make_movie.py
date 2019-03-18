#!/usr/bin/env python
'''Script to make a MP4 movie from the time-series results.'''
import tsinsar as ts
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.mpl as mpl
import matplotlib
import h5py 
import datetime as dt
import argparse
import os
try:
    import json
except:
    try:
        import simplejson as json
    except:
        raise ImportError('No JSON modules found.')


def parse():
    parser = argparse.ArgumentParser(description='Make a MP4 movie from estimated time-series')
    parser.add_argument('-i', action='store', required=True, dest='fname', help='Input HDF5 file with the estimated time-series', type=str)
    parser.add_argument('-o', action='store', default='movie.mp4', dest='oname', help='Output MP4 movie file. Default: movie.mp4', type=str)
    parser.add_argument('-nslice', action='store', default=100, dest='nslice', help='Number of time-slices that time-span is divided into. Default: 100', type=int)
    parser.add_argument('-y', nargs=2, action='store', default=[-25,25], dest='ylim', help='Y Limits in cm for plotting. Default: [-25,25]',type=float)
    parser.add_argument('-win', action='store', default=0.33, dest='gwin', help='Sigma of Gaussian window in years used for interpolation. Used when model interpolation is not specified. Default=0.33', type=float)
    parser.add_argument('-model', action='store_true', default=False, dest='model', help='Use the inferred model instead of the Gaussian filter for interpolation.')
    parser.add_argument('-pix', nargs=2, action='store', default=None, dest='pix', help='Pixel (Azi,Rng) whos time-series will be plotted as reference. Default: Middle of image.', type=int)
    parser.add_argument('-fps', action='store', default=10, dest='fps', help='Frames per second for the movie. Default: 10', type=int)
    parser.add_argument('-geo', action='store', default=None, dest='geo', help='XML file to be used for making geocoded movies. Default: Radar coordinates.', type=str)
    inps = parser.parse_args()
    return inps


if __name__ == '__main__':
    inps = parse()
    fliplr = False
    flipud = False
    neigh = 0     #If you want time-series for neighborhood around specified point
    pixind = inps.pix

    #####Read in data from h5file
    hfile = h5py.File(inps.fname,'r')
    tims = hfile['tims'].value
    dates = hfile['dates'].value

    if inps.model:
        data = hfile['model']
        rep = json.loads(hfile['modelstr'].value)
    else:
        data = hfile['recons']

    cmask = hfile['cmask'].value
    masterind = hfile['masterind'].value

    flen = data.shape[1]
    fwid = data.shape[2]

    if pixind is None:
        pixind = [np.int(flen/2), np.int(fwid/2)]

    ######Setting up the dates correctly
    t0 = dt.date.fromordinal(np.int(dates[0]))
    t0 = t0.year + t0.timetuple().tm_yday/(np.choose((t0.year % 4)==0,[365.0,366.0]))
    tims = tims+t0

    ######Setting up axis
    plt.hold('on')
    pv = plt.figure('GIAnT',figsize=(10,8),dpi=180)
    axv = pv.add_axes([0.1, 0.25, 0.65, 0.65])
    axc = pv.add_axes([0.8, 0.35, 0.05, 0.5])

    cmap = mpl.cm.jet
    norm = mpl.colors.Normalize(vmin=inps.ylim[0], vmax=inps.ylim[1])
    clb = mpl.colorbar.ColorbarBase(axc,cmap=cmap,norm=norm, orientation='vertical')
    clb.set_label('In cm')

    axts = pv.add_axes([0.1,0.05,0.65,0.15])
    pixts = []

    ######Interpolation times
    tarry = np.linspace(tims.min(),tims.max(), num=inps.nslice)
    if inps.model:
        Hmat, mname, repf = ts.Timefn(rep, tarry-tarry.min())
        Horig, mname, repf = ts.Timefn(rep, tims-tims.min())
        

    if inps.geo is not None:    ####Geocoded movies instead of radar coded.
        import geocode.geocode as geocode
        pars = ts.TSXML(inps.geo, File=True)
        h5dir = (pars.data.dirs.h5dir)
        latf  = os.path.join(h5dir,(pars.data.subimage.latfile))
        lonf  = os.path.join(h5dir,(pars.data.subimage.lonfile))

        lats = np.fromfile(latf, dtype=np.float32).reshape((flen,fwid))
        lons = np.fromfile(lonf, dtype=np.float32).reshape((flen,fwid))
        gcode = geocode(lats, lons)
        imextent = [gcode.area_extent[0], gcode.area_extent[1], gcode.area_extent[3], gcode.area_extent[2]];
        

    odata = data[:,pixind[0]-neigh:pixind[0]+neigh+1,pixind[1]-neigh:pixind[1]+neigh+1]/10.0
    prets = np.zeros(odata.shape[0])
    for k in xrange(odata.shape[0]):
        prets[k] = ts.nanmean(odata[k,:,:])

    if inps.model:
        prets = np.dot(Horig, prets)

   
    progb = ts.ProgressBar(maxValue=inps.nslice)

    def animate(ind):
        '''Function called repeatedly for the animation'''
        tinp = tarry[ind]
        res = np.zeros((flen,fwid))
        progb.update(ind, every=1)

        #####Replace this part as needed 
        if inps.model:
            for k in xrange(flen):
                gd = data[:,k,:]
                res[k,:] = np.dot(Hmat[ind,:],gd)
        else:
            win = np.exp(-0.5*(tims-tinp)**2 / (inps.gwin*inps.gwin))
            win = win/(win.sum())
    
            for k in xrange(flen):
                gd = data[:,k,:]
                res[k,:] = np.dot(win,gd)

        zpt = (res == 0)
        res[zpt] = np.nan
        res = res/10.0

        
        ######Evolution of pixel
        if (ind==0):
            if len(pixts)==0:
                pixts.append(ts.nanmean(res[pixind[0]-neigh:pixind[0]+neigh+1,pixind[1]-neigh:pixind[1]+neigh+1]))
        else:
            pixts.append(ts.nanmean(res[pixind[0]-neigh:pixind[0]+neigh+1,pixind[1]-neigh:pixind[1]+neigh+1]))

        lpre = np.flatnonzero(tims <= tinp)


        if inps.geo is not None:
            res = gcode.rdr2geo_nearest(res, radius=400)


        axv.cla()
        if inps.geo:      #Plot geocoded coordinates
            img = axv.imshow(res, clim=inps.ylim, extent = imextent)
            axv.set_xlim([gcode.area_extent[0],gcode.area_extent[1]])
            axv.set_ylim([gcode.area_extent[2],gcode.area_extent[3]])
            axv.scatter(lons[pixind[0],pixind[1]],lats[pixind[0],pixind[1]],c='g',s=50,marker='*')

        else:
            img = axv.imshow(res,clim=inps.ylim)
            if fliplr:
                xlim = [fwid,0]
            else:
                xlim = [0,fwid]
            axv.set_xlim(xlim)

            if flipud:
                ylim = [0,flen]
            else:
                ylim = [flen,0]
            axv.set_ylim(ylim)

            axv.scatter(pixind[1],pixind[0],c='g',s=50,marker='*')


        yr = np.int(np.floor(tinp))
        frac = np.int(np.round((tinp -yr)*365.25))
        dstr = dt.datetime(yr,1,1) + dt.timedelta(frac-1)
        axv.set_title(dstr.strftime('%b - %Y'))


        axts.cla()
        axts.bar(tims, -1*np.ones(len(tims)), width=0.05, color='k')

        tplt = axts.plot(tarry[0:ind+1], np.array(pixts),lw=3)
        gplt = axts.scatter(tims[lpre],prets[lpre],c='k',s=20) 
        axts.set_ylim(inps.ylim)
        axts.set_xlim([tims[0],tims[-1]])

        return img, tplt, gplt

    ani = matplotlib.animation.FuncAnimation(pv, animate, np.arange(inps.nslice, dtype=np.int), interval=25, blit=True)
    progb.close()

    ani.save(inps.oname, fps=inps.fps)
