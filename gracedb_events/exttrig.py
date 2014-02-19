#!/usr/bin/env python

"""
Module to define functions and attributes corresponding 
to some external (non-gravitational) trigger
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"


# imports
import numpy as np
import healpy as hp
import dateutil.parser as dip
import os
import VOEventLib.VOEvent
import VOEventLib.Vutil

from ligo.gracedb.rest import GraceDb
from lalinference.bayestar import fits
from math import floor


# initiate instance of GraceDB server as a global variable
gracedb = GraceDb()


# define functions
def kappa(err):
	""" Approximant to the von Mises-Fisher concentration parameter """
	R = np.exp( -err**2 / 2 )
	return R * (3 - R**2) / (1 - R**2)

def pdf(n, nside, theta0, phi0, err):
	""" Posterior probability density function for the sky location of the
	    external trigger, fit to a von Mises-Fisher distribution on the unit
	    sphere. """
	# If you're already in the most probable pixel, return unity.
	if n == hp.ang2pix(nside, theta0, phi0): return 1.

	# Otherwise, calculate and return the unnormalized probability in this pixel.
	else:
		k = kappa(err)
		th, ph = hp.pix2ang(nside, n)
		xi = k * ( ( np.sin(theta0) * np.sin(th) * np.cos(ph - phi0) ) + ( np.cos(theta0) * np.cos(th) ) - 1 )
		return np.exp( xi )

def Cacc(psky):
	""" Estimator for the cumulative fraction of accidental associations with
	    sky coincidence better than psky. """
	if rho_sky < 1e-50: return 1.
	x = np.log10(rho_sky)
	p = [6.43375601e+00, -3.83233594e+04, 1.35768892e+01]
	return p[0] * x**3 / (p[1] + p[2]*x**3)


def stream(voevent):
	""" Returns name of event stream that detected the external trigger,
		given the trigger's parsed VOEvent file """
	role = voevent.get_role() # observation, test, or utility
	ivorn = voevent.get_ivorn() # get the identifier of the event

	# get the part of the ivorn that is the stream identifier
	streamIvorn = ivorn.split('#')[0]

	# get element with the relevant tag name
	ins_tag = streamIvorn + ' ' + role

	return ins_tag


