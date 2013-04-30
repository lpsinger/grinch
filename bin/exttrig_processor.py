#!/usr/bin/env python

__author__ = "Alex Urban <alexander.urban@ligo.org>"

import os

from sys import stdin, exit
from ligo.gracedb.rest import GraceDb
from ligo.lvalert.utils import get_LVAdata_from_stdin


# initialize instance of gracedb rest API
gracedb = GraceDb()

# create dictionary from gracedb table
streamdata = get_LVAdata_from_stdin(stdin, as_dict=True)

# test whether this event is new
if streamdata['alert_type'] == 'new':
    pass
else:
     exit()

# create working directory for the trigger
home = os.getenv("HOME")
working = home + '/working/ExtTrig/%s' % streamdata['uid']
try:
    os.mkdir(working)
except OSError:
    print 'Could not make directory %s' % working
    pass

# change current working directory
os.chdir(working)

# get info
xml = streamdata['file'] # CLEAN THIS UP; THIS IS WHERE YOU LEFT OFF
gracedb.files(streamdata['uid'],filename=xml)
