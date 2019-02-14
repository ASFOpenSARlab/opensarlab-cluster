#!/usr/bin/env python3
import argparse
import isce
import isceobj
import numpy as np
import shelve
import os
import datetime 
from isceobj.Constants import SPEED_OF_LIGHT
from isceobj.Util.Poly2D import Poly2D

def cmdLineParse():
    '''
    Command line parser.
    '''

    parser = argparse.ArgumentParser( description='Create DEM simulation for merged images')
    parser.add_argument('-a','--alks', dest='alks', type=int, default=1,
            help = 'Number of azimuth looks')
    parser.add_argument('-r','--rlks', dest='rlks', type=int, default=1,
            help = 'Number of range looks')
    parser.add_argument('-d', '--dem', dest='dem', type=str, required=True,
            help = 'Input DEM to use')
    parser.add_argument('-m', '--master', dest='master', type=str, required=True,
            help = 'Dir with master frame')
    parser.add_argument('-o', '--output', dest='outdir', type=str, required=True,
            help = 'Output directory')
    parser.add_argument('-n','--native', dest='nativedop', action='store_true',
            default=False, help='Products in native doppler geometry instead of zero doppler')
    parser.add_argument('-l','--legendre', dest='legendre', action='store_true',
            default=False, help='Use legendre interpolation instead of hermite')
    parser.add_argument('-f', '--full', dest='full', action='store_true',
            default=False, help='Generate all topo products - masks etc')

    return parser.parse_args()

class Dummy(object):
    pass

def runTopo(info, demImage, dop=None, 
        nativedop=False, legendre=False, full=False):
    from zerodop.topozero import createTopozero
    from isceobj.Planet.Planet import Planet

    if not os.path.isdir(info.outdir):
        os.mkdir(info.outdir)

    #####Run Topo
    planet = Planet(pname='Earth')
    topo = createTopozero()
    topo.slantRangePixelSpacing = info.slantRangePixelSpacing
    topo.prf = info.prf
    topo.radarWavelength = info.radarWavelength
    topo.orbit = info.orbit
    topo.width = info.width // info.numberRangeLooks
    topo.length = info.length //info.numberAzimuthLooks
    topo.wireInputPort(name='dem', object=demImage)
    topo.wireInputPort(name='planet', object=planet)
    topo.numberRangeLooks = info.numberRangeLooks
    topo.numberAzimuthLooks = info.numberAzimuthLooks
    topo.lookSide = info.lookSide
    topo.sensingStart = info.sensingStart + datetime.timedelta(seconds = ((info.numberAzimuthLooks - 1) /2) / info.prf) 
    topo.rangeFirstSample = info.rangeFirstSample + ((info.numberRangeLooks - 1)/2) * info.slantRangePixelSpacing

    topo.demInterpolationMethod='BIQUINTIC'
    if legendre:
        topo.orbitInterpolationMethod = 'LEGENDRE'

    topo.latFilename = os.path.join(info.outdir, 'lat.rdr')
    topo.lonFilename = os.path.join(info.outdir, 'lon.rdr')
    topo.losFilename = os.path.join(info.outdir, 'los.rdr')
    topo.heightFilename = os.path.join(info.outdir, 'z.rdr')
    if full:
        topo.incFilename = os.path.join(info.outdir, 'inc.rdr')
        topo.maskFilename = os.path.join(info.outdir, 'mask.rdr')

    if nativedop and (dop is not None):

        try:
            coeffs = dop._coeffs
        except:
            coeffs = dop

        doppler = Poly2D()
        doppler.setWidth(info.width // info.numberRangeLooks)
        doppler.setLength(info.length // info.numberAzimuthLooks)
        doppler.initPoly(rangeOrder = len(coeffs)-1, azimuthOrder=0, coeffs=[coeffs])
    else:
        print('Zero doppler')
        doppler = None

    topo.polyDoppler = doppler

    topo.topo()
    return

def runSimamp(outdir, hname='z.rdr'):
    from iscesys.StdOEL.StdOELPy import create_writer
    
    #####Run simamp
    stdWriter = create_writer("log","",True,filename='sim.log')
    objShade = isceobj.createSimamplitude()
    objShade.setStdWriter(stdWriter)


    hgtImage = isceobj.createImage()
    hgtImage.load(os.path.join(outdir, hname) + '.xml')
    hgtImage.setAccessMode('read')
    hgtImage.createImage()

    simImage = isceobj.createImage()
    simImage.setFilename(os.path.join(outdir, 'simamp.rdr'))
    simImage.dataType = 'FLOAT'
    simImage.setAccessMode('write')
    simImage.setWidth(hgtImage.getWidth())
    simImage.createImage()

    objShade.simamplitude(hgtImage, simImage, shade=3.0)

    simImage.renderHdr()
    hgtImage.finalizeImage()
    simImage.finalizeImage()


def extractInfo(frame, inps):
    '''
    Extract relevant information only.
    '''

    info = Dummy()

    ins = frame.getInstrument()

    info.sensingStart = frame.getSensingStart()

    info.lookSide = frame.instrument.platform.pointingDirection
    info.rangeFirstSample = frame.startingRange
    info.numberRangeLooks = inps.rlks
    info.numberAzimuthLooks = inps.alks

    fsamp = frame.rangeSamplingRate

    info.slantRangePixelSpacing = 0.5 * SPEED_OF_LIGHT / fsamp
    info.prf = frame.PRF
    info.radarWavelength = frame.radarWavelegth
    info.orbit = frame.getOrbit()
    
    info.width = frame.getNumberOfSamples() 
    info.length = frame.getNumberOfLines() 

    info.sensingStop = frame.getSensingStop()
    info.outdir = inps.outdir

    return info

if __name__ == '__main__':

    
    inps = cmdLineParse()

    db = shelve.open(os.path.join(inps.master, 'data'))
    frame = db['frame']
    try:
        doppler = db['doppler']
    except:
        doppler = frame._dopplerVsPixel

    db.close()

    ####Setup dem
    demImage = isceobj.createDemImage()
    demImage.load(inps.dem + '.xml')
    demImage.setAccessMode('read')

    info = extractInfo(frame, inps)
    runTopo(info,demImage,dop=doppler,
            nativedop=inps.nativedop, legendre=inps.legendre,
            full=inps.full)
    runSimamp(inps.outdir)




