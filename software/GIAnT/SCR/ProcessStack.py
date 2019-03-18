#!/usr/bin/env python
'''Reads the input interferograms and processes it before time-series
inversion. Includes atmospheric model based phase corrections and 
network deramping.The results are stored in a HDF5 file.

.. author:

    Piyush Agram <piyush@gps.caltech.edu> 
    modifications:
        DB  AUG 2017    try to import pyaps'''

import numpy as np
import tsinsar as ts
import sys
import h5py
import matplotlib.pyplot as plt
import datetime as dt
import os
import collections
import argparse
try:                                                                                                                                                                  
    import pyaps as pa
except:
    pass

########Command line parser
def parse():
    parser = argparse.ArgumentParser(description='Processes the stack before inversion - Deramping + Atmospheric correction.')
    parser.add_argument('-i', action='store', default='RAW-STACK.h5', dest='iname', help='To override the default Input HDF5 file. Default: RAW-STACK.h5', type=str)
    parser.add_argument('-o', action='store', default='PROC-STACK.h5', dest='oname', help='To override the default Output HDF5 file. Default: PROC-STACK.h5', type=str)
    parser.add_argument('-x', action='store', default='data.xml', dest='dxml', help='To override the default data xml file. Default: data.xml', type=str)
    parser.add_argument('-p', action='store', default='sbas.xml', dest='pxml', help='To override the default sbas xml file. Default: sbas.xml', type=str)
    inps = parser.parse_args()
    return inps

class dummy:
    pass

