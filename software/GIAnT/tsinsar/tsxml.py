'''XML interface for reading the processing parameter file. 
We use lxml.etree to create template XML files and 
lxml.objectify to read the files. 

.. author:

    Piyush Agram <piyush@gps.caltech.edu>
    Batuhan Osmanoglu <batu@gi.alaska.edu>
    
.. Dependencies:

    numpy, tsio, json, os.path, lxml.etree, lxml.objectify
    
.. Comments:
    
    Pylint checked. Sticking with names.'''
    
'''CHANGELOG
   20121219: Putting objectify.get in try/except block. Otherwise can't read None from xml file for int etc.
'''    
    
import numpy as np
import tsio
import doris
import json
from lxml import etree as ET
from lxml import objectify as OB
import logmgr
import datetime

logger = logmgr.logger('giant')

class Container:
    """Dummy container class. Children contain useful values."""
    pass

def objectify(parent, inp):
    def get(obj):
        '''Function provides a means of interpreting the data in the input
        XML file. All the XML entries in our XML files have value, type and
        help attributes.
    
        .. Args:
        
            * obj    ->  Any input object from our xml file with type and
            value fields.

        .. Returns:
        
            * value  -> Returns the value of the object. The data type of the
            returned object is determined by type attribute. '''
  
        if hasattr(obj, 'value') and hasattr(obj, 'type'):
            dtype = obj.type.text
            try:
                ###Convert to float and then int for correct behavior
                if dtype == 'INT':
                    val = np.int(np.float(obj.value.text))
                elif dtype == 'FLOAT':
                    val = np.float(obj.value.text)
                elif dtype == 'BOOL':
                    val = (obj.value.text == 'True')
                elif dtype in ('DICT', 'LIST'):
                    val = json.loads(obj.value.text) 
                elif dtype == 'INTLIST':
                    val = json.loads(obj.value.text)
                    for kk in xrange(length(val)):
                        val[kk] = np.int(np.float(val[kk]))
                elif dtype == 'FLOATLIST':
                    val = json.loads(obj.value.text)
                    for kk in xrange(length(val)):
                        val[kk] = np.float(val[kk])
                else:
                    val = obj.value.text
            except:
                val = None
            return val
        else:
            raise AttributeError, "Undefined value attribute."

    keys = inp.__dict__.keys()
    if 'value' in keys:
        h = get(inp)

        setattr(parent, inp.tag, h)
    else:
        h = Container()
        for gg in inp.iterchildren():
            objectify(h, gg)

        setattr(parent, inp.tag, h) 
            

