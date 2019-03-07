#!/usr/bin/env python
import tsinsar as ts
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.mpl as mpl
import h5py
import datetime as dt
import geocode.geocode as geocode
from pykml.factory import KML_ElementMaker as KML
from lxml import etree
import os
import argparse
try:
    import json
except:
    try:
        import simplejson as json
    except:
        raise ImportError('No JSON modules found.')


def parse():
    parser = argparse.ArgumentParser(description='Make a KML/KMZ file with a time-slider for visualization on Google Earth.')
    parser.add_argument('-i', action='store', required=True, dest='fname', help='Input HDF5 file with the estimated time-series', type=str)
    parser.add_argument('-x', action='store', default='data.xml', dest='xname', help='XML file with the data information.', type=str)
    parser.add_argument('-o', action='store', default = 'doc.kml', dest='oname', help='Output KML/KMZ file',type=str)
    parser.add_argument('-nslice', action='store', default=100, dest='nslice', help='Number of time-splices that the time-span is divided into. Default: 100', type=int)
    parser.add_argument('-y', nargs=2, action='store', default=[-25,25], dest='ylim', help='Y Limits in cm for plotting. Default: [-25,25]',type=float)
    parser.add_argument('-win', action='store', default=0.33, dest='gwin', help='Sigma of Gaussian window in years used for interpolation. Used when model interpolation is not specified. Default=0.33', type=float)
    parser.add_argument('-model', action='store_true', default=False, dest='model', help='Use the inferred model instead of the Gaussian filter for interpolation.')
    parser.add_argument('-dir', action='store', default='images', dest='diri', help='Directory that stores the PNG files for the KML/KMZ file.', type=str)
    parser.add_argument('-trans', action='store_true', default=False, dest='trans', help='Use flag to make nan data transparent in output. (Can be slow). Default: False')
    inps = parser.parse_args()
    return inps


