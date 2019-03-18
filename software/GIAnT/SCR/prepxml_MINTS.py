#!/usr/bin/env python
'''Example script for creating XML files for use with the MInTS processing chain. This script is supposed to be copied to the working directory and modified as needed.'''


import tsinsar as ts
import argparse
import numpy as np

def parse():
    parser= argparse.ArgumentParser(description='Preparation of XML files for setting up the processing chain. Check tsinsar/tsxml.py for details on the parameters.')
    parser.parse_args()


parse()
g = ts.TSXML('data')
g.prepare_data_xml('example',xlim=[30,380],ylim=[100,600],rxlim=[30,50],rylim=[50,70],latfile='lat.map',lonfile='lon.map',hgtfile='hgt.map',inc=21.,cohth=0.2,demfmt='RMG',chgendian='False',masktype='f4')
g.writexml('data.xml')


g = ts.TSXML('params')
g.prepare_mints_xml(netramp=True,atmos='ECMWF',demerr=False,uwcheck=False,regu=True,masterdate='19920604',minscale=2,wvlt='meyer')
g.writexml('mints.xml')


############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
