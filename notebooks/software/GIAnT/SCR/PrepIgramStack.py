#!/usr/bin/env python
'''Reads the input interferograms and correlation files, masks data
according to a threshold and creates the igram matrix. The results are
 stored in a HDF5 file.
 
.. author:
 
    Piyush Agram <piyush@gps.caltech.edu>
    Batuhan Osmanoglu <batu@gi.alaska.edu>
     
.. Default Inputs:
     
    * ifg.list   -> List with interferogram information
    * data.xml   -> Data parameters from prepxml.py

.. Default Outputs:

    * Stack/RAW-STACK.h5    -> Igram stack + aux information
    * Stack/lat.flt         -> Cropped lat file (from data.xml)
    * Stack/lon.flt         -> Cropped lon file (from data.xml)
    * Stack/hgt.flt[.rsc]   -> Cropped hgt file (from data.xml)
'''

'''CHANGE_LOG:
20121217: Modified for ADORE.

'''
     
import numpy as np
import tsinsar as ts
import sys
import h5py
import matplotlib.pyplot as plt
import os
import collections
import argparse
import imp



###########The main code that reads data and prepares stacks#######
def parse():
    parser = argparse.ArgumentParser(description='Reads in unwrapped interferograms and prepares data from time-series processing. See doc strings in code for details.')
    parser.add_argument('-i', action='store', default='ifg.list', dest='iname', help='Text file to be read for interferogram information. Default: ifg.list', type=str)
    parser.add_argument('-o', action='store', default='RAW-STACK.h5', dest='oname', help='To override the default output HDF5 file. Default: RAW-STACK.h5', type=str)
    parser.add_argument('-x', action='store', default='data.xml', dest='dxml', help='To override the default data xml file. Default: data.xml', type=str)
    parser.add_argument('-f', action='store', default='Igrams', dest='figs', help='To override the default directory for creating PNG previews. Default:Igrams', type=str)
    parser.add_argument('-u', action='store', default='userfn.py', dest='userpy', help='Stand-alone python script with user-defined function (makefnames).', type=str)
    inps = parser.parse_args()
    return inps
    

