#!/usr/bin/env python

"""
Module to define functions and attributes corresponding 
to some gravitational-wave candidate event
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"


import os
import tempfile
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


# define the gravitational-wave candidate event object class
class GW:
    """ Instance of a gravitational-wave candidate event """
    def __init__(self, graceid):
        self.graceid = graceid # graceid of GW candidate
        self.fits = 'skymap.fits.gz' # default name of fits file

        try: 
            get_fits(self) # download .fits file from gracedb
        except:
            print 'ERROR: Could not find file skymap.fits.gz for event ' + self.graceid
            pass

        self.__result__ = gracedb.events(query=self.graceid)
        for event in self.__result__:
            self.far = event['far']
            self.gpstime = event['gpstime']

    def submit_gracedb_log(self, message, tagname=None):
        """ wrapper for gracedb.writeLog() for this event """
        gracedb.writeLog(self.graceid,message,tagname=tagname)

    def search(self, tl, th):
        """ Search for coincident GW events happening within a window
            of [-tl, +th] seconds in gpstime """
        start, end = self.gpstime + tl, self.gpstime + th
        arg = '%s..%d' % (start, end)

        # return list of graceids of coincident events
        try:
            return list(gracedb.events(arg))
        except HTTPError:
            import sys
            print "Problem accessing GraCEDb while calling gracedb_events.grace.GW.search()"
            raise HTTPError
            sys.exit(1)

    # define special attributes for short- and long-duration GRB coincidence searches
    def short_search(self):
        """ Speecialized short-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result = [event for event in self.search(-1, 5) if event['graceid'][0] == 'E']
        if result == []:
            message = 'No external triggers in window [-1,+5] seconds'
            self.submit_gracedb_log(message, tagname="ext_coinc") # annotate GRB with news of lack of news
        else:
            from exttrig import GRB
            for i in xrange(len(result)):
                gid = result[i]['graceid']
                filedict = gracedb.files(gid).json()
                for key in filedict: # search for this trigger's VOEvent file
                    if key.endswith('.xml'):
                        voevent = key
                        result[i]['file'] = voevent
                        break
                os.system('/usr/bin/gracedb download %s %s' % (gid, voevent))
                grb = GRB(gid,voevent)
                message1 = "GW candidate found: <a href='http://gracedb.ligo.org/events/"
                message1 += self.graceid + "'>" + self.graceid + "</a> with FAR = %s within [-5,+1] seconds" % self.far
                grb.submit_gracedb_log(message1, tagname="ext_coinc") # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/"
                message2 += gid + "'>" + grb.name + "</a> within window [-5,+1] seconds"
                self.submit_gracedb_log(message2, tagname="ext_coinc") # annotate GW with news of discovery
        return result

    def long_search(self):
        """ Speecialized long-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result1 = [event for event in self.search(-60, -1) if event['graceid'][0] == 'E']
        result2 = [event for event in self.search(5, 120) if event['graceid'][0] == 'E']
        result = result1 + result2 # must ensure the two searches do not overlap
        if result == []:
            message = 'No external triggers in window [-60,+120] seconds'
            self.submit_gracedb_log(message, tagname="ext_coinc") # annotate GRB with news of lack of news
        else:
            from exttrig import GRB
            for i in xrange(len(result)):
                gid = result[i]['graceid']
                filedict = gracedb.files(gid).json()
                for key in filedict: # search for this trigger's VOEvent file
                    if key.endswith('.xml'):
                        voevent = key
                        result[i]['file'] = voevent
                        break
                os.system('/usr/bin/gracedb download %s %s' % (gid, voevent))
                grb = GRB(gid,voevent)
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += self.graceid + "'>" + self.graceid + "</a> with FAR = %s within [-120,+60] seconds" % self.far
                grb.submit_gracedb_log(message1, tagname="ext_coinc") # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/"
                message2 += gid + "'>" + grb.name + "</a> within window [-120,+60] seconds"
                self.submit_gracedb_log(message2, tagname="ext_coinc") # annotate GW with news of discovery
        return result

    def hardware_search(self):
        result = [event for event in self.search(-5, 5) if event['graceid'][0] == 'H']
        if result == []:
            message = 'No unblind injections in window [-5,+5] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
        else:
            for i in xrange(len(result)):
                gid = result[i]['graceid']
                filedict = gracedb.files(gid).json()
                for key in filedict: # search for this injection's sim_inspiral table
                    if key.endswith('.xml.gz'):
                        sim_inspiral_table = key
                        result[i]['file'] = sim_inspiral_table
                        break
                message = "Unblind injection <a href='http://gracedb.ligo.org/events/"
                message += "%s'>%s</a> within window [-5,+5] seconds; " % (gid, gid)
                self.submit_gracedb_log(message) # annotate GW with news of discovery
        return result
