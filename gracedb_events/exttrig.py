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
def normal(x, x0, s):
    """ define unnormalized Gaussian distribution centred at x0
        with standard deviation s """
    return np.exp(-(x - x0)**2/(2*s**2))

def pdf(n, nside, theta0, phi0, err):
    """ define probability distribution for external trigger
        as a function of index n and assuming very small 
        error radius """
    k = hp.ang2pix(nside, theta0, phi0)
    if n == k: th, ph = theta0, phi0 
    else: th, ph = hp.pix2ang(nside, n)
    s1 = np.deg2rad(err)
    s2 = abs(np.sin(theta0))*s1
    return normal(ph, phi0, s1)*normal(np.cos(th),np.cos(theta0),s2)

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

    def write_fits(self):
        """ Given sky location and error radius of an external trigger, 
            fit it to a Gaussian distribution and write to a HEALPix 
            .fits file whose name is supplied """
        nside = 128 # default

        # convert RA and dec to standard spherical coordinates
        theta = np.deg2rad(90 - self.dec)
        phi = np.deg2rad(self.RA)

        # calculate the probability distribution and store it in a skymap
        npix = hp.nside2npix(nside)
        trig_map = np.array([0.0]*npix)

        for i in xrange(npix): trig_map[i] = pdf(i, nside, theta, phi, self.err_rad)
        trig_map /= np.sum(trig_map) # normalize
 
        # write to a .fits file and upload to GraCEDb
        fits.write_sky_map(self.fits, trig_map, objid=self.graceid, gps_time=self.gpstime)
        gracedb.writeLog(self.graceid, "Uploaded sky map", self.fits, tagname="sky_loc")

    def submit_gracedb_log(self, message):
        """ wrapper for gracedb.writeLog() for this event """
        gracedb.writeLog(self.graceid,message)

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
        result = [event for event in self.search(-5, 1) if event['graceid'][0] == 'G']
        if result == []:
            message = 'No GW candidates in window [-5,+1] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
        else: 
            from grace import GW
            for i in xrange(len(result)):
                gid = result[i]['graceid']
                far = result[i]['far']
                message1 = "GW candidate found: <a href='http://gracedb.ligo.org/events/"
                message1 += gid + "'>" + gid + "</a> with FAR = %s within [-5,+1] seconds" % far
                self.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/" 
                message2 += self.graceid + "'>" + self.name + "</a> within window [-5,+1] seconds"
                GW(gid).submit_gracedb_log(message2) # annotate GW with news of discovery
        return result

    def long_search(self):
        """ Speecialized long-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result1 = [event for event in self.search(-120, -5) if event['graceid'][0] == 'G']
        result2 = [event for event in self.search(1, 60) if event['graceid'][0] == 'G']
        result = result1 + result2 # must ensure the two searches do not overlap
        if result == []:
            message = 'No GW candidates in window [-120,+60] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
        else: 
            from grace import GW
            for i in xrange(len(result)):
                gid = result[i]['graceid']
                far = result[i]['far']
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += gid + "'>" + gid + "</a> with FAR = %s within [-120,+60] seconds" % far
                self.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/" 
                message2 += self.graceid + "'>" + self.name + "</a> within window [-120,+60] seconds"
                GW(gid).submit_gracedb_log(message2) # annotate GW with news of discovery
        return result
