'''Interface for reading DORIS output files.

.. author:
 
    Piyush Agram <piyush@gps.caltech.edu>
    Batuhan Osmanoglu <batu@gi.alaska.edu>
     
.. Classes:
   * doris : Class object for reading DORIS output files.
   
'''

''' CHANGELOG:
   20121217: Most of the class methods are deprecated and replaced with methods from adore module.
'''
import numpy as np
import adore

class doris:
    '''Class object for reading DORIS output files.'''
    def __init__(self, fname):
        #self.dict = {}
        #self.read(fname)
        self.dict=adore.res2dict( fname );
        self.obj=adore.dict2obj(self.dict);

    @staticmethod
    def readtillstar(fid):
        '''Moves the file pointer to next line starting with *'''
        while(fid):
            line = fid.readline()
            if line:
                if line[0] == "*":
                    return False
            else:
                return True

    @staticmethod
    def getmodname(fid):
        '''Reads the module name starting with _Start_'''
        line = fid.readline()
        line = line.rstrip()
        parts = line.split('_')
        nparts = len(parts)
        mods = ''.join(parts[2:])
        modname = mods.split(':')[0]
        return modname

    @staticmethod
    def fixline(line):
        '''Reads a line of header information and splits into a dictionary key and value.'''
        parts = line.split(':')
        if len(parts) < 2:
            return None

        for kk in xrange(len(parts)):
            parts[kk] = ''.join(parts[kk].split())
        return parts

    def read(self,fname):
        '''Reads a doris interferogram.out file into a dictionary of dicts. Every processing stage represents a dictionary.'''

        fid = open(fname,'r')
        
        endoffile = False

        while (endoffile==False):
            endoffile = self.readtillstar(fid)
            if not endoffile:
                mname = self.getmodname(fid)
                endoffile = self.readtillstar(fid)
                if mname not in ('comprefphase','leaderdatapoints'):
                    self.dict[mname] = {}
                    flag = True
                    while flag:
                        line = fid.readline()
                        if line[0]=='*':
                            flag=False
                        else:
                            parts = self.fixline(line)
                            if parts is not None:
                                self.dict[mname][parts[0]] = ''.join(parts[1:])

                else:
                    endoffile = self.readtillstar(fid)

                endoffile = self.readtillstar(fid)
                endoffile = self.readtillstar(fid)

        
        fid.close()

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
