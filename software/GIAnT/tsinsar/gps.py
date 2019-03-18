'''Support for using reading GPS time-series for comparison with time-series products and to deramp interferograms.

.. author:

    Piyush Agram <piyush@gps.caltech.edu>

.. Dependencies:

    numpy'''

import numpy as np
import tsio
import tsutils as tu
import schutils as sch
import datetime as dt
import logmgr
import matplotlib.pyplot as plt
try:
    import solver.tikh as tikh
except:
    pass

import sopac

logger = logmgr.logger('gps')
# determine if a point is inside a given polygon or not
# Polygon is a list of (x,y) pairs.
#Adapted from website www.ariel.com.au
def point_inside_polygon(x,y,poly):
    ''' Determines if a point x, y is locate within poly, which is a list of points. Adapted from http://www.ariel.com.au .'''

    n = len(poly)
    inside =False

    p1x,p1y = poly[0]
    for i in range(n+1):
        p2x,p2y = poly[i % n]
        if y > min(p1y,p2y):
            if y <= max(p1y,p2y):
                if x <= max(p1x,p2x):
                    if p1y != p2y:
                        xinters = (y-p1y)*(p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x,p1y = p2x,p2y

    return inside


class STN:
    '''Class meant to deal with data from a single GPS station.'''

    def __init__(self, stname, gpsdir, los, usevert=True, plot=False):
      
        logger.info('Reading in GPS station: %s'%(stname))
        fname = '%s/%sCleanFlt.neu'%(gpsdir,stname)
        logger.debug('Filename : %s'%(fname))
        [ddec,yr,day,north,east,up,dnor,deas,dup] = tsio.textread(fname,
                'F I I F F F F F F')
        self.fname = fname
        self.los = los
        self.name = stname
        self.losts  = 1000*(los[0]*north+los[1]*east)
        self.loserr = 1.0e6*((los[0]*dnor)**2 + (los[1]*deas)**2)
        self.north = 1000.0 * north
        self.east = 1000.0 * east
        self.up = 1000.0 * up
        self.tdec  = ddec
        self.model = None
        logger.debug('Time Span: %f %f'%(ddec.min(),ddec.max()))

        if usevert:
            self.losts += 1000*(los[2]*up)
            self.loserr += 1.0e6*((los[2]*dup)**2)

        self.loserr = np.sqrt(self.loserr)

        if plot:
            plt.errorbar(self.tdec, self.losts, self.loserr)
            plt.show()


    def get_data(self, daystr, margin=50, model=True):
        '''Return the nearest GPS observation within a margin.
        Only one date at a time.'''
        if isinstance(daystr,str):
            daynum = tu.datenum([daystr])
        else:
            daynum = daystr    #Already in ordinal form

        dobj = dt.date.fromordinal(daynum)
        if dobj.year%4 == 0:
            ndaysyr = 366.0
        else:
            ndaysyr = 365.0

        ddec = dobj.year + dobj.timetuple().tm_yday / ndaysyr

        close_day = np.argmin(np.abs(self.tdec - ddec))

        if np.abs(self.tdec[close_day] - ddec) > (margin/ndaysyr):
            disp = np.nan
            disperr = np.nan
        else:
            if model:
                disp = self.sopac_losts[close_day]
            else:
                disp = self.losts[close_day]

            disperr = self.loserr[close_day]

        return disp, disperr

    def preprocess(self, plot=False):
        '''Simple pre-processor for smoothing out the time-series with a bunch of integeral splines. If you have cleaned time-series, please use that instead of this utility. This has only been included for testing purposes and as a template to help write your own specific pre-processor.'''

        tmin = self.tdec.min()
        tmax = self.tdec.max()

        logger.debug('Preprocessing GPS Station: %s'%(self.name))
        nspline = np.int((tmax-tmin)/0.16)  ####Spacing every 2 months

        tin = self.tdec - tmin
        disp = self.losts - self.losts[0]
    
        rep = [['ISPLINES',[3],[nspline]], ['SEASONAL',[1.0]]]
        logger.debug('Preprocess String: %s',str(rep))

        G,mn,reg = tu.Timefn(rep,tin)
        Lf = tu.laplace1d(nspline)
        Lf = np.column_stack((Lf,np.zeros((nspline,2))))

        solv = tikh.TIKH(G, Lf)
        alpha = solv.gcv(disp)
        soln = solv.solve(alpha, disp)
       
        tin = np.linspace(0.,tmax-tmin,num=nspline*30)
        G,mn,reg = tu.Timefn(rep,tin)
        losts = np.dot(G,soln)
        if plot:
            plt.plot(self.tdec, self.losts)
            plt.hold('on')
            plt.plot(tmin+tin, losts)
            plt.title('Station %s'%(self.name))
            plt.show()

        self.tdec = tmin+tin
        self.losts = losts
        self.loserr = 2 * np.ones(len(losts))


    def get_sopac_model(self, plot=False):
        '''Reads in the model parameters from SOPAC files and generates
        the modeled displacements in los direction.'''

        # Initialize sopac model
        smodel = sopac.sopac(self.fname)
        components = [smodel.north, smodel.east, smodel.up]

        self.model = smodel
        # Compute los displacements by looping through components
        self.sopac_losts = 0.0
        ii = 0
        for comp in components:

            # First, compute piece-wise linear contributions separately
            amp = []; win = []
            for frep in comp.slope:
                amp.append(frep.amp)
                win.append(frep.win)
            num = len(win)
            points = np.zeros((num+1,), dtype=float)
            tpts = [win[0][0]]
            for jj in xrange(num):
                disp = amp[jj] * (win[jj][1] - win[jj][0])
                points[jj+1] = points[jj] + disp
                tpts.append(win[jj][1])
            linear = np.interp(self.tdec, tpts, 1000.0*points)

            # Loop through rest of time functionals
            rep = []; amp = []; win = []
            smodel_all = [comp.decay, comp.offset,
                          comp.annual, comp.semi]
            for model in smodel_all:
                for frep in model:
                    rep.append(frep.rep)
                    if isinstance(frep.amp, np.ndarray):
                        amp.extend(frep.amp)
                    else:
                        amp.append(frep.amp)
                    win.append(frep.win)

            # Construct design matrix and compute displacments
            G = np.asarray(tu.Timefn(rep, self.tdec)[0], order='C')
            amp = 1000.0 * np.array(amp)
            fit = np.dot(G, amp) + linear

            # Remove constant bias and compute los displacement
            if ii == 0:
                fit -= np.mean(fit - self.north)
            elif ii == 1:
                fit -= np.mean(fit - self.east)
            elif ii == 2:
                fit -= np.mean(fit - self.up)
            self.sopac_losts += self.los[ii] * fit
            ii += 1

        if plot:
            plt.plot(self.tdec, self.losts, '.', label='Data')
            plt.plot(self.tdec, self.sopac_losts, '-', linewidth=2, label='Model')
            plt.xlabel('Year')
            plt.ylabel('LOS displacement (mm)')
            plt.legend()
            plt.show()
        

class GPS:
    def __init__(self, stnlist, fourcol=False):
        '''Initiate the GPS structure with a station list.'''
       
        logger.debug('Station List File = %s'%(stnlist))
        if fourcol is True:
            [name,lat,lon] = tsio.textread(stnlist,'S F F')
	elif fourcol == 'velocity':
	    [name,lat,lon,ve,vn,vu] = tsio.textread(stnlist,'S F F F F F')
	    self.ve = np.array(ve)
	    self.vn = np.array(vn)
	    self.vu = np.array(vu)
        else:
            [name,lat,lon] = tsio.textread(stnlist,'S K K K F F K K K K K K K K')

        self.name = np.array(name)
        self.lat = np.array(lat)
        self.lon = np.array(lon)
        self.xi = None
        self.yi = None
        self.bndry = None
        self.los  = None
        self.stns = None

    def croplist(self, latlim, lonlim):
        '''Crop the station list based on a bounding box.'''
        
        flag = (self.lon > lonlim[0]) & (self.lon < lonlim[1]) & (self.lat > latlim[0]) & (self.lat < latlim[1])
        self.name = self.name[flag]
        self.lat = self.lat[flag]
        self.lon = self.lon[flag]
    

    def lltoij(self, flen, fwid, latfile=None, lonfile=None):
       
        lats = tsio.load_flt(latfile, fwid, flen)
        lons = tsio.load_flt(lonfile, fwid, flen)
	lats[lats==0.0] = np.nan
	lons[lons==0.0] = np.nan        

        dx = np.abs(lons[fwid/2,flen/2+1] - lons[fwid/2,flen/2])
        dy = np.abs(lats[fwid/2,flen/2+1] - lats[fwid/2,flen/2])
        dr = 4*dx*dx + 4*dy*dy
        
        bndry = []
	milat = np.nanmin(lats)
	milon = np.nanmin(lons)
	malat = np.nanmax(lats)
	malon = np.nanmax(lons)
	
        bndry.append([malat,milon])
        bndry.append([malat,malon])
        bndry.append([milat,malon])
        bndry.append([milat,milon])
        bndry.append([malat,milon])
        
        xi = np.nan*np.zeros(len(self.lat),dtype=np.int)
        yi = np.nan*np.zeros(len(self.lat),dtype=np.int)
        
        flag = (np.zeros(len(self.lat)) > 1)
                
        for k in xrange(len(self.lat)):
            flag[k] = point_inside_polygon(self.lat[k],self.lon[k],bndry)
            if flag[k]:
                dist = (lats-self.lat[k])**2 + (lons-self.lon[k])**2
                ind = np.nanargmin(dist)
                ii,jj = divmod(ind,fwid)
                mval = dist[ii,jj]
                if mval < (dr):
                    yi[k] = ii
                    xi[k] = jj
                else:
                    flag[k] = False
        
        logger.info('Number of viable GPS: %d',np.sum(flag))
        self.name = self.name[flag]
        self.lat = self.lat[flag]
        self.lon = self.lon[flag]
        self.bndry = bndry
        self.xi = xi[flag].astype(np.int)
        self.yi = yi[flag].astype(np.int)
	if hasattr(self, 've'):
		self.ve = self.ve[flag]
		self.vn = self.vn[flag]
		self.vu = self.vu[flag]

        logger.info('Number of GPS stations in Frame: %d'% (len(self.name)))
        print 'Stations: ', len(self.name)

    def lltoij_sch(self, par):
        """
        Compute range and azimuth pixels for a given list of latitude and longitude
        by resampling locations to -> SCH -> range-azimuth.

        Arguments:
        par         parameter structure. Get from sch.getrsc_par

        Output:
        inc         array of incidence angles
        """

        rad = np.pi / 180.0
        schcoor = sch.llh2sch(self.lat*rad, self.lon*rad, self.elev, par)

        ### sanity check
        #lat,lon,h = sch.sch2llh(schcoor, par)    # sanity check
        #print self.lat*rad, lat, 111.1/rad*(self.lat*rad - lat)*1000
        #print self.lon*rad, lon, 111.1/rad*(self.lon*rad - lon)*1000

        ii,jj,inc = sch.sch2ijh(schcoor, par)

        self.xi = jj
        self.yi = ii

        return inc

    ######Check sign.
    @staticmethod
    def hdginc2los(hdg,inc):
        hdgr = hdg*np.pi/180.0
        incr = inc*np.pi/180.0
        slook = np.sin(incr)
        nfac = np.cos(np.pi/2.0 + hdgr) * slook
        efac = np.sin(np.pi/2.0 - hdgr) * slook
        ufac = -np.cos(incr)
       
        los = np.array([nfac,efac,ufac])
        return los

    def setlos(self, hdg, inc, flen=None, fwid=None):
        
        if fwid is not None:
            incang = tsio.load_flt(inc, fwid, flen)
            incdeg = incang[self.yi, self.xi]
            self.los = np.zeros((len(self.xi),3))
            for k in xrange(len(self.xi)):
                self.los[k,:] = self.hdginc2los(hdg,incdeg[k])
        # BVR 08/14/12: added support for array of incidence angles
        elif isinstance(inc, np.ndarray):
            self.los = np.zeros((inc.size,3))  # shape (nstat,3)
            for k in xrange(inc.size):
                self.los[k,:] = self.hdginc2los(hdg, inc[k]*180.0/np.pi) 
        else:
            self.los = self.hdginc2los(hdg,inc)

    
    def readgps(self, GPSdir, usevert=True, model=True, preprocess=False):
        self.stns = []
        nstations = len(self.name)

        logger.info('READING GPS data files')
        progb = tsio.ProgressBar(maxValue = nstations)

        for k in xrange(nstations):
            if len(self.los.shape) == 2:
                los = self.los[k,:]
            else:
                los = self.los

            newstn = STN(self.name[k], GPSdir, los, usevert)
            if preprocess:
                newstn.preprocess(plot=False)

            if model:
                newstn.get_sopac_model(plot=False)

            self.stns.append(newstn)
            progb.update(k,every=2)

        progb.close()

    def get_ts(self, daylist, model=True):
        nstns = len(self.stns)
        ntims = len(daylist)
        sar_ts = np.zeros((nstns, ntims))
        sar_terr = np.zeros((nstns, ntims))
        for k in xrange(nstns):
            for dd in xrange(ntims):
                disp,disperr = self.stns[k].get_data(daylist[dd], model=model)
                sar_ts[k,dd] = disp
                sar_terr[k,dd] = disperr

        return sar_ts, sar_terr

    def buildtsvelo(self, time):
	nstns = len(self.name)
        ntims = len(time)
        sar_ts = np.zeros((nstns, ntims))
        sar_terr = np.zeros((nstns, ntims))
	T = time - time[0]
	tm,e = np.meshgrid(T,self.ve) 
	E = tm*e
	tm,n = np.meshgrid(T,self.vn)
	N = tm*n
	tm,u = np.meshgrid(T,self.vu)
	U = tm*u 

        ndims = len(self.los.shape)
	for n in xrange(nstns):
            if ndims == 1:
                sar_ts[n,:] = self.los[0]*E[n,:] + self.los[1]*N[n,:] + self.los[2]*U[n,:]
            else:
                sar_ts[n,:] = self.los[n,0]*E[n,:] + self.los[n,1]*N[n,:] + self.los[n,2]*U[n,:]

	# Put it in mm
	sar_ts = sar_ts*1000.0		

	return sar_ts,sar_terr

    def resample(self):
        """
        Optional: resample all stations to a common time array. Use with care
        when dealing with data with coseismic offsets.
        """

        # Loop through stations to find bounding times
        tmin = 1000.0
        tmax = 3000.0
        for stn in self.stns:
            tmin_cur = stn.tdec[0]
            tmax_cur = stn.tdec[-1]
            if tmin_cur > tmin:
                tmin = tmin_cur
            if tmax_cur < tmax:
                tmax = tmax_cur

        # Determine (approximate) number of days between tmin and tmax and create common time
        days = (tmax - tmin) * 365.25
        tint = np.linspace(tmin, tmax, np.floor(days))

        # Resample each station to common time
        for stn in self.stns:
            stn.losts = np.interp(tint, stn.tdec, stn.losts)
            stn.loserr = np.interp(tint, stn.tdec, stn.loserr) # bogus
            stn.tdec = tint


############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