#########Start of the main program.
if __name__ == '__main__':
    inps = parse()
    logger = ts.logger
    try:
        user=imp.load_source('makefnames',inps.userpy)
    except:
        logger.info('No user defined function for file names in userfn.py')
        logger.info('Assuming file names are directly read in.')
    if "userfn_adore.py" in inps.userpy:
        logger.info('ADORE-DORIS specific customizations are selected.')

    #########Reading the parameters.
    pars = ts.TSXML(inps.dxml,File=True)

    sarproc = (pars.data.proc)

    ########Get directory structure
    figdir = (pars.data.dirs.figsdir)
    h5dir  = (pars.data.dirs.h5dir)


    ##########Create directory structure.
    ts.makedir([figdir,h5dir])

    #####My work around for 2 sensors. Not needed if using only 1.
    rdict = {}
    rdict['ERS-wvl'] = 0.0565646
    rdict['ENV-wvl'] = 0.0562356

    ####Output HDF5 file.

    ilist = None  #List of interferogram file names
    clist = None  #List of coherence file names
    slist = None    #List of satellite sensors

    #####Reading in network data.
    #####Do not read in slist if you are using only one sensor.
    if "userfn_adore" not in inps.userpy:    
        [date1,date2,bperp,slist]=ts.textread(inps.iname,'s s f s')
        dates = np.hstack((date1[:,None],date2[:,None]))
    else:
        #FOR adore it is to return ilist and clist directly (at the moment at least).
        drs=ts.textread(inps.iname,'s')[0]
        [date1, date2, bperp, ilist, clist, wlist]=user.import_adore_meta(mresfiles=None, sresfiles=None, iresfiles=None, drsFiles=drs)
        dates = np.vstack((date1,date2)).T 

    #########Check if file names are defined.
    if ilist is None:
        try:
            user.makefnames
        except:
            raise ValueError('No user defined file names found.')


    ######If undefined, set up single sensor
    if slist is None:
        sat = np.ones(len(bperp),dtype='S3')
    else:
        sat = slist

    days,usat,Jmat = ts.ConnectMatrix(dates,sat)

    Nifg = Jmat.shape[0]
    Nsar = Jmat.shape[1]


    ##########Report some stats
    logger.info('Number of interferograms = ' + str(Nifg))
    logger.info('Number of unique SAR scenes = ' + str(Nsar))
    nIslands = np.min(Jmat.shape) - np.linalg.matrix_rank(Jmat)
    logger.info('Number of connected components in network: ' + str(nIslands))

    if nIslands > 1:
        logger.warn('The network appears to be contain disconnected components')

    #######Setting first scene to reference.
    tims = (days-days[0])/365.25    #conversion to years

    ######Choosing a set of coherent pixels can be achieved using CMASK.
    flen = (pars.data.master.file_length)
    fwid = (pars.data.master.width)
    mask = (pars.data.master.mask)
    cthresh = (pars.data.master.cthresh)
    wvl = (pars.data.master.wavelength)
    chgendian = (pars.data.format.chgendian)
    endianlist = (pars.data.format.endianlist)


    #######Check for presence of common mask
    if mask is None:
        logger.info('No common mask defined')
        cmask = np.ones((flen,fwid))
    else:
        masktype = (pars.data.format.masktype)
        if masktype == 'GMT':
            cmask = ts.load_grd(mask)
            if cmask.shape != (flen,fwid):
                raise ValueError('Shape mismatch in GRDfile: '%mask)

        else:
            #cmask = ts.load_flt(mask,fwid,flen,datatype=masktype,
            #    conv=(chgendian and 'MASK' in endianlist))
	    cmask = np.ones((flen,fwid))
            rmask = ts.load_mmap(mask, fwid, flen, datatype=masktype,
                    conv = (chgendian and 'MASK' in endianlist))
            cmask = cmask*rmask

        cmask[cmask==0] = np.nan

    ####Other parameters related to data..
    nlen = (pars.data.subimage.length)
    nwid = (pars.data.subimage.width)
    lks  = (pars.data.subimage.looks)
    Ry0 = (pars.data.subimage.rymin)
    Ry1 = (pars.data.subimage.rymax)
    Rx0 = (pars.data.subimage.rxmin)
    Rx1 = (pars.data.subimage.rxmax)
    x0 = (pars.data.subimage.xmin)
    x1 = (pars.data.subimage.xmax)
    y0 = (pars.data.subimage.ymin)
    y1 = (pars.data.subimage.ymax)

    lx0 = lks*x0
    lx1 = min((lks*x1, fwid))
    ly0 = lks*y0
    ly1 = min((lks*y1, flen))
    cmask = cmask[ly0:ly1, lx0:lx1]
    
    #####Preparing for reading in IFGs.
    outname = os.path.join(h5dir,inps.oname)
    figsname = os.path.join(figdir,inps.figs)
    ts.makedir([figsname])

    logger.info('Output h5file: %s',outname)
    logger.info('PNG preview dir: %s',figsname)

    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Deleting previous %s'%(outname))

    f = h5py.File(outname,"w")
    f.attrs['help'] = 'All the raw data read from individual interferograms into a single location for fast access.'


    ifgs = f.create_dataset('igram',(Nifg,nlen,nwid),'f')
    ifgs.attrs['help'] = 'Unwrapped IFGs read straight from files.'

    rawstack = ts.STACK(ifgs,conn=Jmat,baseline=bperp)

    progb = ts.ProgressBar(minValue=0,maxValue=Nifg)

    #####Number of sensors
    if slist is not None:
        nsens = len(set(slist))
    else:
        nsens = 1

    logger.info('Reading in IFGs')
    unwfmt = (pars.data.format.unwfmt)
    corfmt = (pars.data.format.corfmt)

    for k in xrange(Nifg):
        if ilist is None and clist is None:
        #####File names not provided as input
            iname,cname = user.makefnames(dates[k,0],dates[k,1],sat[k])
        else:
            #####File names provided in input file
            iname = ilist[k]
            cname = clist[k]

        if "userfn_adore" in inps.userpy:
            scl = 1000*wlist[k]/(4*np.pi) 	     ####Converting to mm.
        else:
            if nsens==1:   #Single sensor being used.
                scl = 1000*wvl/(4*np.pi)
            else:
                #####Set rdict earlier in the program
                wname = '%s-wvl'%(sat[k])
                scl = 1000*rdict[wname]/(4*np.pi)        ####Converting to mm.

        phs = None
    #   In case of one satellite. scl is constant and uses wvl from XML.
        if (sarproc == 'GMT') or (unwfmt=='GRD'):
            phs = ts.load_grd(iname, shape=(flen,fwid))
        elif unwfmt=='RMG':
            #tmp,phs = ts.load_rmg(iname,fwid,flen,scale=scl,quiet=True,
            #        conv=(chgendian and 'UNW' in endianlist))
            phs = ts.load_mmap(iname, fwid, flen, quiet=True, map='BIL',
                    nchannels=2, channel=2,conv = (chgendian and 'UNW' in endianlist))
        elif unwfmt=='FLT':
            #            phs = ts.load_flt(iname,fwid,flen, scale=scl,quiet=True,
            #    conv=(chgendian and 'UNW' in endianlist))
            phs = ts.load_mmap(iname, fwid, flen, quiet=True, conv= (chgendian and 'UNW' in endianlist))
        else:
            raise ValueError('Undefined format for unw files.')

        cor = None
        if (sarproc == 'GMT') or (corfmt == 'GRD'):
            cor = ts.load_grd(cname, shape=(flen,fwid))

        elif corfmt=='RMG':
            #            tmp,cor = ts.load_rmg(cname,fwid,flen,quiet=True,
            #    conv=(chgendian and 'COR' in endianlist))
            cor = ts.load_mmap(cname, fwid, flen, quiet=True, map='BIL',
                        nchannels=2, channel=2, conv = (chgendian and 'COR' in endianlist))


        elif corfmt=='FLT':
            #            cor = ts.load_flt(cname,fwid,flen,quiet=True,
            #    conv=(chgendian and 'COR' in endianlist))
            cor = ts.load_mmap(cname, fwid, flen, quiet=True, 
                        conv = (chgendian and 'COR' in endianlist))

        else:
            raise ValueError('Undefined format for cor files.')

        
        mask = np.nan*np.ones((ly1-ly0,lx1-lx0))
        mask[cor[ly0:ly1,lx0:lx1] >= cthresh] = 1.0
        mask = mask*cmask

        mask[phs[ly0:ly1,lx0:lx1] == 0.0] = np.nan
        phs = phs[ly0:ly1,lx0:lx1]*mask*scl

