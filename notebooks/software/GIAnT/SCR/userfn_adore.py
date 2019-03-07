''' Defines the makefnames function connecting orbits to files. 
    Also generates the temporal dictionaries for NSBAS and MInTS

.. author:
 
    Piyush Agram <piyush@gps.caltech.edu>
    Batuhan Osmanoglu <batu@gi.alaska.edu>
     
.. Methods:
    
    * import_adore_meta(mresfiles=None, sresfiles=None, iresfiles=None, drsFiles=None)
    * NSBASdict()
    * timedict()     
'''

def import_adore_meta(mresfiles=None, sresfiles=None, iresfiles=None, drsFiles=None):
    '''    [date1, date2, bperp, ilist, clist, wlist]=import_adore_meta(mresfiles=None, sresfiles=None, iresfiles=None, drsFiles=None)
    mresfiles: master result files
    sresfiles: slave result files
    iresfiles: interferogram result files
    drsfiles: doris input files (e.g. coarseorb.drs) which have paths for master, slave and interferogram result files.
    '''
    import adore
    from dateutil import parser
    
    if drsFiles is not None:
        mresfiles=[]
        sresfiles=[]
        iresfiles=[]
        for f in drsFiles:
            d=adore.drs2dict(f);
            mresfiles.append(d['general']['m_resfile'].strip())
            sresfiles.append(d['general']['s_resfile'].strip())
            iresfiles.append(d['general']['i_resfile'].strip())
            
    masterDates=[]
    slaveDates=[]
    unw=[]   
    bperp=[]
    btemp=[]
    coh=[]
    wlist=[]
    
    for f in range(0,len(mresfiles)):
        mobj=adore.dict2obj(adore.res2dict(mresfiles[f]))
        sobj=adore.dict2obj(adore.res2dict(sresfiles[f]))
        ires=adore.res2dict(iresfiles[f])
        iobj=adore.dict2obj(ires)
        masterDates.append(parser.parse(mobj.readfiles.First_pixel_azimuth_time).date().strftime('%Y%m%d') )
        slaveDates.append( parser.parse(sobj.readfiles.First_pixel_azimuth_time).date().strftime('%Y%m%d') )        
        unw.append( iobj.unwrap.Data_output_file);
        coh.append( iobj.coherence.Data_output_file )
        bperp.append( iobj.coarse_orbits.Bperp )
        btemp.append( iobj.coarse_orbits.Btemp )           
        wlist.append( mobj.readfiles.Radar_wavelength )
    return [masterDates, slaveDates, bperp, unw, coh, wlist]
    
#####To use for NSBAS
def NSBASdict():
    '''Returns a string representation of the temporal dictionary to be used with NSBAS.'''
    rep = [['POLY',[1],[tims[Ref]]],
	   ['LOG'],[-2.0],[3.0]]  
    return rep

#####To use for timefn invert / MInTS.
def timedict():
    '''Returns a string representation of the temporal dictionary to be used with inversions.'''
    rep = [['ISPLINES',[3],[48]]]
    return rep
