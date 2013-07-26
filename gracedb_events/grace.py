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
#        self.allsky = 'allsky_with_trigger.png' # all-sky map produced with bayestar
#        self.posterior = 'post_map_rect.png' # rectangular heatmap of cross-correlation

        try: 
            get_fits(self) # download .fits file from gracedb
            #self.skymap = hp.read_map(self.fits) # array containing probability map for GW candidate
            #self.nside = hp.npix2nside(len(self.skymap)) # number of pixels per side at the equator
            #self.area = hp.nside2pixarea(self.nside, degrees=True) # area in sq. degs of a pixel
        except:
            print 'ERROR: Could not find file skymap.fits.gz for event ' + self.graceid
            pass

        self.__result__ = gracedb.events(query=self.graceid)
        for event in self.__result__:
            self.far = event['far']
            self.gpstime = event['gpstime']

#    def plot_trig(self, grb_fits):
#        """ Produces an all-sky map for this GW candidate
#            indicating the external trigger, then uploads
#            to GraceDB """ 
#        current = os.getcwd() + '/'
#        os.system('plot_allsky  --output=' + self.allsky + ' --skymap=' + current
#            + self.fits + ' --trigger=' + grb_fits)
#        gracedb.writeFile(self.graceid,self.allsky,filecontents='All-sky map with external trigger')
#
#    def plot_xcor(self, grb_fits):
#        """ Produces a rectangular heatmap of the 'convolved' probability 
#            distribution for X-Y, where X is the ext trigger sky location
#            and Y that of the GW candidate event, then uploads to GraceDB """
#        current = os.getcwd() + '/'
#        os.system('plot_xcorrelate  --output=' + self.posterior + ' --skymap=' + current
#            + self.fits + ' --trigger=' + grb_fits)
#        gracedb.writeFile(self.graceid,self.posterior,filecontents='Convolved probability heatmap')

    def plot_dag(self, grb_fits, RA, dec):
        """ Create and submit a dag that produces and uploads plots to gracedb """

        trig_sub = """\
universe            = vanilla

executable          = /usr/bin/env
arguments           = plot_allsky -o skymap_with_triggers.png --contour=50 --contour=90 -radec %(RA)s %(dec)s %(fits)s 
getenv              = True
notification        = never

error               = allsky_$(cluster)-$(process).err
output              = allsky_$(cluster)-$(process).out

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True

Queue
"""
        with open('plot_allsky_w_trigger.sub', 'w') as f:
            f.write(trig_sub%{'uid':self.graceid,'RA':RA,'dec':dec,'fits':self.fits})

        xcor_sub = """\
universe            = vanilla

executable          = /usr/bin/env
arguments           = plot_xcorrelate --output=convolved_prob_heatmap.png  --skymap=%(skymap)s --trigger=%(trigger)s 
getenv              = True
notification        = never

error               = heatmap_$(cluster)-$(process).err
output              = heatmap_$(cluster)-$(process).out

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True

Queue
"""
        with open('plot_heatmap.sub', 'w') as f:
            f.write(xcor_sub%{'uid':self.graceid,'skymap':self.fits,'trigger':grb_fits})

        dag = """\
JOB PLOTALLSKY plot_allsky_w_trigger.sub
SCRIPT POST PLOTALLSKY /usr/bin/gracedb upload skymap_with_triggers.png

JOB HEATMAP plot_heatmap.sub
SCRIPT POST HEATMAP /usr/bin/gracedb upload convolved_prob_heatmap.png
"""
        with open('plot_runner.dag', 'w') as f:
            f.write(dag)

        # Create uniquely named log file.
        logfid, logpath = tempfile.mkstemp(suffix='.nodes.log', prefix=self.graceid)

        # Set environment variable telling condor to use this log file
        # for communication with nodes.
        os.environ['_CONDOR_DAGMAN_DEFAULT_NODE_LOG'] = logpath

        # submit dag
        condorargs=['condor_submit_dag','plot_runner.dag']
        os.execlp('condor_submit_dag', *condorargs)

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
        except HTTPError:
            import sys
            print "Problem accessing GraCEDb while calling gracedb_events.grace.GW.search()"
            raise HTTPError
            sys.exit(1)

    # define special attributes for short- and long-duration GRB coincidence searches
    def short_search(self):
        """ Speecialized short-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result = [event for event in self.search(-1, 5) if event['graceid'] == 'E']
        if result == []:
            message = 'No external triggers in window [-1,+5] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
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
                grb = GRB(gid,voevent)
                message1 = "GW candidate found: <a href='http://gracedb.ligo.org/events/"
                message1 += self.graceid + "'>" + self.graceid + "</a> with FAR = %s within [-5,+1] seconds" % self.far
                grb.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/"
                message2 += gid + "'>" + grb.name + "</a> within window [-5,+1] seconds"
                self.submit_gracedb_log(message2) # annotate GW with news of discovery
        return result

    def long_search(self):
        """ Speecialized long-duration coincidence search; also annotates
            relevant events with brief overview of results """
        result1 = [event for event in self.search(-60, -1) if event['graceid'] == 'E']
        result2 = [event for event in self.search(5, 120) if event['graceid'] == 'E']
        result = result1 + result2 # must ensure the two searches do not overlap
        if result == []:
            message = 'No external triggers in window [-60,+120] seconds'
            self.submit_gracedb_log(message) # annotate GRB with news of lack of news
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
                grb = GRB(gid,voevent)
                message1 = "GW candidate found; <a href='http://gracedb.ligo.org/events/"
                message1 += self.graceid + "'>" + self.graceid + "</a> with FAR = %s within [-120,+60] seconds" % self.far
                grb.submit_gracedb_log(message1) # annotate GRB with news of discovery
                message2 = "External trigger <a href='http://gracedb.ligo.org/events/"
                message2 += gid + "'>" + grb.name + "</a> within window [-120,+60] seconds"
                self.submit_gracedb_log(message2) # annotate GW with news of discovery
        return result
