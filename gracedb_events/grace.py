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
    gracedb.files(gw_event.graceid,filename='skymap.fits.gz')
    os.system('gunzip skymap.fits.gz')


# define the gravitational-wave candidate event object class
class GW:
    """ Instance of a gravitational-wave candidate event """
    def __init__(self, graceid):
        self.graceid = graceid # graceid of GW candidate
        self.fits = 'skymap.fits' # default name of fits file
        self.allsky = 'allsky_with_trigger.png' # all-sky map produced with bayestar
        self.posterior = 'post_map_rect.png' # rectangular heatmap of cross-correlation
        get_fits(self) # download .fits file from gracedb
        self.skymap = hp.read_map(self.fits) # array containing probability map for GW candidate
        self.nside = hp.npix2nside(len(self.skymap)) # number of pixels per side at the equator
        self.area = hp.nside2pixarea(self.nside, degrees=True) # area in sq. degs of a pixel

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