if __name__ == '__main__':
    ###########The main code that reads data and processes stacks#######
    inps = parse()
    logger=ts.logger

    #########Reading the parameters.
    dpars = ts.TSXML(inps.dxml,File=True)
    ppars = ts.TSXML(inps.pxml,File=True)

    ##########Get the directories
    h5dir = (dpars.data.dirs.h5dir)
    figdir = (dpars.data.dirs.figsdir)
    atmdir = (dpars.data.dirs.atmosdir)

    ts.makedir([atmdir,figdir,h5dir])


    inname = os.path.join(h5dir,inps.iname)
    logger.info('Input h5file: %s'%(inname))
    f = h5py.File(inname)
    bperp = f['bperp'].value
    tims = f['tims'].value
    Jmat = f['Jmat'].value
    dates = f['dates'].value
    igram = f['igram']
    mask  = f['cmask'].value


    ######Dimensions of the problem
    Nifg = Jmat.shape[0]
    Nsar = Jmat.shape[1]
    fwid = igram.shape[2]
    flen = igram.shape[1]

    #####Reference region for the stack
    Ry0 = (dpars.data.subimage.rymin)
    Ry1 = (dpars.data.subimage.rymax)
    Rx0 = (dpars.data.subimage.rxmin)
    Rx1 = (dpars.data.subimage.rxmax)

    outname = os.path.join(h5dir,inps.oname)
    if os.path.exists(outname):
        os.remove(outname)
        logger.info('Deleting previous %s'%(outname))

    logger.info('Output h5file: %s'%(outname))

    fout = h5py.File(outname)
    fout.attrs['help'] = 'Processed stack of interferograms - Atmospheric corrections + Referencing + Deramping' 


    ######Atmospheric corrections
    atmos = (ppars.params.proc.atmos)


    if atmos in ('ECMWF','ERA','NARR','MERRA'):
        #####
        utc = (dpars.data.master.utc)
        latm = (dpars.data.master.latfile)
        latf = (dpars.data.subimage.latfile)
        lonf = (dpars.data.subimage.lonfile)
        incf = (dpars.data.subimage.incidence)
        hgtf = (dpars.data.subimage.hgtfile)

        if latm is None:
            latf is None
        
        if atmos in ('NARR'):
            period = 3    #3 hourly
        else:
            period = 6    #6 hourly

        logger.info('Weather model data every %2d hours'%(period))
        
        hr = np.int(period*np.round(utc/(period*3600.0)))
        
        addday = np.int(np.floor(hr/24))
        hr = hr%24    

        #####Dates list.
        daylist = ts.datestr((dates+addday).astype(np.int))
       


        #####Automated download
        if atmos in ('ECMWF'):
            logger.info('Getting ECMWF')
            if hr>10:
                    flist = pyaps.ECMWFdload(daylist,'%2d'%(hr),atmdir)
            else:
                    flist = pyaps.ECMWFdload(daylist,'0%d'%(hr),atmdir)
        elif atmos in ('NARR'):
            logger.info('Getting NARR')
            if hr>10:
                    flist = pyaps.NARRdload(daylist,'%2d'%(hr),atmdir)
            else:
                    flist = pyaps.NARRdload(daylist,'0%d'%(hr),atmdir)
        elif atmos in ('ERA'):
            logger.info('Getting ERA-Interim')
            if hr>10:
                    flist = pyaps.ERAdload(daylist,'%2d'%(hr),atmdir)
            else:
                    flist = pyaps.ERAdload(daylist,'0%d'%(hr),atmdir)
        elif atmos in ('MERRA'):
            logger.info('Getting MERRA')
            if hr>10:
                    flist = pyaps.MERRAdload(daylist,'%2d'%(hr),atmdir)
            else:
                    flist = pyaps.MERRAdload(daylist,'0%d'%(hr),atmdir)

        ######Create SAR phase screens.
        aps = fout.create_dataset("sar_aps",(Nsar,flen,fwid),'f')
        aps.attrs['help'] = 'Atmospheric phase screen for each of the SAR scenes in mm.'

        logger.info('ESTIMATING Phase screen for SAR scenes')
        
        phs = np.zeros((flen,fwid))
        progb = ts.ProgressBar(maxValue=len(flist))
        for k in xrange(len(flist)):
            atmobj = pyaps.PyAPS_rdr(flist[k],os.path.join(h5dir,hgtf),grib=atmos,demfmt='HGT')

            if latf is not None:
                atmobj.getgeodelay(phs,lat=os.path.join(h5dir,latf),lon=os.path.join(h5dir,lonf),inc=incf)
            else:
                atmobj.getdelay(phs,inc=incf)

            del atmobj
            
            sub = phs[Ry0:Ry1,Rx0:Rx1]
            refph = ts.nanmean(sub)
            aps[k,:,:] = 1000.*(phs-refph) #Convert to mm
            progb.update(k,every=3)

        progb.close()

    elif atmos == 'TROPO':

        hgtf = (dpars.data.subimage.hgtfile)
        tminscl = (ppars.params.proc.tropomin)
        tmaxscl = (ppars.params.proc.tropomax)
        tlooks = (ppars.params.proc.tropolooks)

        logger.info('Applying empirical tropospheric corrections.')

        dem = ts.load_flt(os.path.join(h5dir,hgtf), fwid, flen, quiet=True)

        tstack = ts.STACK(igram, conn=Jmat)
        
        aps = fout.create_dataset("sar_aps",(Nsar,flen,fwid),'f')
        aps.attrs['help'] = 'Atmospheric phase screen for each of the SAR scenes in mm.'

        astack = ts.STACK(aps)
       
        logger.info('Inverting parameters and estimating phase screen for SAR scenes') 
        tstack.tropocorrect(dem, astack, minscale=tminscl,maxscale=tmaxscl, looks=tlooks)


        ######Correct interferograms.
    if atmos is not None:

        cigram = fout.create_dataset("igram_aps",(Nifg,flen,fwid),'f')
        cigram.attrs['help'] = 'Atmosphere corrected interferogram stack'

        logger.info('Correcting IFGs')
        fadir = os.path.join(figdir,'Atmos')
        ts.makedir([fadir])
        logger.info('PNG preview dir: %s'%fadir) 
        progb = ts.ProgressBar(maxValue=Nifg)

        for k in xrange(Nifg):
            row = Jmat[k,:]
            mast = np.where(row == 1)
            slav = np.where(row == -1)

            ph1 = aps[mast,:,:]
            ph2 = aps[slav,:,:]

            corr = np.squeeze(ph2-ph1)

            ifg = igram[k,:,:]
            ifg2 = ifg-corr
            cigram[k,:,:] = ifg2
            imname = '%s/I%03d.png'%(fadir,k+1)
            idict = collections.OrderedDict()
            idict['Original'] = ifg
            idict['Correction'] = corr
            idict['Corrected'] = ifg2
            ts.imagemany(idict,save=imname,master='Original')
            progb.update(k,every=5)

        progb.close()

    netramp = (ppars.params.proc.netramp)
    gpsramp = (ppars.params.proc.gpsramp)



    #######Use GPS to correct IFGs.
    if gpsramp:

        hdg = (dpars.data.master.heading)
        gpstype = (ppars.params.proc.gpstype)
        stntype = (ppars.params.proc.stntype)
        stnlist = (ppars.params.proc.stnlist)
        gpspreproc = (ppars.params.proc.gpspreproc)
        gpsmodel = (ppars.params.proc.gpsmodel)
        gpspath  = (ppars.params.proc.gpspath)
        gpspad = (ppars.params.proc.gpspad)
        gpsmin = (ppars.params.proc.gpsmin)
        gpsvert = (ppars.params.proc.gpsvert)
        latf = (dpars.data.subimage.latfile)
        lonf = (dpars.data.subimage.lonfile)
        incf = (dpars.data.subimage.incidence)

        dcigram = fout.create_dataset('figram',(Nifg,flen,fwid),'f')
        if atmos is None:
            logger.info('Using RAW Igram for GPS deramping')
            inigram = igram
            dcigram.attrs['help'] = 'GPS deramped interferograms.'

        else:
            logger.info('Using Atmos corrected Igram for GPS deramping')
            inigram = cigram
            dcigram.attrs['help'] = 'GPS deramped + atmosphere corrected interferograms.'

        if gpstype=='sopac':
            gpsfilestyle=True
            logger.info('Taking GPS solutions from SOPAC directory: %s'%(gpspath))
            if not stntype:
                logger.info('Using SOPAC generated file for station locations: %s'%stnlist)
            else:
                logger.info('Using three column station location file: %s'%stnlist)

        elif gpstype=='velocity':
            gpsfilestyle='velocity'
            logger.info('Taking GPS velocities from file %s'%stnlist)
            stntype = 'velocity'
        else:
            raise ValueError('Undefined GPS type in XML file')

        mynet = ts.gps.GPS(stnlist,fourcol=stntype)
        mynet.lltoij(flen, fwid, latfile=os.path.join(h5dir,latf),
                lonfile=os.path.join(h5dir,lonf))

        if isinstance(incf,str):
            mynet.setlos(hdg, incf, flen=flen, fwid=fwid)
        else:
            mynet.setlos(hdg, incf)

        if gpstype in ('sopac'):
                mynet.readgps(gpspath, usevert=gpsvert, model=gpsmodel, preprocess=gpspreproc)
                disp, disperr = mynet.get_ts(dates.astype(np.int), model=gpsmodel)
        elif gpstype in ('velocity'):
                disp, disperr = mynet.buildtsvelo(tims)
            
        # Container for SAR GPS measurements.
        gpssar = dummy()

        logger.info('Correcting RAMP using GPS')

        gpssar.xi = mynet.xi
        gpssar.yi = mynet.yi
        gpssar.disp = disp
        gpssar.disperr = disperr
           
        rstack = ts.STACK(inigram,conn=Jmat,baseline=bperp)
        rstack.setmask(mask)
        rstack.setref([Ry0,Ry1,Rx0,Rx1])

        drstack = ts.STACK(dcigram,conn=Jmat,baseline=bperp)
        rstack.deramp_gps(drstack,gpssar,network=netramp,neigh=gpspad,minnum=gpsmin)
        ramparr = drstack.ramparr



    if netramp and not gpsramp:
        if atmos is None:
            stack = ts.STACK(igram,conn=Jmat,baseline=bperp)
        else:
            stack = ts.STACK(cigram,conn=Jmat,baseline=bperp)

        stack.setmask(mask) ###Can be more conservative mask here.
        stack.setref([Ry0,Ry1,Rx0,Rx1])


        dcigram = fout.create_dataset('figram',(Nifg,flen,fwid),'f')
        if atmos:
            dcigram.attrs['help'] = 'Deramped + atmosphere corrected interferograms.'
        else:
            dcigram.attrs['help'] = 'Deramped interferograms.'

        dstack = ts.STACK(dcigram,conn=Jmat,baseline=bperp)
        dstack.setref([Ry0,Ry1,Rx0,Rx1])
        stack.deramp(dstack)
        ramparr = dstack.ramparr


    if netramp or gpsramp:
        frdir = os.path.join(figdir,'Ramp')
        ts.makedir([frdir])
        logger.info('PNG preview of Deramped images: %s'%frdir)
        progb = ts.ProgressBar(maxValue=Nifg)
        idict = collections.OrderedDict()
        for k in xrange(Nifg):
            imname = '%s/I%03d.png'%(frdir,k+1)
            if atmos is None:
                ifg = igram[k,:,:]
            else:
                ifg = cigram[k,:,:]

            ifg2 = dcigram[k,:,:]
            
            idict['Original'] = ifg
            idict['Deramped'] = ifg2
            ts.imagemany(idict,save=imname,master='Original')
            progb.update(k, every=5)

        progb.close()

        g = fout.create_dataset('ramp',data=ramparr)
        g.attrs['help'] = 'Array of ramp coefficients'

    g = fout.create_dataset('Jmat',data=Jmat)
    g.attrs['help'] = 'Connectivity matrix [-1,1,0]'

    g = fout.create_dataset('bperp',data=bperp)
    g.attrs['help'] = 'Perpendicular baseline array'

    g = fout.create_dataset('tims',data=tims)
    g.attrs['help'] = 'Array of SAR acquisition times in years.'

    g = fout.create_dataset('dates',data=dates)
    g.attrs['help'] = 'Array of ordinal values for SAR acquisition dates.'

    g = fout.create_dataset('cmask',data=mask)
    g.attrs['help'] = 'Common mask for pixels.'

    fout.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
