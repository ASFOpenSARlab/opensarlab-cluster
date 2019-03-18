#!/usr/bin/env python3

import isce
from isceobj.Sensor import createSensor
import shelve
import argparse
import glob
from isceobj.Util import Poly1D
from isceobj.Planet.AstronomicalHandbook import Const
import os
from mroipac.dopiq.DopIQ import DopIQ
from isceobj.Util.decorators import use_api

import copy

def cmdLineParse():
    '''
    Command line parser.
    '''

    parser = argparse.ArgumentParser(description='Unpack CSK SLC data and store metadata in pickle file.')
    parser.add_argument('-i','--input', dest='h5dir', type=str,
            required=True, help='Input CSK directory')
    parser.add_argument('-o', '--output', dest='slcdir', type=str,
            required=True, help='Output SLC directory')
    parser.add_argument('-r', '--resamp', dest='resamp', action='store_true',
            default=False, help='FBD2FBS')
    parser.add_argument('-m', '--mult', dest='multiple',
            action='store_true', default=False,
            help='Use multiple frames')

    return parser.parse_args()

@use_api
def unpack(hdf5, slcname, multiple=False, resamp=False):
    '''
    Unpack HDF5 to binary SLC file.
    '''
    if not os.path.isdir(slcname):
        os.mkdir(slcname)

    date = os.path.basename(slcname)
    obj = createSensor('ALOS')
    obj.configure()

    if multiple:
        print('Trying multiple subdirs...')
        obj._imageFileList = glob.glob(os.path.join(hdf5, '*', 'IMG*'))
        obj._leaderFileList = glob.glob(os.path.join(hdf5, '*', 'LED*'))

        if (len(obj._imageFileList) == 0) or (len(obj._leaderFileList) == 0):
            print('No imagefiles / leaderfiles found in sub-dirs. Trying same directory ...')
            obj._imageFileList = glob.glob(os.path.join(hdf5, 'IMG*'))
            obj._leaderFileList = glob.glob(os.path.join(hdf5, 'LED*'))

    else:
        imgname = glob.glob(os.path.join(hdf5,'IMG*'))[0]
        ldrname = glob.glob(os.path.join(hdf5, 'LED*'))[0]



        obj._leaderFileList = [ldrname]
        obj._imageFileList = [imgname]

    obj.output = os.path.join(slcname, date+'.raw')

    print(obj._leaderFileList)
    print(obj._imageFileList)
    print(obj.output)
   
    if resamp:
        obj._resampleFlag = 'dual2single'

    obj.extractImage()
    obj.frame.getImage().renderHdr()


        #####Estimate doppler
    dop = DopIQ()
    dop.configure()

    img = copy.deepcopy(obj.frame.getImage())
    img.setAccessMode('READ')

    dop.wireInputPort('frame', object=obj.frame)
    dop.wireInputPort('instrument', object=obj.frame.instrument)
    dop.wireInputPort('image', object=img)

    dop.calculateDoppler()
    dop.fitDoppler()
    fit = dop.quadratic
    coef = [fit['a'], fit['b'], fit['c']]

    obj.frame._dopplerVsPixel = [x*obj.frame.PRF for x in coef]

    pickName = os.path.join(slcname, 'raw')
    with shelve.open(pickName) as db:
        db['frame'] = obj.frame

if __name__ == '__main__':
    '''
    Main driver.
    '''

    inps = cmdLineParse()
    if inps.slcdir.endswith('/'):
        inps.slcdir = inps.slcdir[:-1]

    if inps.h5dir.endswith('/'):
        inps.h5dir = inps.h5dir[:-1]

    unpack(inps.h5dir, inps.slcdir, 
            multiple=inps.multiple,
            resamp=inps.resamp)
