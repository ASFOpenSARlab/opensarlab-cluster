import numpy as np
import matplotlib.pyplot as plt
import pyresample as psamp
import _vrt
import _gmt

'''We can write more complicated geocoders using pyresample. For example, changing coordinate systems etc. We are for now interested in keeping everything in the WGS84 domain.

.. Author: Piyush Agram <piyush@gps.caltech.edu>'''

class geocode:
    '''Class containing the geocode functions.'''
    def __init__(self, lats=None, lons=None, box=None, spacing=None):
        '''Geocoding constructor.

        Kwargs:

            * lats = Radar coded Lats
            * lons = Radar coded Lons
            * Box  = [MinLon, MaxLon, MinLat, MaxLat] for area imaged.
            * Spacing = Spacing for the Box [dLon,dLat] or scalar.
            
        Returns:
            
            * None'''
        
        if lats.shape != lons.shape:
            raise ValueError('Lats and Lons should have same shape.')

        if box is None:
            self.area_extent = [np.nanmin(lons), np.nanmax(lons), np.nanmin(lats), np.nanmax(lats)]
        else:
            self.area_extent =  box

        if spacing is None:
            self.step = [(self.area_extent[1]-self.area_extent[0])/(lats.shape[1]*1.0), (self.area_extent[3] - self.area_extent[2])/(lats.shape[0]*1.0)]

        elif np.isscalar(spacing):
            self.step = np.ones(2)*spacing
        else:
            self.step = spacing

        self.lons = np.arange(self.area_extent[0],self.area_extent[1],self.step[0])
        self.lats = np.arange(self.area_extent[2],self.area_extent[3],self.step[1])
        self.swath_def = psamp.geometry.SwathDefinition(lons=lons, lats=lats)
        self.grid_def = psamp.geometry.GridDefinition(np.tile(self.lons[None,:],(self.lats.size,1)), np.tile(self.lats[:,None],(1,self.lons.size)))

    def rdr2geo_nearest(self, img, radius=50, epsilon=0):
        '''Transform data in radar coordinates to geocoordinates. Nearest neighbor.
        
        Args:

            * img      ->  2D image in radar coordinates to be geocoded

        Kwargs:
            
            * radius  ->  Radius in meters
            * epsilon ->  Nearest neighbor approximation factor
            
        Returns:
            
            * gimg    ->  Geocoded image'''

        if img.shape != self.swath_def.shape:
            raise ValueError('Image shape does not match swath definition.')

        swath_con = psamp.image.ImageContainerNearest(img, self.swath_def, radius_of_influence=radius,fill_value=np.nan,epsilon=epsilon)
        im1 = swath_con.resample(self.grid_def)
        return im1.image_data

    def geo2rdr_nearest(self, img, radius=50, epsilon=0):
        '''Transform data in geo coordinates to radar coordinates. Nearest neighbor.

        Args:

            * img       -> 2D image in geocoordinates (lat,lon)

        Kwargs:

            * radius    -> Radius in meters
            * epsilon   -> Nearest neighbor approximation factor

        Returns:

            * rimg      -> Radar-coded image'''

        if img.shape != self.grid_def.shape:
            raise ValueError('Image shape does not match grid definition.')

        grid_con = psamp.ImageContainerNearest(img, self.grid_def, radius_of_influence=radius, fill_value=np.nan, epsilon=epsilon)
        im1 = grid_con.resample(self.swath_def)
        return im1.image_data

    def rdr2gmt(self,img,fname,title='default', name='height', radius=50, epsilon=0, units='meters'):
        '''Automatically geocodes and saves the geocoded image in a GMT-readable grd file.
        Args:

            * img    -> Input image  in radar coordinates.
            * fname  -> Name of the output GMT file.

        Kwargs:

            * title  -> Title for the grd file
            * name   -> Name of the field in the grd file
            * radius -> Radius for nearest neighbor interpolation
            * epsilon -> Nearest neighbor approximation factor
            
        Returns:
            
            * None'''

        res = self.rdr2geo_nearest(img, radius=radius, epsilon=epsilon)
        _gmt.write_gmt_simple(self.lons, self.lats, res, fname, title=title, name=name, units=units)

class Swath:
    def __init__(self, lats=None, lons=None):
        '''Swath constructor.

        Kwargs:

            * lats = Radar coded Lats
            * lons = Radar coded Lons
            * Box  = [MinLon, MaxLon, MinLat, MaxLat] for area imaged.
            * Spacing = Spacing for the Box [dLon,dLat] or scalar.
            
        Returns:
            
            * None'''
        
        if lats.shape != lons.shape:
            raise ValueError('Lats and Lons should have same shape.')

        self.swath_def = psamp.geometry.SwathDefinition(lons=lons, lats=lats)

    def gdal_points(self, img, base='temp'):
        '''Save finite values as points in a CSV file and write a VRT to allow to be read in to GDAL.
        
        Args:
            
            * img     -> 2D slice to be saved
            
        Kwargs:
            
            * base    -> Name of the layer in the vrt file and the name of output file
            
        Returns:
            
            * None'''

        if img.shape != self.swath_def.shape:
            raise ValueError('Image shape does not match swath definition.')

        csvname = '%s.csv'%base
        layername = base
        vrtname = '%s.vrt'%base

        mask = np.isfinite(img)
        res = np.column_stack((self.swath_def.lons[mask].flatten(), self.swath_def.lats[mask].flatten(), img[mask].flatten()))
        np.savetxt(csvname,res,fmt='%4.6f',delimiter=",",newline="\n")
        _vrt.VRTcreate_points(vrtname,csvname,layername)


    def gdal_raster(self, img, base='temp',new=False, latbase='latitude', lonbase='longitude'):
        '''Save the slice as a raster file and write a VRT file to allow to be read in to GDAL.
        
        Args:
            
            * img     -> 2D slice to be saved

        Kwargs:

            * base    -> Name of layer in the VRT file and the output file
            * new     -> If set to True, geometry VRT files wont be created
            * latbase -> Base for the latitude VRT file
            * lonbase -> Base for the longitude VRT file
            
        Returns:
            
            * None'''

        if img.shape != self.swath_def.shape:
            raise ValueError('Image shape does not match swath definition.')

        datname = '%s.flt'%base
        vrtname = '%s.vrt'%base

        londat = '%s.flt'%lonbase
        lonvrt = '%s.vrt'%lonbase

        latdat = '%s.flt'%latbase
        latvrt = '%s.vrt'%latbase

        shape = self.swath_def.shape
        if new:
            self.swath_def.lons[:,:].astype(np.float32).tofile(londat)
            _vrt.VRTlatlonraster(lonvrt, londat, shape)

            self.swath_def.lats[:,:].astype(np.float32).tofile(latdat)
            _vrt.VRTlatlonraster(latvrt, latdat, shape)
        
        img.astype(np.float32).tofile(datname)
        _vrt.VRTdataraster(vrtname, datname, shape, lat=latvrt, lon=lonvrt) 

############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