class TSXML:
    '''Class that deals with creating and reading XML files.'''
    
    def __init__(self, name, File=False):
        ''' Initializes the XML class.
        
        .. Args:
        
            * name    ->  Name of the input or output file depending on 
            the keyword argument.
            
        .. Kwargs:
        
            * File    -> If False (Default), it is assumed that a new XML file
            will be created and written to file. If True, assumed that we are 
            reading from an XML File.
        
        .. Returns:
            
            None'''
        
        if not File:
            self.root = ET.Element(name)
        else:
            ######Init from file.
            self.parsexml(name)

    def parsexml(self, fname):
        '''Reads an XML file and makes it a simple usable object.
        
        .. Args:
            
            * fname     -> Name of the input XML file.
            
        .. Returns:
            
            None'''

        fin = open(fname)
        inp = OB.fromstring(fin.read())
        fin.close()
        objectify(self, inp)

    
    def addsubelement(self, master, name, value, dtype, helpstr=None):
        '''Adds a subelement to a specified node with given value,type and
        help string.
        
        .. Args:
        
            * master    -> etree Element that represents the parent node.
            * name      -> String representing the name of the field.
            * dtype     -> String representing dtype of field.
        
        .. Kwargs:
            
            * helpstr   -> String describing the field.
            
        .. Returns:
            
            None'''
        assert dtype in ('INT', 'FLOAT', 'BOOL', 'STR',
                'DICT', 'LIST'), 'Unknown value type.'
        elem = ET.SubElement(master, name)
        val = ET.SubElement(elem, 'value')
        if dtype in ('STR'):
            val.text = value
        elif dtype in ('DICT','LIST'):
            val.text = json.dumps(value)
        else:
            val.text = str(value)

        typ = ET.SubElement(elem, 'type')
        typ.text = dtype

        if helpstr is not None:
            desc = ET.SubElement(elem, 'help')
            desc.text = helpstr

        logger.info('Creating Field: %s , Value=%s, Type=%s'%(name,val.text,typ.text))

    def addnode(self, master, name):
        '''Adds a new XML node to location specified by master.
        
        .. Args:
            
            * master   -> etree Element that represents the parent node.
            * name     -> Name of the new node to be added.  
        
        .. Returns:
            
            None'''
        
        elem = ET.SubElement(master, name)
        return elem

    def writexml(self, outname):
        '''Writes the XML etree root to an output XML file.
        
        .. Args:
        
            * outname     -> Name of the output XML file.
            
        .. Returns:
            None'''
        
        tree = ET.ElementTree(self.root)
        tree.write(outname, pretty_print=True, xml_declaration=False)


    def prepare_data_xml(self, fname, proc='RPAC',looks=1, cohth=0., mask='', 
            xlim=None, ylim=None, rxlim=None, rylim=None, latfile='',
                     lonfile='', hgtfile='', inc=23.,h5dir='Stack',
                     atmosdir='Atmos',figsdir='Figs',respdir='RESP',
                     unwfmt='RMG',demfmt='RMG',corfmt='RMG',
                     chgendian=False,masktype='f4',
                     endianlist=['UNW','COR','HGT']):
        '''Creates a template XML File for reading in data and preparing
        it for time-series analysis. This is intended to store
        
        .. Args:
        
            * fname        ->   str or LIST depending on the insar products
            
            * ROI-PAC -> str for unw file (no .rsc in name) used to build structure.
            * ISCE    -> str for insarProc.xml file 
            * DORIS   -> List of two strs - ['interferogram.out','master.res']
            * GMT     -> List of two strs - ['IMAGE.PRM','unwrap.grd']
	    * GAMMA   -> str for .par file used to build structure
            
        .. Kwargs:
       
            * proc     -> Processor used ('RPAC','DORIS','ISCE','GMT', 'GAMMA')
            * looks    -> Number of additional looks
            * cohth    -> Coherence threshold for SBAS pixel selection
            * mask     -> Common mask for pixels
            * xlim     -> Cropping limits in Range direction
            * ylim     -> Cropping limits in Azimuth direction
            * rxlim    -> Reference region limits in Range direction
            * rylim    -> Reference region limits in Azimuth direction
            * latfile  -> Latitude file
            * lonfile  -> Longitude file
            * hgtfile  -> Altitude file
            * inc      -> Const float or incidence angle file
        
        .. Returns:
        
            None'''
       
        if proc not in ('RPAC','DORIS','ISCE','GMT', 'GAMMA'):
            raise ValueError('Undefined SAR processor.')

        if proc=='RPAC':
            logger.info('Using ROI-PAC products.')
            rdict = tsio.read_rsc(fname)
            wid = np.int(rdict['WIDTH'])
            lgth = np.int(rdict['FILE_LENGTH'])
            wvl = np.float(rdict['WAVELENGTH'])
            hdg = np.float(rdict['HEADING_DEG'])
            utc = np.int(np.float(rdict['CENTER_LINE_UTC']))

        elif proc=='DORIS':
            import dateutil
            parser=dateutil.parser

            logger.info('Reading DORIS products.')
            if len(fname) == 1:
                raise ValueError('For doris products, two files - interferogram.out and master.res are needed as inputs.')
            rdict = doris.doris(fname[0])
            iobj = rdict.obj 
            # when doing super master stacks with doris, it is possible that subtrrefdem is done 
            # at the resampling step. unwrap is a safer bet to exist.
            wid = iobj.unwrap.Number_of_pixels #np.int(rdict.dict['subtrrefdem']['Numberofpixels(multilooked)'])
            lgth = iobj.unwrap.Number_of_lines #np.int(rdict.dict['subtrrefdem']['Numberofpixels(multilooked)'])
            rdict = doris.doris(fname[1])
            mobj = rdict.obj
            wvl = mobj.readfiles.Radar_wavelength #np.float(rdict.dict['readfiles']['Radar_wavelength(m)'])
            #utc1 = rdict.dict['readfiles']['First_pixel_azimuth_time(UTC)']
            #utc1 = int(float(utc1.split()[1]))
            utc1 = parser.parse(mobj.readfiles.First_pixel_azimuth_time.split()[1])
            #utc = 3600*(utc1)+60*(utc1/100 - 100*(utc1/10000)) + (utc1-100*(utc1/100))
            utc = 3600*utc1.hour + 60*utc1.minute + utc1.second # + utc1.microsecond*1.0e-6
            hdg = iobj.coarse_orbits.alpha #-9999.0
            #logger.warning('Doris products do not include heading. Modify manually.')

        elif proc == 'ISCE':
            logger.info('Using ISCE Products.')
            rdict = tsio.read_isce_xml(fname) 
            #####If in radar coordinates