# define the external trigger object class
class GRB(object):
	""" Instance of an external trigger event (i.e. gamma-ray burst) """
	def __init__(self, graceid, xml):
		self.graceid = graceid
		self.xml = xml # standard GRB designation
		self.name = os.path.splitext(xml)[0] # name of VOEvent .xml file accompanying the GRB

		self.voevent = VOEventLib.Vutil.parse(xml) # parsed VOEvent informations
		wwd = VOEventLib.Vutil.getWhereWhen(self.voevent)
		self.RA, self.dec = wwd['longitude'], wwd['latitude'] # right ascention, declination
		self.err_rad = wwd['positionalError'] # error radius
		self.inst = stream(self.voevent) # instrument that detected the event
		self.fits = self.name+'.fits.gz' # name of .fits file for this event
		self.gpstime = int(floor(fits.iso8601_to_gps(wwd['time'])))

	def submit_gracedb_log(self, message, filename=None, tagname=None):
		""" Wrapper for gracedb.writeLog() for this event """
		if filename is not None: gracedb.writeLog(self.graceid, message, filename, tagname=tagname)
		else: gracedb.writeLog(self.graceid, message, tagname=tagname)

	def sky_map(self, nside):
		""" Returns a numpy array equivalent to the one that would get written
		    to a FITS file for this event """
		# convert RA, dec and error radius to standard spherical coordinates
		theta, phi, err = np.deg2rad( (90. - self.dec, self.RA, self.err_rad) )

		# calculate the probability distribution and store it in a skymap
		npix = hp.nside2npix(nside)
		trig_map = np.array( [pdf(i, nside, theta, phi, err) for i in xrange(npix)] )
		trig_map /= np.sum(trig_map) # normalize

		return trig_map

	def write_fits(self, sky_map, publish=False):
		""" Given sky location and error radius of an external trigger, fit
		    it to a von Mises-Fisher distribution and write to a HEALPix .fits
		    file whose name is supplied """
 
		# write to a .fits file
		fits.write_sky_map(self.fits, trig_map, objid=self.graceid, gps_time=self.gpstime)

		# publish to GraceDB if desired
		if publish: self.submit_gracedb_log(self.graceid, "Uploaded sky map",
			filename=self.fits, tagname="sky_loc")

	def search(self, tl, th):
		""" Search for coincident GW events happening within a window
			of [-tl, +th] seconds in gpstime """
		start, end = self.gpstime + tl, self.gpstime + th
		arg = '%s..%d' % (start, end)

		# return list of graceids of coincident events
		try: 
			return list(gracedb.events(arg))
		except:
			import sys
			print "Problem accessing GraCEDb while calling gracedb_events.exttrig.GRB.search()"
			sys.exit(1)

	# define special attributes for short- and long-duration GRB coincidence searches
	def short_search(self):
		""" Speecialized short-duration coincidence search; also annotates
		    relevant events with brief overview of results """
		results = [event for event in self.search(-5, 1) if event['graceid'][0] == 'G' or event['graceid'][0] == 'T']
		if results == []:
			message = 'No GW candidates in window [-5,+1] seconds'
			self.submit_gracedb_log(message, tagname="ext_coinc") # annotate GRB with news of lack of news
		else: 
			from grace import GW
			for result in results:
				gid = result['graceid']
				far = np.float64( result['far'] )
				message1 = "Raven: GW candidate found: <a href='http://gracedb.ligo.org/events/"
				message1 += gid + "'>" + gid + "</a> with untriggered FAR = %s Hz within [-5,+1] seconds" % far
				self.submit_gracedb_log(message1, tagname="ext_coinc") # annotate GRB with news of discovery
				message2 = "Raven: External trigger <a href='http://gracedb.ligo.org/events/" 
				message2 += self.graceid + "'>" + self.name + "</a> within window [-5,+1] seconds"
				GW(gid).submit_gracedb_log(message2, tagname="ext_coinc") # annotate GW with news of discovery
		return results

	def long_search(self):
		""" Speecialized long-duration coincidence search; also annotates
		    relevant events with brief overview of results """
		result1 = [event for event in self.search(-120, -5) if event['graceid'][0] == 'G' or event['graceid'][0] == 'T']
		result2 = [event for event in self.search(1, 60) if event['graceid'][0] == 'G' or event['graceid'][0] == 'T']
		results = result1 + result2 # must ensure the two searches do not overlap
		if results == []:
			message = 'No GW candidates in window [-120,+60] seconds'
			self.submit_gracedb_log(message, tagname="ext_coinc") # annotate GRB with news of lack of news
		else: 
			from grace import GW
			for result in results:
				gid = result['graceid']
				far = result['far']
				message1 = "Raven: GW candidate found; <a href='http://gracedb.ligo.org/events/"
				message1 += gid + "'>" + gid + "</a> with untriggered FAR = %s Hz within [-120,+60] seconds" % far
				self.submit_gracedb_log(message1, tagname="ext_coinc") # annotate GRB with news of discovery
				message2 = "Raven: External trigger <a href='http://gracedb.ligo.org/events/" 
				message2 += self.graceid + "'>" + self.name + "</a> within window [-120,+60] seconds"
				GW(gid).submit_gracedb_log(message2, tagname="ext_coinc") # annotate GW with news of discovery
		return results

	def calc_signif_gracedb(self, coinc, gw_sky_map, short=True):
		""" Calculate the improvement in significance that is got out of the second tier
		    of this hierarchical GRB-triggered search. """
		nside = hp.npix2nside( len(gw_sky_map) )
		grb_sky_map = self.sky_map(nside)
		psky = (4 * np.pi)**2 * np.sum( [x * y for x, y in zip(gw_sky_map, grb_sky_map)] ) / len(gw_sky_map)
		if short: far = 6 * 1.268e-6 * Cacc( psky ) * coinc['far']
		else : far = 180 * 1e-5 * Cacc( psky ) * coinc['far']
		message = "Raven: Spatiotemporal coincidence with external trigger <a href='http://gracedb.ligo.org/events/"
		message += self.graceid + "'>" + self.name + "</a> gives a coincident FAR = %s Hz" % far
		GW(coinc['graceid']).submit_gracedb_log(message, tagname="ext_coinc")
