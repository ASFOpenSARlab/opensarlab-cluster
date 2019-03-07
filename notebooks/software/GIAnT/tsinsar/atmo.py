#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Copyright 2012, by the California Institute of Technology. ALL RIGHTS RESERVED.
# Any commercial use must be negotiated with the Office of Technology Transfer at the California Institute of Technology.
#
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

''' Library of routines used to estimate tropospheric phase screen with 
    an empirical approach

.. author:
	
	Romain Jolivet 	<rjolivet@caltech.edu>
	Piyush Agram	<piyush@caltech.edu>

.. Dependencies:
	
	numpy'''

import numpy as np
import matplotlib.pyplot as plt
import logmgr
import tsinsar as ts
import scipy.interpolate as si
try:
    import pyaps as pa
except:
    pass

logger = logmgr.logger('atmo')

class EstimateK:
	
	''' Determine the ks polynomial parameters of the phase/elevation 
	relationship using DEM and estimates an optional orbital term. A model 
	can be used. '''
	
	def __init__(self, Pol=1, Orb=3, Mod=False,plotyn=False):
	
		''' Initializes a class preparing the estimation of ks
		Args:
			Pol: Order of the polynomial relationship between phase and elevation. Default is 1.
			Orb: Type of orbit to estimate (1. Cste, 3. ax+by+c, 4. dxy+ax+by+c). Default is 3.
			Mod: Deformation model to scale with phase.
			Plt: Plot things'''

		logger.info('Atmospheric Empirical Method Initialized')

		self.Pol = Pol
		self.Orb = Orb
		self.Mod = Mod
		self.plotyn = plotyn

	def getK(self,Phi,Dem,lkdown=1):
	
		''' Computes the phase topo relationship

		Args:
			Phi: Phase array (length,width)
			Dem: Digital Elevation Model array (length,width)

		Returns:

			k: phase/topography coefficient
			o: Orbital parameters
			s: Deformation model scaling factor'''

		if lkdown>1:
			Dem = ts.LookDown(Dem,lkdown,'MEAN')
			Phi = ts.LookDown(Phi,lkdown,'MEAN')			

		x,y = np.where(np.isfinite(Phi*Dem))
		d = Phi[x,y].flatten()
		Gdem = self.polyatmo(Dem[x,y].flatten(),self.Pol)
		Gorb = self.orbfun(x,y,self.Orb)
		if np.array(self.Mod).any():
			G = np.hstack((np.hstack((Gdem.T,Gorb.T)),self.Mod[x,y].flatten()))
		else:
			G = np.hstack((Gdem.T,Gorb.T))
		
		self.G = G
		self.d = d

		m,res,rank,s = np.linalg.lstsq(G,d,rcond=1e-8)

		if self.plotyn:
			plt.figure()
			plt.subplot(221)
			plt.imshow(Phi,interpolation='nearest')
			plt.clim([np.nanmin(Phi.flatten()),np.nanmax(Phi.flatten())])
			plt.colorbar(orientation='horizontal',shrink=0.5)

			Phimod = np.zeros((Phi.shape))
			Phimod[:,:]=np.nan
			Phimod[x,y] = np.dot(G,m)
			plt.subplot(222)
			plt.imshow(Phimod,interpolation='nearest')
			plt.clim([np.nanmin(Phi.flatten()),np.nanmax(Phi.flatten())])
			plt.colorbar(orientation='horizontal',shrink=0.5)

			plt.subplot(212)
			plt.plot(Dem.flatten(),Phi.flatten(),'.k')
			plt.plot(Dem.flatten(),Phimod.flatten(),'.r')

			plt.show()

		k = m[0:self.Pol]
		s = []
		if np.array(self.Mod).any():
			o = m[self.Pol:-1]
			s = m[-1]
		else:
			o = m[self.Pol:]
		if self.Orb == 3:
                        o[0] = o[0]/np.float(lkdown)
                        o[1] = o[1]/np.float(lkdown)
                elif self.Orb == 4:
                        o[0] = o[0]/np.float(lkdown)*np.float(lkdown)
                        o[1] = o[1]/np.float(lkdown)
                        o[2] = o[2]/np.float(lkdown)

		return k,o,s

	# Builds maps of the k parameters
	def getKmap(self,Phi,Dem,lkdown=1,wl=30):

		if lkdown>1:
			lo,wo = Phi.shape
			Phi = ts.LookDown(Phi,lkdown,'MEAN')
			Dem = ts.LookDown(Dem,lkdown,'MEAN')
	
		l,w = Phi.shape
		Kmapi = np.zeros((l,w,self.Pol))
		vy,vx = np.where(np.isfinite(Phi))
		est = ts.atmo.EstimateK(Pol=self.Pol,Orb=self.Orb)

		toto = ts.ProgressBar(maxValue=len(vx))
		for i in xrange(len(vx)):
			le = np.max((0,vx[i]-wl))
			ri = np.min((w,vx[i]+wl))
			up = np.max((0,vy[i]-wl))
			do = np.min((l,vy[i]+wl))
			k,o,s = est.getK(Phi[up:do,le:ri],Dem[up:do,le:ri])
			Kmapi[vy[i],vx[i],:] = k			
			toto.update(i,every=1)
		toto.close()

		self.Kmapi = Kmapi
		if lkdown>1:
			Kmap = np.zeros((lo,wo,self.Pol))
			x = np.array(xrange(w))
			y = np.array(xrange(l))
			xout = np.linspace(0,w,wo)
			yout = np.linspace(0,l,lo)
			for i in xrange(self.Pol):
				bili = pa.processor.Bilinear2DInterpolator(x,y,np.squeeze(Kmapi[:,:,i]),cube=False)
				toto = ts.ProgressBar(maxValue=len(xout))
				for n in xrange(len(xout)):
					xi = np.ones((yout.shape))*xout[n]
					Kmap[:,n,i] = bili(xi,yout)
					toto.update(n,every=5)
				toto.close()

		else:
			Kmap = Kmapi

		ii,jj,ll = np.where(Kmap==0.0)
		Kmap[ii,jj,ll] = np.nan

		if self.plotyn:
			plt.figure()
			plt.imshow(Kmap[:,:,0])
			plt.colorbar()
			plt.show()
	
		return Kmap

	# Polynomial function for phase/elevation relationship
	@staticmethod
	def polyatmo(z,Pol):
		n=len(z)
		e=np.cumsum(np.ones((Pol,n)),axis=0)
		r=z**e
		return r
	
	# Orbital function
	@staticmethod	
	def orbfun(x,y,Orb):
		if Orb==1:
			r=np.ones((1,len(x.flatten())))
		elif Orb==3:
			r=np.vstack((np.vstack((x.flatten(),y.flatten())),np.ones((len(x.flatten()),))))
		elif Orb==4:
			r=np.vstack((x.flatten()*y.flatten(),np.vstack((np.vstack((x.flatten(),y.flatten())),np.ones((len(x.flatten()),))))))
		return r


############################################################
# Program is part of GIAnT v1.0                            #
# Copyright 2012, by the California Institute of Technology#
# Contact: earthdef@gps.caltech.edu                        #
############################################################
