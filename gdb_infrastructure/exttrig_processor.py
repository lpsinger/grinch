#!/usr/bin/env python

"""
Module to define functions and attributes corresponding 
to some external trigger (a gamma-ray burst)
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"

import os
from GRB import ExtTrig
from optparse import Option, OptionParser

# read in options from command line
opts, args = OptionParser(
    description = __doc__,
    usage = "%prog [options] [INPUT]",
    option_list = [
        Option("-t","--trigger",metavar="FILE.xml",
            help="name of VOEvent .xml file containing skymap of external trigger")
    ]
).parse_args()

# initialize ExtTrig object corresponding to the GRB trigger
trig = ExtTrig(opts.trigger)

# create working directory for the trigger
home = os.getenv("HOME")
working = home + '/working/ExtTrig/' + trig.name
test = os.path.exists(working)
if test == False: os.mkdir(working)

# move xml and change current working directory
os.system('mv ' + trig.xml + ' ' + working)
os.chdir(working)

# upload trigger to gracedb and inform the database that shite is about to go down
#note = 'Initiating coincidence search'
#trig.upload()
#trig.submit_gracedb_log(note)


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

        working2 = home + '/working/GW/' + coincs[i]
        test2 = os.path.exists(working2)
        if test2 == False: os.mkdir(working2)
        os.chdir(working2) # move to GW event working directory

        event = GraCE(coincs[i]) # initialize object of class GW
        event.plot_trig(trigfits) # plot and upload skymap with trigger
        event.plot_xcor(trigfits) # plot and upload cross-correlation

# finally, the long-duration search
coincs2 = trig.long_search()

note2 = 'Coincidence search complete'
trig.submit_gracedb_log(note2)
