#!/usr/bin/env python

"""
Module to define functions and attributes corresponding 
to some gravitational-wave candidate event
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"


import os
import numpy as np
import healpy as hp

from ligo.gracedb.rest import GraceDb


# initiate instance of GraceDB server as a global variable
gracedb = GraceDb()


# define function for use later
def get_fits(gw_event): 
    """ Downloads and unzips .fits file from gracedb into the 
        current working directory """
    os.system('gracedb download ' + gw_event.graceid + ' skymap.fits.gz')
    os.system('gunzip skymap.fits.gz')


# define the gravitational-wave candidate event object class
class GW:
    """ Instance of a gravitational-wave candidate event """
    def __init__(self, graceid):
        self.graceid = graceid # graceid of GW candidate
        self.fits = 'skymap.fits' # default name of fits file
        self.allsky = 'allsky_with_trigger.png' # all-sky map produced with bayestar
        self.posterior = 'post_map_rect.png' # rectangular heatmap of cross-correlation

        try: 
            get_fits(self) # download .fits file from gracedb
            #self.skymap = hp.read_map(self.fits) # array containing probability map for GW candidate
            #self.nside = hp.npix2nside(len(self.skymap)) # number of pixels per side at the equator
            #self.area = hp.nside2pixarea(self.nside, degrees=True) # area in sq. degs of a pixel
        except:
            print 'Could not find file skymap.fits.gz for event ' + self.graceid
            pass

        self._result = gracedb.events(query=self.graceid)
        for event in self._result:
            self.far = event['far']
            self.gpstime = event['gpstime']

    def plot_trig(self, grb_fits):
        """ Produces an all-sky map for this GW candidate
            indicating the external trigger, then uploads
            to GraceDB """
        os.system('plot_allsky  --output=' + self.allsky + ' --skymap=' 
            + self.fits + ' --trigger=' + grb_fits)
        gracedb.writeFile(self.graceid,self.allsky,filecontents='All-sky map with external trigger')

    def plot_xcor(self, grb_fits):
        """ Produces a rectangular heatmap of the 'convolved' probability 
            distribution for X-Y, where X is the ext trigger sky location
            and Y that of the GW candidate event, then uploads to GraceDB """
        os.system('plot_xcorrelate  --output=' + self.posterior + ' --skymap=' 
            + self.fits + ' --trigger=' + grb_fits)
        gracedb.writeFile(self.graceid,self.posterior,filecontents='Cross-correlation heatmap')

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
        else:
            coincs = []
            for event in result:
                gid = event['graceid']
                filedict = gracedb.files(gid).json()
                for key in filedict:
                    if key.endswith('.xml'):
                        voevent = key
                        break
                coincs.append([gid, voevent])
            try:
                return coincs
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
            from exttrig import GRB
            for i in xrange(len(result)):
                gid = result[i][0]
                voevent = result[i][1]
                grb = GRB(gid,voevent)
                message1 = "GW candidate found: <a href='http://gracedb.ligo.org/events/"
                message1 += self.graceid + "'>" + self.graceid + "</a> with FAR = " + self.far + " within [-5,+1] seconds"
                grb.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/"
                message2 += gid + "'>" + grb.name + "</a> within window [-5,+1] seconds"
                self.submit_gracedb_log(message2) # annotate GW with news of discovery
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
            from exttrig import GRB
            for i in xrange(len(result)):
                gid = result[i][0]
                voevent = result[i][1]
                grb = GRB(gid,voevent)
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += self.graceid + "'>" + self.graceid + "</a> with FAR = " + self.far + " within [-120,+60] seconds"
                grb.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/"
                message2 += gid + "'>" + grb.name + "</a> within window [-120,+60] seconds"
                self.submit_gracedb_log(message2) # annotate GW with news of discovery
        return result
