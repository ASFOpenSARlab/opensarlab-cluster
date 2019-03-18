import numpy as np
from lxml import etree as ET

#SRStext = 'GEOGCS[&quot;WGS 84&quot;, DATUM[&quot;WGS_1984&quot;,SPHEROID[&quot;WGS 84&quot;,6378137,298.257223563, AUTHORITY[&quot;EPSG&quot;,&quot;7030&quot;]], AUTHORITY[&quot;EPSG&quot;,&quot;6326&quot;]], PRIMEM[&quot;Greenwich&quot;,0, AUTHORITY[&quot;EPSG&quot;,&quot;8901&quot;]], UNIT[&quot;degree&quot;,0.0174532925199433, AUTHORITY[&quot;EPSG&quot;,&quot;9122&quot;]], AUTHORITY[&quot;EPSG&quot;,&quot;4326&quot;]]'

SRStext = 'GEOGCS["WGS 84", DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563, AUTHORITY["EPSG","7030"]], AUTHORITY["EPSG","6326"]], PRIMEM["Greenwich",0, AUTHORITY["EPSG","8901"]], UNIT["degree",0.0174532925199433, AUTHORITY["EPSG","9122"]], AUTHORITY["EPSG","4326"]]'

def VRTcreate_points(vrtname, csvname, layername, fields=None):
    '''Creates a VRT file for a CSV file.'''
    root = ET.Element('OGRVRTDataSource')

    layer = ET.SubElement(root, 'OGRVRTLayer', name=layername)

    elem = ET.SubElement(layer, 'SrcDataSource')
    elem.text = csvname

    elem = ET.SubElement(layer,'LayerSRS')
    elem.text = 'WGS84'

    if fields is None:
        elem = ET.SubElement(layer,'GeometryField',encoding="PointFromColumns",x="field_1",y="field_2",z="field_3")
    else:
        elem = ET.SubElement(layer,'GeometryField',encoding='PointFromColumns',x='field_%d'%fields[0],y='field_%d'%fields[1],z='field_%d'%fields[2])


    tree = ET.ElementTree(root)
    tree.write(vrtname,pretty_print=True,xml_declaration=False)


def VRTlatlonraster(fname,datname,shape):
    '''Create a VRT file for lat / lon raster files.'''
    root = ET.Element('VRTDataset',rasterXSize=str(shape[1]),rasterYSize=str(shape[0]))

    layer = ET.SubElement(root, 'VRTRasterBand', dataType='Float32', band='1', subClass='VRTRawRasterBand')

    elem = ET.SubElement(layer, 'SourceFilename', relativetoVRT='1')
    elem.text = datname

    elem = ET.SubElement(layer,'ByteOrder')
    elem.text = 'LSB'

    elem = ET.SubElement(layer,'ImageOffset')
    elem.text = '0'

#    elem = ET.SubElement(layer,'PixelOffset')
#    elem.text = '0' #'4'

    elem = ET.SubElement(layer,'LineOffset')
    elem.text = '0' #str(4*shape[1])

    elem = ET.SubElement(layer,'ByteOrder')
    elem.text = 'LSB'

    elem = ET.SubElement(root,'SRS')
    elem.text = SRStext

    elem = ET.SubElement(layer,'NoDataValue')
    elem.text = 'nan'

    tree = ET.ElementTree(root)
    tree.write(fname, pretty_print=True, xml_declaration=False)

def VRTdataraster(fname,datname,shape,lat='latitude.vrt',lon='longitude.vrt'):
    '''Create a VRT file for data with corresponding lat/lon data as well.'''
   
    root = ET.Element('VRTDataset',rasterXSize=str(shape[1]),rasterYSize=str(shape[0]))

    ######Meta data section
    meta = ET.SubElement(root, 'Metadata', domain='GEOLOCATION')

    elem = ET.SubElement(root, 'SRS')
    elem.text = SRStext

    elem = ET.SubElement(meta, 'MDI', key='LINE_OFFSET')
    elem.text = '0' #str(4*shape[1])

    elem = ET.SubElement(meta, 'MDI', key='LINE_STEP')
    elem.text = '1'

    elem = ET.SubElement(meta, 'MDI', key='PIXEL_OFFSET')
    elem.text='0' #'4'

    elem = ET.SubElement(meta, 'MDI', key='PIXEL_STEP')
    elem.text = '1'

    elem = ET.SubElement(meta, 'MDI', key='X_BAND')
    elem.text='1'

    elem = ET.SubElement(meta, 'MDI', key='X_DATASET')
    elem.text = lon

    elem = ET.SubElement(meta, 'MDI', key='Y_BAND')
    elem.text = '1'

    elem = ET.SubElement(meta, 'MDI', key='Y_DATASET')
    elem.text = lat

    #######Data layer section
    layer = ET.SubElement(root, 'VRTRasterBand', dataType='Float32', band="1", subClass='VRTRawRasterBand')

    elem = ET.SubElement(layer, 'SourceFilename', relativetoVRT='1')
    elem.text = datname

    elem = ET.SubElement(layer,'ByteOrder')
    elem.text = 'LSB'

    elem = ET.SubElement(layer,'ImageOffset')
    elem.text = '0'

#    elem = ET.SubElement(layer,'PixelOffset')
#    elem.text = '4'

    elem = ET.SubElement(layer,'LineOffset')
    elem.text = '0' #str(4*shape[1])

    elem = ET.SubElement(layer,'ByteOrder')
    elem.text = 'LSB'

    elem = ET.SubElement(layer,'NoDataValue')
    elem.text = 'nan'

    tree = ET.ElementTree(root)
    tree.write(fname, pretty_print=True, xml_declaration=False)



############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
