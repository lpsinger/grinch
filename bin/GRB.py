#!/usr/bin/env python

"""
Module to define functions and attributes corresponding 
to some external trigger (a gamma-ray burst)
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"


import numpy as np
import healpy as hp
import dateutil.parser as dip
import os, json
from xml.dom.minidom import parseString as ps
from ligo.gracedb.rest import GraceDb


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

def SkyLoc(voevent):
    """ Returns sky location of trigger in RA and dec,
        given the trigger's parsed VOEvent file """

    # get elements with the relevant tag name
    RA_tag = voevent.getElementsByTagName('C1')[0].toxml()
    dec_tag = voevent.getElementsByTagName('C2')[0].toxml()

    # exterminate tags from these strings
    RA_st = RA_tag.replace('<C1>','').replace('</C1>','')
    dec_st = dec_tag.replace('<C2>','').replace('</C2>','')

    # convert these strings into numerical values
    RA = float(RA_st)
    dec = float(dec_st)
    return RA, dec

def err(voevent):
    """ Returns error radius of trigger sky location in degrees, 
        given the trigger's parsed VOEvent file """

    # get element with the relevant tag name
    err_tag = voevent.getElementsByTagName('Error2Radius')[0].toxml()

    # exterminate tags from this string
    err_st = err_tag.replace('<Error2Radius>','').replace('</Error2Radius>','')

    # convert this string into numerical values
    err = float(err_st)
    return err

def GPS_time(voevent):
    """ Returns GPSTime of the external trigger in UTC format,
        given the trigger's parsed VOEvent file """

    # get element with the relevant tag name
    iso_tag = voevent.getElementsByTagName('ISOTime')[0].toxml()
        
    # exterminate tags from this string
    iso_st = iso_tag.replace('<ISOTime>','').replace('</ISOTime>','')

    # convert ISO time to GPS time
    iso_st = dip.parse(iso_st).strftime("%B %d %Y %H:%M:%S")
    gps = int(os.popen('lalapps_tconvert '+iso_st).readline().replace('\n',''))
    return gps

def instrument(voevent):
    """ Returns name of instrument that detected the external trigger,
        given the trigger's parsed VOEvent file """

    # get element with the relevant tag name
    ins_tag = voevent.getElementsByTagName('Description')[0].toxml()

    # exterminate tags from this string
    ins_st = ins_tag.replace('<Description>','').replace('</Description>','')
    return ins_st


# define the external trigger object class
class ExtTrig:
    """ Instance of an external trigger event (i.e. gamma-ray burst) """
    def __init__(self, xml):
        self.name = os.path.splitext(xml)[0] # standard GRB designation
        self.xml = xml # name of VOEvent .xml file accompanying the GRB

        self.__file = open(xml,'r') # open and read input xml file
        self.data = self.__file.read()
        self.__file.close() # close xml (it is no longer needed)

        self.voevent = ps(self.data) # parsed VOEvent informations
        self.RA, self.dec = SkyLoc(self.voevent) # right ascention, declination
        self.err_rad = err(self.voevent) # error radius

        self.gpstime = GPS_time(self.voevent) # time of event in GPS format
        self.inst = instrument(self.voevent) # instrument that detected the event

        self.fits = self.name+'.fits' # name of .fits file for this event
        self.graceid = ''

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

    def upload(self):
        r = gracedb.createEvent("Test","GRB", self.xml).json() # create GraceDB event
        self.graceid = r['graceid'] # get graceid of the new event

        gracedb.writeLog(self.graceid,'This event detected with '+self.inst) # brief annotation

        self.write_fits() # write to a .fits file, tar it, and upload it
        os.system('tar -czf ' + self.fits + '.gz ' + self.fits)
        gracedb.writeFile(self.graceid,self.fits+'.gz')

    def submit_gracedb_log(self, message):
        """ wrapper for gracedb.writeLog() for this event """
        gracedb.writeLog(self.graceid,message)

    def search(self, tl, th):
        """ Search for coincident GW events happening within a window
            of [-tl, +th] seconds in gpstime """
        start, end = self.gpstime + tl, self.gpstime + th
        arg = 'gracedb search %s..%d' % (start, end)
        lines = os.popen(arg).readlines()
        result = []

        for line in lines: 
            x = line.split()
            result.append([x[j] for j in xrange(len(x))])

        # return list of graceids of coincident events
        if len(result) == 1: return []
        else: return [result[i][0] for i in xrange(1,len(result))]

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
                gid = result[i]
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += gid + "'>" + gid + "</a> within [-5,+1] seconds"
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
                gid = result[i]
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += gid + "'>" + gid + "</a> within [-120,+60] seconds"
                self.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/" 
                message2 += self.graceid + "'>" + self.name + "</a> within window [-120,+60] seconds"
                GraCE(gid).submit_gracedb_log(message2) # annotate GW with news of discovery
        return result