#            wid = np.int(rdict.runResamp_only.inputs.NUMBER_RANGE_BIN)
#            lgth = np.int(rdict.runResamp_only.inputs.NUMBER_LINES)

            #####For geo coordinates
            wid = np.int(rdict.runGeocode.outputs.GEO_WIDTH)
            lgth = np.int(rdict.runGeocode.outputs.GEO_LENGTH)
            hdg  = np.float(rdict.runTopo.inputs.PEG_HEADING) * 180.0/np.pi
            wvl = np.float(rdict.runTopo.inputs.RADAR_WAVELENGTH)
            utc1 = datetime.datetime.strptime(str(rdict.master.frame.SENSING_START), '%Y-%m-%d %H:%M:%S.%f')
            utc = 3600*utc1.hour + 60*utc1.minute + utc1.second
            logger.warning('ISCE products do not contain first line UTC. Modify manually.')

        elif proc == 'GMT':
            logger.info('Using GMTSAR products')
            if len(fname)==1:
                raise ValueError('For GMT products, two files - image.PRM and unwrap.grd are needed as inputs.')
            rdict = tsio.read_prm(fname[0])
            wvl = np.float(rdict['radar_wavelength'])
            utc1 = np.float(rdict['SC_clock_start'])
            utc = np.int((utc1-np.floor(utc1))*24*3600)
            hdg = -9999.0
            logger.warning('GMTSAR products do not include heading. Modify manually.')
            lgth, wid = tsio.get_grddims(fname[1])

	elif proc == 'GAMMA':
	    logger.info('Using GAMMA products')
	    rdict = tsio.read_par(fname)
	    wvl = 299792548.0/np.float(rdict['radar_frequency'])
	    utc = np.int(np.float(rdict['center_time']))
	    hdg = np.float(rdict['heading'])
	    lgth = np.int(rdict['azimuth_lines'])
	    wid  = np.int(rdict['range_samples'])



        ######master->proc
        desc = 'Processor used for generating the interferograms.'
        self.addsubelement(self.root, 'proc', proc, 'STR', desc)

        ###### <<<<  Master geometry >>>> ######
        master = self.addnode(self.root,'master')


        ######master->width
        desc = 'WIDTH of the IFGs to be read in.'
        self.addsubelement(master, 'width', wid, 'INT', desc)

        ######master->file_length
        desc = 'FILE_LENGTH of the IFGS to be read in.'
        self.addsubelement(master, 'file_length', lgth, 'INT', desc)

        ######master->wavelength
        desc = 'WAVELENGTH of the Stack. If combining sensors,' \
        'ensure that they are all converted to same units.'
        self.addsubelement(master, 'wavelength', wvl, 'FLOAT', desc)

        ######master->heading
        desc = 'Heading of the satellite in degrees. Manually adjust for Doris.'
        self.addsubelement(master, 'heading', hdg, 'FLOAT', desc)
        
        #######master->utc
        desc = 'Average time of acquisition in seconds of the day'
        self.addsubelement(master, 'utc', utc, 'INT', desc)

        ######master->mask
        desc = 'Common mask applied to all the images. Useful for' \
        'filtering out water bodies.'
        self.addsubelement(master, 'mask', mask, 'STR', desc)
        
        ######master->cthresh
        desc = 'Coherence threshold for pixels to be included in analysis.'
        self.addsubelement(master, 'cthresh', cohth, 'FLOAT', desc)

        ######master->latfile
        desc = 'Latitude file. Same size as IFGs.'
        self.addsubelement(master, 'latfile', latfile, 'STR', desc)

        ######master->lonfile
        desc = 'Longitude file. Same size as IFGs.'
        self.addsubelement(master, 'lonfile', lonfile, 'STR', desc)

        ######master->hgtfile
        desc = 'DEM height in radar coordinates. Same size as IFGs.'
        self.addsubelement(master, 'hgtfile', hgtfile, 'STR', desc)

        ######master->incidence
        desc = 'Incidence angle file. Same size as IFGs. Can be ' \
        'a constant float too.'
        if isinstance(inc, str):
            self.addsubelement(master, 'incidence', inc, 'STR', desc)
        else:
            self.addsubelement(master, 'incidence', inc, 'FLOAT', desc)


        ###### <<<<< Sub image >>>>
        ###### This is information on the image that is actually processed.
        master = self.addnode(self.root, 'subimage')

        ######sunimage->looks
        desc = 'Number of additional looks to be applied ' \
        'for time-series analysis'
        self.addsubelement(master, 'looks', looks, 'INT', desc)


        ####Dimensions of look down image
        nwid  = np.int(np.floor(wid/(looks*1.)))
        nlgth = np.int(np.floor(lgth/(looks*1.)))


        ####### subimage->width
        ####### subimage->xmin
        ####### subimage->xmax
        
        if (xlim is None):
            desc = 'WIDTH of the analyzed image'
            self.addsubelement(master, 'width', nwid, 'INT', desc)

            desc = 'START of the valid region in X. After taking looks.'
            self.addsubelement(master, 'xmin', 0, 'INT', desc)

            desc = 'END of the valid region in X. After taking looks.'
            self.addsubelement(master, 'xmax', nwid, 'INT', desc)

        else:

            nwid = xlim[1] - xlim[0]
            desc = 'WIDTH of the analyzed image'
            self.addsubelement(master, 'width', nwid, 'INT', desc)

            desc = 'START of the valid region in X. After taking looks.'
            self.addsubelement(master, 'xmin', xlim[0], 'INT', desc)

            desc = 'END of the valid region in X. After taking looks.'
            self.addsubelement(master, 'xmax', xlim[1], 'INT', desc)


        ####### subimage->length
        ####### subimage->ymin
        ####### subimage->ymax
        
        if (ylim is None):
            desc = 'LENGTH of the cropped image'
            self.addsubelement(master, 'length', nlgth, 'INT', desc)

            desc = 'START of the crop region in Y. After taking looks.'
            self.addsubelement(master, 'ymin', 0, 'INT', desc)

            desc = 'END of the crop region in Y. After taking looks.'
            self.addsubelement(master, 'ymax', nlgth, 'INT', desc)

        else:

            nlgth = ylim[1] - ylim[0]
            desc = 'LENGTH of the cropped image'
            self.addsubelement(master, 'length', nlgth, 'INT', desc)

            desc = 'START of the crop region in Y. After taking looks.'
            self.addsubelement(master, 'ymin', ylim[0], 'INT', desc)

            desc = 'END of the crop region in Y. After taking looks.'
            self.addsubelement(master, 'ymax', ylim[1], 'INT', desc)


        ######Reference region. In Lookdown image.
        ###### subimage->rxmin
        ###### subimage->rxmax
        ###### subimage->rymin
        ###### subimage->rymax
        
        if (rxlim is None) | (rylim is None):
            desc = 'Start of reference region in X. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rxmin', 0, 'INT', desc)

            desc = 'End of reference region in X. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rxmax', -1, 'INT', desc)

            desc = 'Start of reference region in Y. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rymin', 0, 'INT', desc)

            desc = 'End of reference region in Y. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rymax', -1, 'INT', desc)

        else:
            
            desc = 'Start of reference region in X. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rxmin', rxlim[0], 'INT', desc)

            desc = 'End of reference region in X. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rxmax', rxlim[1], 'INT', desc)

            desc = 'Start of reference region in Y. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rymin', rylim[0], 'INT', desc)

            desc = 'End of reference region in Y. After multilooking ' \
            'and cropping.'
            self.addsubelement(master, 'rymax', rylim[1], 'INT', desc)

        ####### subimage->latfile
        desc = 'Latitude file for the cropped and multilooked image.'
        self.addsubelement(master, 'latfile', 'lat.flt', 'STR', desc)

        ####### subimage->lonfile
        desc = 'Longitude file for the cropped and multilooked image.'
        self.addsubelement(master, 'lonfile', 'lon.flt', 'STR', desc)

        ####### subimage->incfile
        desc = 'Incidence angle file for the cropped and multilooked image.'
        if isinstance(inc, str):
            self.addsubelement(master, 'incidence', 'inc.flt', 'STR', desc)
        else:
            self.addsubelement(master, 'incidence', inc, 'FLOAT', desc)

        ###### subimage->hgtfile
        desc = 'Height file for the cropped and multilooked image.'
        self.addsubelement(master, 'hgtfile', 'hgt.flt', 'STR', desc)


        ######Directory structure
        master = self.addnode(self.root,'dirs')

        ########dirs->h5dir
        desc = 'Directory for storing all the HDF5 files.'
        self.addsubelement(master,'h5dir',h5dir,'STR',desc)

        ########dirs->atmosdir
        desc = 'Directory for storing all the weather model data.'
        self.addsubelement(master,'atmosdir',atmosdir,'STR',desc)

        ########dirs->figsdir
        desc = 'Directory for storing all the PNG previews at intermediate stages.'
        self.addsubelement(master,'figsdir',figsdir,'STR',desc)

        ########dirs->respdir
        desc = 'Directory for storing wavelet impulse responses.'
        self.addsubelement(master,'respdir',respdir,'STR',desc)

        #########Input format
        master = self.addnode(self.root,'format')

        #########format->unw
        assert unwfmt in ('FLT','RMG','GRD'), 'Undefined unwfmt'
        desc = 'Unwrapped file format. FLT/RMG'
        self.addsubelement(master,'unwfmt',unwfmt,'STR',desc)
       
        assert corfmt in ('FLT','RMG','GRD'), 'Undefined corfmt'
        desc = 'Coherence file format. FLT/RMG'
        self.addsubelement(master,'corfmt',corfmt,'STR',desc)

        assert demfmt in ('FLT','RMG','GRD'), 'Undefined demfmt'
        desc = 'DEM file format. FLT/RMG'
        self.addsubelement(master,'demfmt',demfmt,'STR',desc)

        desc = 'Convert Endianness when reading in data.'
        self.addsubelement(master,'chgendian',chgendian,'BOOL',desc)

        desc = 'List for changing endianness. Possible Entries:UNW,COR,HGT,LAT,LON,INC,MASK'
        self.addsubelement(master,'endianlist',endianlist,'LIST',desc)

        desc = 'Mask datatype.'
        self.addsubelement(master,'masktype',masktype,'STR',desc)


    def prepare_sbas_xml(self, uwcheck=False, netramp=False,
                         atmos='', demerr=False, nvalid=0,
                         regu=False, masterdate='', filt=1.0,
                         gpsramp=False,stnlist='',stntype='',
                         gpspath='',gpstype='',gpsvert=False,
                         gpsmodel=False,gpspreproc=False,
                         gpspad=3,gpsmin=5,tropomin=1,
                         tropomax=None,tropolooks=8):
        '''Creates a template XML File for SBAS processing.
        
        .. Args:
        
            * fname        ->   An example ROI-PAC style unw file
             (no .rsc in name) used to build structure.
            
        .. Kwargs:
        
            * uwcheck  -> Check for unwrapping errors (simple cycles only)
            * netramp  -> Network deramping
            * atmos    -> Atmospheric corrections
            * demerr   -> DEM Error estimation
            * nvalid   -> Number of IFGS where pixel is coherent
            * regu     -> Regularization of time functions
            * masterdate -> Time to be used as reference
            * filt      -> Length of Gaussian filter in years
            * gpsramp   -> Use GPS data for deramping interferograms
            * stnlist   -> Ascii file with station names and locations
            * stntype   -> SOPAC/ Velocity / Three column
            * gpspath   -> Directory/File with all GPS data
            * gpsvert   -> Use vertical component for GPS
            * gpsmodel  -> Use model description for GPS (sopac)
            * gpspreproc -> Filter GPS data before using it 
            * gpspad    -> Half width of window for averaging InSAR data for comparison with GPS
            * gpsmin    -> Minimum number of GPS stations needed in the scene

        .. Returns:
        
            None'''

        #######SBAS
        master = self.addnode(self.root, 'proc')

        ######sbas->nvalid
        desc = 'Minimum number of coherent IFGs for a single pixel. ' \
        'If zero, pixel should be coherent in all IFGs.'
        self.addsubelement(master, 'nvalid', nvalid, 'INT', desc)

        ######sbas->uwcheck
        desc = 'Perform unwrapping check using closed loops in time.'
        self.addsubelement(master, 'uwcheck', uwcheck, 'BOOL')

        ######sbas->netramp
        desc = 'Network deramp. Remove ramps from IFGs in a network sense.'
        self.addsubelement(master, 'netramp', netramp, 'BOOL', desc)

        ######sbas->gpsramp
        desc = 'GPS deramping. Use GPS network information to correct' \
                ' ramps.'
        self.addsubelement(master, 'gpsramp', gpsramp, 'BOOL', desc)


        #######sbas->stnlist
        desc = 'Station list for position of GPS stations.'
        self.addsubelement(master, 'stnlist', stnlist, 'STR' ,desc)

        #######sbas->stntype
        desc = 'Type of station list. False for Sopac, True for (Name,Lat,Lon), velocity for (Name,lat,lon,ve,vn,vu)'
        assert stntype in (True,False,'velocity','True','False',''), 'Undefined GPS station list type'
        if isinstance(stntype,bool) or stntype in ('True','False'):
            self.addsubelement(master,'stntype',bool(stntype),'BOOL',desc)
        else:
            self.addsubelement(master,'stntype',stntype,'STR',desc)

        ########sbas->gpspath
        desc = 'Directory that stores the files for SOPAC or full path of the velotable.'
        self.addsubelement(master,'gpspath',gpspath,'STR',desc)

        ########sbas->gpstype
        desc = 'Type of data that is provided. Can be sopac or velocity.'
        assert gpstype in ('sopac','velocity',''), 'Undefined GPS type'
        self.addsubelement(master,'gpstype',gpstype,'STR',desc)

        ########sbas->gpsvert
        desc = 'Use vertical components from the GPS data.'
        self.addsubelement(master,'gpsvert',gpsvert,'BOOL',desc)

        ########sbas->gpsmodel
        desc = 'Use SOPAC model header for the GPS stations.'
        self.addsubelement(master,'gpsmodel',gpsmodel,'BOOL',desc)

        ########sbas->gpspreproc
        desc = 'Preprocess and smoothen the data using before using.'
        self.addsubelement(master,'gpspreproc',gpspreproc,'BOOL',desc)

        ########sbas->gpspad
        desc = 'Number of pixels around GPS station to be averaged for comparison.'
        self.addsubelement(master,'gpspad',gpspad,'INT',desc)

        desc= 'Minimum number of GPS needed for ramp correction.'
        self.addsubelement(master,'gpsmin',gpsmin,'INT',desc)

        ######sbas->atmos
        desc = 'Atmospheric correction using weather models.'
        if (atmos != '') and (atmos != None):
            atmos = atmos.upper()

        assert atmos in ('ERA', 'ECMWF', 'NARR', 'TROPO', ''), 'Undefined PyAPS ' \
        ' correction Flag.'
        self.addsubelement(master, 'atmos', atmos, 'STR', desc)

        ######sbas->demerr
        desc = 'Correct for DEM Error. Use in case when IFGs'
        'are generated from coregistered SLCs.'
        self.addsubelement(master, 'demerr', demerr, 'BOOL', desc)

        ######sbas->regularize
        desc = 'Regularization of the inverted time-series, if'
        'deformation is described using time functions.'
        self.addsubelement(master, 'regularize', regu, 'BOOL', desc)

        ######sbas->masterdate
        desc  = 'SAR acquisition to be chosen as time zero.' \
        ' If none, first acquisition is used. '
        self.addsubelement(master, 'masterdate', masterdate, 'STR', desc)
        
        ######sbas->filterlen
        desc = 'Width of the Gaussian filter used for smoothing' \
        ' final time-series'
        self.addsubelement(master, 'filterlen', filt, 'FLOAT', desc)

        ######sbas->tropomin
        desc = 'Minimum scale to be analyzed for empirical tropospheric corrections.'
        self.addsubelement(master, 'tropomin', tropomin, 'INT', desc)

        ######sbas->tropomax
        desc = 'Maximum scale to be analyzed for empirical tropospheric corrections.'
        self.addsubelement(master, 'tropomax', tropomax, 'INT', desc)

        ######sbas->tropolooks
        desc = 'Number of additional looks to be applied before estimating tropospheric parameters.'
        self.addsubelement(master,'tropolooks', tropolooks, 'INT', desc)

        
        
        
    def prepare_mints_xml(self, uwcheck=False, netramp=False,
                         atmos='', demerr=False,
                         minscale=0, maxscale=0,
                         regu=True, masterdate='', minpad=0.1,
                         shape=0, smooth=1, skip=1, wvlt='meyer',
                         gpsramp = False, gpspad=2, gpsmin=5,
                         gpsmodel=False,gpsvert=False,gpspreproc=False,
                         gpstype='',gpspath='',stnlist='',stntype='',
                         kfolds=1,lamrange=[-5,5,50], tropomin=1,
                         tropomax=None, tropolooks=8):
        '''Creates a template XML File for SBAS processing.
        
        .. Args:
        
            * fname        ->   An example ROI-PAC style unw file
             (no .rsc in name) used to build structure.
            
        .. Kwargs:
        
            * uwcheck  -> Check for unwrapping errors (simple cycles only)
            * netramp  -> Network deramping
            * atmos    -> Atmospheric corrections
            * demerr   -> DEM Error estimation
            * minscale -> Smallest scale to be considered for reconstruction
            * regu     -> Regularization of time functions
            * masterdate -> Time to be used as reference
            * minpad   -> Minimum fraction of padding for mirroring
            * shape    -> Use shape factor for inversions
            * smooth   -> Smoothing window size for regularization parameter
            * skip     -> Estimate smoothing paramater every skip pixels
            * wvlt     -> Wavelet to user 'meyer' or from pywt
            * gpsramp  -> Use GPS data to correct orbit errors
            * gpspad   -> Half width of window for averaging InSAR data to compare with GPS
            * gpsmin   -> Minimum number of GPS stations for ramp correction
            * gpsmodel -> Use sopac model description instead of raw timeseries
            * gpsvert  -> Use vertical component of GPS
            * gpspreproc -> Filter gps data before using them for corrections
            * gpstype   -> sopac / velocity
            * gpspath   -> Directory/ File with all GPS data
            * stnlist   -> File with name and coordinates of GPS stations
            * stntype   -> sopac/ velocity / three column
        
        .. Returns:
        
            None'''

        #######MInTS
        master = self.addnode(self.root, 'proc')

        ######mints->minscale
        desc = 'Number of smallest scales to ignore for reconstruction.'
        self.addsubelement(master, 'minscale', minscale, 'INT', desc)

        desc = 'Number of largest scales to ignore for reconstruction.'
        self.addsubelement(master, 'maxscale', maxscale, 'INT', desc)

        ######mints->uwcheck
        desc = 'Perform unwrapping check using closed loops in time.'
        self.addsubelement(master, 'uwcheck', uwcheck, 'BOOL')

        ######mints->netramp
        desc = 'Network deramp. Remove ramps from IFGs in a network sense.'
        self.addsubelement(master, 'netramp', netramp, 'BOOL', desc)

        #######mints->gpsramp
        desc = 'Use GPS network information to correct ramps.'
        self.addsubelement(master, 'gpsramp', gpsramp, 'BOOL', desc)

        #######mints->stnlist
        desc = 'Station list for position of GPS stations.'
        self.addsubelement(master, 'stnlist', stnlist, 'STR' ,desc)

        #######mints->stntype
        desc = 'Type of station list. False for Sopac, True for (Name,Lat,Lon), velocity for (Name,lat,lon,ve,vn,vu)'
        assert stntype in (True,False,'velocity','True','False',''), 'Undefined GPS station list type'
        if isinstance(stntype,bool) or stntype in ('True','False'):
            self.addsubelement(master,'stntype',bool(stntype),'BOOL',desc)
        else:
            self.addsubelement(master,'stntype',stntype,'STR',desc)

        ########mints->gpspath
        desc = 'Directory that stores the files for SOPAC or full path of the velotable.'
        self.addsubelement(master,'gpspath',gpspath,'STR',desc)

        ########mints->gpstype
        desc = 'Type of data that is provided. Can be sopac or velocity.'
        assert gpstype in ('sopac','velocity',''), 'Undefined GPS type'
        self.addsubelement(master,'gpstype',gpstype,'STR',desc)

        ########mints->gpsvert
        desc = 'Use vertical components from the GPS data.'
        self.addsubelement(master,'gpsvert',gpsvert,'BOOL',desc)

        ########mints->gpsmodel
        desc = 'Use SOPAC model header for the GPS stations.'
        self.addsubelement(master,'gpsmodel',gpsmodel,'BOOL',desc)

        ########mints->gpspreproc
        desc = 'Preprocess and smoothen the data using before using.'
        self.addsubelement(master,'gpspreproc',gpspreproc,'BOOL',desc)

        ########mints->gpspad
        desc = 'Number of pixels around GPS station to be averaged for comparison.'
        self.addsubelement(master,'gpspad',gpspad,'INT',desc)

        desc= 'Minimum number of GPS needed for ramp correction.'
        self.addsubelement(master,'gpsmin',gpsmin,'INT',desc)


        ######mints->atmos
        desc = 'Atmospheric correction using weather models.'
        if (atmos!= None) and (atmos != ''):
           atmos = atmos.upper()
        assert atmos in ('ERA', 'ECMWF', 'NARR', 'TROPO', ''), 'Undefined PyAPS' \
        ' correction Flag.'
        self.addsubelement(master, 'atmos', atmos, 'STR', desc)

        ######mints->demerr
        desc = 'Correct for DEM Error. Use in case when IFGs are' \
        ' generated from coregistered SLCs.'
        self.addsubelement(master, 'demerr', demerr, 'BOOL', desc)

        ######mints->regularize
        desc = 'Regularization of the inverted time-series, if' \
        ' deformation is described using time functions.'
        self.addsubelement(master, 'regularize', regu, 'BOOL', desc)

        ######mints->masterdate
        desc  = 'SAR acquisition to be chosen as time zero. ' \
        'If none, first acquisition is used. '
        self.addsubelement(master, 'masterdate', masterdate, 'STR', desc)
        
        ######mints->minpad
        desc = 'Minimum padding to dyadic length for interferograms.'
        self.addsubelement(master, 'minpad', minpad, 'FLOAT', desc)
        
        ######mints->wavelet
        desc = 'Wavelet to use for analysis. Meyer or list from pywt.'
        self.addsubelement(master, 'wavelet', wvlt, 'STR', desc)
        
        ######mints->shape
        desc = 'Shape smoothing during Regularization'
        self.addsubelement(master, 'shape', shape, 'INT', desc)
        
        ######mints->smooth
        desc = 'Window size for smoothing of regularization parameter'
        self.addsubelement(master, 'smooth', smooth, 'INT', desc)
       
        ######mints->smoothskip
        desc = 'Skip for smoothing parameter estimation'
        self.addsubelement(master, 'smoothskip', skip, 'INT', desc)

        ######mints->kfolds
        desc = 'Number of folds for k-fold cross validation.'
        self.addsubelement(master,'kfolds', kfolds, 'INT', desc)

        ######mints->lamrange
        desc = 'Range of regularization penalty parameters. Logspace definition.'
        self.addsubelement(master,'lamrange',lamrange,'LIST',desc)


        ######mints->tropomin
        desc = 'Minimum scale to be analyzed for empirical tropospheric corrections.'
        self.addsubelement(master, 'tropomin', tropomin, 'INT', desc)

        ######mints->tropomax
        desc = 'Maximum scale to be analyzed for empirical tropospheric corrections.'
        self.addsubelement(master, 'tropomax', tropomax, 'INT', desc)

        ######mints->tropolooks
        desc = 'Number of additional looks to be applied before estimating tropospheric parameters.'
        self.addsubelement(master,'tropolooks', tropolooks, 'INT', desc)

        
    def prepare_gen_xml(self, **kwargs):
        '''Function to build generic XML file.'''
        
        #if root is None:
        #    raise ValueError('Master node name should be provided.')
        
        #########Root node
        master = self.root
        
        flds = kwargs.keys()
        
        #########Adding each node
        for fld in flds:
            value = kwargs[fld]
            self.addsubelement(master, fld, value[0], value[1], value[2])

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
