#!/usr/bin/env python

"""
Script to execute temporal coincidence search 
for  external triggers
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"

import os

from GRB import gracedb, ExtTrig
from optparse import Option, OptionParser


# read in options from command line
opts, args = OptionParser(
    description = __doc__,
    usage = "%prog [options] [INPUT]",
    option_list = [
        Option("-g","--graceid",help="graceid of external trigger event"),
        Option("-x","--xml",metavar="FILE.xml",help="VOEvent .xml file of external trigger")
    ]
).parse_args()

# create working directory for the trigger
home = os.getenv("HOME")
working = home + '/working/ExtTrig/' + opts.graceid
test = os.path.exists(working)
if test == False: os.mkdir(working)

# change current working directory and download VOEvent .xml file
os.chdir(working)
gracedb.files(opts.graceid,filename=opts.xml)
trig = ExtTrig(opts.trigger,opts.xml)
trig.write_fits()

# inform GraCEDb things are about to go down
note = 'Initiating coincidence search'
trig.submit_gracedb_log(note)


#####################################
# initiate the coincidence searches #
#####################################

# first, the short-duration search
coincs = trig.short_search()
if coincs != []: # produce plots and skymaps if there is a non-null result
    from GW import GraCE
    for i in xrange(len(coincs)):
        trigdir = os.getcwd() + '/'
        trigfits = trigdir + trig.fits # will need the path to this file

        working2 = home + '/working/GW/' + coincs[i][0]
        test2 = os.path.exists(working2)
        if test2 == False: os.mkdir(working2)
        os.chdir(working2) # move to GW event working directory

        event = GraCE(coincs[i][0]) # initialize object of class GW
        event.plot_trig(trigfits) # plot and upload skymap with trigger
        event.plot_xcor(trigfits) # plot and upload cross-correlation

# finally, the long-duration search
coincs2 = trig.long_search()

note2 = 'Coincidence search complete'
trig.submit_gracedb_log(note2)