if __name__ == '__main__':
    inps = parse()

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

    ######Setting up the dates correctly
    t0 = dt.date.fromordinal(np.int(dates[0]))
    t0 = t0.year + t0.timetuple().tm_yday/(np.choose((t0.year % 4)==0,[365.0,366.0]))
    tims = tims+t0
    tarry = np.linspace(tims.min(), tims.max(), num=inps.nslice)

    if inps.model:
        Hmat, mname, repf = ts.Timefn(rep, tarry-tarry.min())
        Horig, mname, repf = ts.Timefn(rep, tims-tims.min())


    ######Setting up the geocoder
    pars = ts.TSXML(inps.xname, File=True)
    h5dir = (pars.data.dirs.h5dir)
    latf  = os.path.join(h5dir,(pars.data.subimage.latfile))
    lonf  = os.path.join(h5dir,(pars.data.subimage.lonfile))

    lats = np.fromfile(latf, dtype=np.float32).reshape((flen,fwid))
    lons = np.fromfile(lonf, dtype=np.float32).reshape((flen,fwid))
    gcode = geocode(lats, lons)
    imextent = [gcode.area_extent[0], gcode.area_extent[1], gcode.area_extent[3], gcode.area_extent[2]];
    

   
    plt.hold('on')
    pv = plt.figure('GIAnT',figsize=(8,8))
    axv = pv.add_axes([0., 0., 1., 1.])    ####Full space.
    aspect = fwid/(flen*1.0)

    ts.makedir([inps.diri])

    progb = ts.ProgressBar(maxValue=inps.nslice)

    def animate(ind):
        tinp = tarry[ind]
        res = np.zeros((flen,fwid))

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
    
    
        res = res/10
        im2 = gcode.rdr2geo_nearest(res, radius=400)


        axv.cla()
        img = axv.imshow(im2,clim=inps.ylim,aspect=aspect)
        axv.set_xlim([0,fwid])
        axv.set_ylim([0,flen])
        axv.yaxis.set_visible(False)
        axv.xaxis.set_visible(False)
        progb.update(ind, every=1)

        return img

    ani = ts.animate.FuncAnimation(pv, animate, np.arange(inps.nslice, dtype=np.int), interval=25, blit=True)
    progb.close()


    mname = os.path.join(inps.diri,'temp.mp4')
    ani.save(mname, fps=10, clear_temp=False, frame_prefix='%s/slice'%(inps.diri), transp=inps.trans)

    ######Making the colorbar
    pc = plt.figure(figsize=(1,4))
    axc = pc.add_subplot(111)
    cmap = mpl.cm.jet
    norm = mpl.colors.Normalize(vmin=inps.ylim[0], vmax=inps.ylim[1])
    clb = mpl.colorbar.ColorbarBase(axc,cmap=cmap,norm=norm, orientation='vertical')
    clb.set_label('cm')
    pc.subplots_adjust(left=0.25,bottom=0.1,right=0.4,top=0.9)
    pc.savefig('%s/cbr.png'%(inps.diri))

    print 'Building KML'
    progb = ts.ProgressBar(maxValue=inps.nslice)
    #######Building the KML file
    doc = KML.kml(KML.Folder(KML.name('Slider Example')))
    for k in xrange(inps.nslice):
        yr = np.int(np.floor(tarry[k]))
        frac = np.int(np.round((tarry[k] -yr)*365.25))
        dstr = dt.datetime(yr,1,1) + dt.timedelta(frac-1)
        name = dstr.strftime('%Y-%m-%d')
        fname = '%s/slice%04d.png'%(inps.diri,k)


        if k==0:
            dstr1 = dstr
            tend = 0.5*(tarry[1]+tarry[0])
            yr = np.int(np.floor(tend))
            frac = np.int(np.round((tend -yr)*365.25))
            dstr2 = dt.datetime(yr,1,1) + dt.timedelta(frac-1)
        elif k== (inps.nslice-1):
            dstr2 = dstr
            tstart = 0.5*(tarry[-2]+tarry[-1])
            yr = np.int(np.floor(tstart))
            frac = np.int(np.round((tstart -yr)*365.25))
            dstr1 = dt.datetime(yr,1,1) + dt.timedelta(frac-1)

        else:
            tstart = 0.5*(tarry[k-1]+tarry[k])
            yr = np.int(np.floor(tstart))
            frac = np.int(np.round((tstart -yr)*365.25))
            dstr1 = dt.datetime(yr,1,1) + dt.timedelta(frac-1)
            tend = 0.5*(tarry[k]+tarry[k+1])
            yr = np.int(np.floor(tend))
            frac = np.int(np.round((tend -yr)*365.25))
            dstr2 = dt.datetime(yr,1,1) + dt.timedelta(frac-1)

        slc = KML.GroundOverlay(KML.name(name),KML.TimeSpan(KML.begin(dstr1.strftime('%Y-%m')),KML.end(dstr2.strftime('%Y-%m'))),KML.Icon(KML.href(fname)),KML.LatLonBox(KML.north(str(imextent[2])),KML.south(str(imextent[3])),KML.east(str(imextent[1])),KML.west(str(imextent[0]))))
        doc.Folder.append(slc)
        progb.update(k, every=1)

    progb.close()

    latdel = imextent[2]-imextent[3]
    londel = imextent[1]-imextent[0]
    slc = KML.GroundOverlay(KML.name('colorbar'),KML.Icon(KML.href(os.path.join(inps.diri,'cbr.png'))),KML.LatLonBox(KML.north(str(imextent[2]-0.2*latdel)), KML.south(str(imextent[3]+0.2*latdel)), KML.east(str(imextent[0]-0.2*londel)), KML.west(str(imextent[0]-0.3*londel))),KML.altitude('9000'),KML.altitudeMode('absolute'))
    doc.Folder.append(slc)

    kmlstr = etree.tostring(doc, pretty_print=True)

    if inps.oname.endswith('kmz'):
        kmlname = os.path.join(os.path.splitext(inps.oname)[0]+'.kml')
    else:
        kmlname = inps.oname

    fout = open(kmlname,'w')
    fout.write(kmlstr)
    fout.close()

    if inps.oname.endswith('kmz'):
        cmd = 'zip %s %s %s/slice*'%(inps.oname, kmlname, inps.diri)
        os.system(cmd)