#####Multi-looking
        if lks != 1:
            phs = ts.LookDown(phs,lks,'MEAN')
            mask = ts.LookDown(mask,lks,'MEAN')
            mask = np.isfinite(mask)


#####Computing reference phase.
        sub = phs[Ry0:Ry1,Rx0:Rx1]
        refph = ts.nanmean(sub)

        if np.isnan(refph):
            raise ValueError('Reference region has no pixels for interferogram %d.' % (k))

        phs = phs - refph
        phs = phs.astype(np.float32)
   
######Saving an image for checking.
        imname = '%s/I%03d-%s-%s-%s.png'%(figsname,k+1,dates[k,0],dates[k,1],sat[k])
        idict = collections.OrderedDict()
        idict['Unw phase'] = phs
        idict['Mask'] = np.isfinite(mask)
        ts.imagemany(idict,save=imname)

        rawstack.setslice(k,phs)

        progb.update(k,every=2)


    progb.close()

    #######Multi-look common mask as well.
    logger.info('Fixing mask and geometry files.')
    if lks!=1:
        cmask = ts.LookDown(cmask,lks,'MEAN')

    latf = (pars.data.master.latfile)
    if latf is not None:
        olatf = (pars.data.subimage.latfile)
        if sarproc == 'GMT':
            lat = ts.load_grd(latf, shape=(flen,fwid))
        else:
            #lat = ts.load_flt(latf,fwid,flen,quiet=True,
            #    conv=(chgendian and 'LAT' in endianlist))
            lat = ts.load_mmap(latf, fwid, flen, quiet=True,
                    conv = (chgendian and 'LAT' in endianlist))

        lat = lat[ly0:ly1, lx0:lx1]
        if lks!=1:
            lat = ts.LookDown(lat,lks,'MEAN')

        lout = open(os.path.join(h5dir,olatf),'wb')
        lat = lat.astype(np.float32)
        lat.tofile(lout)
        lout.close()
        del lat

    lonf = (pars.data.master.lonfile)
    if lonf is not None:
        olonf = (pars.data.subimage.lonfile)

        if sarproc == 'GMT':
            lon = ts.load_grd(lonf,shape=(flen,fwid))
        else:
            #lon = ts.load_flt(lonf,fwid,flen,quiet=True,
            #    conv=(chgendian and 'LON' in endianlist))
            lon = ts.load_mmap(lonf,fwid,flen, quiet=True,
                conv = (chgendian and 'LON' in endianlist))

        lon = lon[ly0:ly1,lx0:lx1]

        if lks!=1:
            lon = ts.LookDown(lon,lks,'MEAN')

        lout = open(os.path.join(h5dir,olonf),'wb')
        lon = lon.astype(np.float32)
        lon.tofile(lout)
        lout.close()
        del lon

    inc = (pars.data.master.incidence)
    if inc is not None:
        if isinstance(inc,str):
            oincf = (pars.data.subimage.incidence)
            if sarproc == 'GMT':
                ang = ts.load_grd(inc, shape=(flen,fwid))
            else:
            #ang = ts.load_flt(inc,fwid,flen,quiet=True,
            #        conv=(chgendian and 'INC' in endianlist))
                ang = ts.load_mmap(inc, fwid, flen, quiet=True,
                    conv=(chgendian and 'INC' in endianlist))

            ang = ang[ly0:ly1, lx0:lx1]
            if lks!=1:
                ang = ts.LookDown(ang,lks,'MEAN')

            ang = ang.astype(np.float32)
            lout = open(os.path.join(h5dir,oincf),'wb')
            ang.tofile(lout)
            lout.close()
            del ang

    demfmt = (pars.data.format.demfmt)
    hgtf = (pars.data.master.hgtfile)
    if hgtf is not None:
        ohgtf = (pars.data.subimage.hgtfile)

        if sarproc == 'GMT':
            hgt = ts.load_grd(hgtf, shape=(flen,fwid))

        elif demfmt=='RMG':
            #dum,hgt = ts.load_rmg(hgtf,fwid,flen,quiet=True,
            #        conv=(chgendian and 'HGT' in endianlist))
            hgt = ts.load_mmap(hgtf, fwid, flen, quiet=True, map='BIL',
                nchannels=2, channel=2, conv = (chgendian and 'HGT' in endianlist))
        elif demfmt=='FLT':
        #hgt = ts.load_flt(hgtf,fwid,flen,quiet=True,
            #            conv=(chgendian and 'HGT' in endianlist))
            hgt = ts.load_mmap(hgtf, fwid, flen, quiet=True,
                    conv = (chgendian and 'HGT' in endianlist))
        else:
            raise ValueError('Unknown DEM format.')

        hgt = hgt[ly0:ly1, lx0:lx1]
        if lks!=1:
            hgt = ts.LookDown(hgt,lks,'MEAN')

        hgt = hgt.astype(np.float32)
        lout = open(os.path.join(h5dir,ohgtf),'wb')
        hgt.tofile(lout)
        lout.close()
        del hgt
    #######Make a dummy hgt.rsc file.
        hdict = ts.read_rsc(hgtf) 
        ohgtfrsc = os.path.join(h5dir,ohgtf)
        hout = open(ohgtfrsc+'.rsc','w')
        hout.write('WIDTH\t\t%d\n'%(nwid))
        hout.write('FILE_LENGTH\t\t%d\n'%(nlen))
        dazpix = np.float(hdict['AZIMUTH_PIXEL_SIZE'])*lks
        drgpix = np.float(hdict['RANGE_PIXEL_SIZE'])*lks
        for k in xrange(4):
            hout.write('LAT_REF%1d\t\t%s\n'%(k+1,hdict['LAT_REF%d'%(k+1)]))
            hout.write('LON_REF%1d\t\t%s\n'%(k+1,hdict['LON_REF%d'%(k+1)]))

        hout.write('AZIMUTH_PIXEL_SIZE\t\t%f\n'%(dazpix))
        hout.write('RANGE_PIXEL_SIZE\t\t%f\n'%(drgpix))
        hout.close()

    g=f.create_dataset('cmask',data=cmask)
    g.attrs['help'] = 'Common mask for pixels.'

    g = f.create_dataset('bperp',data=bperp)
    g.attrs['help'] = 'Array of baseline values.'

    g = f.create_dataset('Jmat',data=Jmat)
    g.attrs['help'] = 'Connectivity matrix [-1,1,0]'

    g = f.create_dataset('tims',data=tims)
    g.attrs['help'] = ' Array of SAR acquisition times.'

    g = f.create_dataset('usat',data=usat)
    g.attrs['help'] = 'Satellite sensor name for each SAR acquisition.'

    g = f.create_dataset('dates',data=days)
    g.attrs['help'] = 'Ordinal values of SAR acquisition dates.'
    f.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
