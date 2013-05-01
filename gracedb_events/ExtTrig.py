#!/usr/bin/env python

"""
Module to define functions and attributes corresponding 
to some external trigger (a gamma-ray burst)
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"


import numpy as np
import healpy as hp
import dateutil.parser as dip
import os
from ligo.gracedb.rest import GraceDb
import VOEventLib.VOEvent
import VOEventLib.Vutil


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
    th, ph = hp.pix2ang(nside, n)
    s1 = np.deg2rad(err)
    s2 = abs(np.sin(s1))
    return normal(ph, phi0, s1)*normal(-np.cos(th),-np.cos(theta0),s2)*np.sin(th)

def GPS_time(wwd):
    """ Returns GPSTime of the external trigger in UTC format,
        given the trigger's parsed VOEvent file """

    # get UTC time of the trigger
    iso_st = wwd['time']

    # convert ISO time to GPS time
    iso_st = dip.parse(iso_st).strftime("%B %d %Y %H:%M:%S")
    gps = int(os.popen('lalapps_tconvert '+iso_st).readline().replace('\n',''))
    return gps

def stream(voevent):
    """ Returns name of event stream that detected the external trigger,
        given the trigger's parsed VOEvent file """

    role = voevent.get_role() # observation, test, or utility

    ivorn = voevent.get_ivorn() # get the identifier of the event

    # get the part of the ivorn that is the stream identifier
    streamIvorn = ivorn.split('#')[0]

    # get element with the relevant tag name
    ins_tag = streamIvorn + ' ' + role

    return ins_st


# define the external trigger object class
class ExtTrig:
    """ Instance of an external trigger event (i.e. gamma-ray burst) """
    def __init__(self, graceid, xml):
        self.graceid = graceid
        self.xml = xml # standard GRB designation
        self.name = os.path.splitext(xml)[0] # name of VOEvent .xml file accompanying the GRB

        self.voevent = VOEventLib.Vutil.parse(xml) # parsed VOEvent informations
        wwd = VOEventLib.Vutil.getWhereWhen(self.voevent)
        self.RA, self.dec = wwd['longitude'], wwd['latitude'] # right ascention, declination

        self.err_rad = wwd['positionalError'] # error radius

        self.gpstime = GPS_time(wwd) # time of event in GPS format
        self.inst = stream(self.voevent) # instrument that detected the event

        self.fits = self.name+'.fits' # name of .fits file for this event

    def write_fits(self):
        """ Given sky location and error radius of an external trigger 
            (object class GRB.ExtTrig), fit it to a Gaussian distribution
            and write to a HEALPix .fits file whose name is supplied """
        # if error radius is smaller than a third of pixel radius, regard as a delta function
        nside = 32 # default
        pixar = hp.nside2pixarea(nside, degrees=True)

        # convert RA and dec to standard spherical coordinates
        theta = np.deg2rad(90 - self.dec)
        phi = np.deg2rad(self.RA)

        # calculate the probability distribution and write it to a .fits file
        npix = hp.nside2npix(nside)
        trig_map = np.array([0.0]*npix)

        for i in xrange(npix): trig_map[i] = pdf(i,nside,theta,phi,self.err_rad)
        trig_map /= np.sum(trig_map) # normalize
        hp.write_map(self.fits,trig_map) # write trigger skymap to .fits

        os.system('tar -czf ' + self.fits + '.gz ' + self.fits)
        gracedb.writeFile(self.graceid,self.fits+'.gz')

    def submit_gracedb_log(self, message):
        """ wrapper for gracedb.writeLog() for this event """
        gracedb.writeLog(self.graceid,message)

    def search(self, tl, th):
        """ Search for coincident GW events happening within a window
            of [-tl, +th] seconds in gpstime """
        start, end = self.gpstime + tl, self.gpstime + th
        arg = '%s..%d' % (start, end)
        result = gracedb.events(query=arg)

        # return list of graceids of coincident events
        if len(list(result)) == 0: return []
        try: 
            return [[event['graceid'],event['far']] for event in result]
        except HTTPError:
            return []

    # define special attributes for short- and long-duration GRB coincidence searches
    def short_search(self): 
        """ Speecialized short-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result = self.search(-5, 1)
        if result == []:
            message = 'No GW candidates in window [-5,+1] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
        else: 
            from GW import GraCE
            for i in xrange(len(result)):
                gid = result[i][0]
                far = result[i][1]
                message1 = "GW candidate found: <a href='http://gracedb.ligo.org/events/"
                message1 += gid + "'>" + gid + "</a> with FAR = " + far + " within [-5,+1] seconds"
                self.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/" 
                message2 += self.graceid + "'>" + self.name + "</a> within window [-5,+1] seconds"
                GraCE(gid).submit_gracedb_log(message2) # annotate GW with news of discovery
        return result

    def long_search(self):
        """ Speecialized long-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result1 = self.search(-120, -5)
        result2 = self.search(1, 60)
        result = result1 + result2 # must ensure the two searches do not overlap
        if result == []:
            message = 'No GW candidates in window [-120,+60] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
        else: 
            from GW import GraCE
            for i in xrange(len(result)):
                gid = result[i][0]
                far = result[i][1]
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += gid + "'>" + gid + "</a> with FAR = " + far + " within [-120,+60] seconds"
                self.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/" 
                message2 += self.graceid + "'>" + self.name + "</a> within window [-120,+60] seconds"
                GraCE(gid).submit_gracedb_log(message2) # annotate GW with news of discovery
        return result
