#!/usr/bin/python

__author__ = "Alex Urban <alexander.urban@ligo.org>"

import os
import tempfile
import urlparse
import ConfigParser

from sys             import exit, stdin
from string          import split

from workflow_helper import directory, home
from ligo.lvalert.utils import get_LVAdata_from_stdin
from ligo.gracedb.rest import GraceDb


# initialize instance of gracedb rest API
gracedb = GraceDb()


# read in exttrig_config.ini
cp = ConfigParser.ConfigParser()
etc = home + '/opt/etc/'
cp.read(etc+'exttrig_config.ini')

gracedbcommand = cp.get('executable','gracedbcommand')
coinc_search   = cp.get('executable','coincscript')


# create dictionary from gracedb table
streamdata = get_LVAdata_from_stdin(stdin, as_dict=True)

# test whether this event is new
if streamdata['alert_type'] == 'new':
    pass
else: # if not, do nothing
     exit()


# create working directory for the trigger and move to it
working = directory(streamdata['uid'])
working.build_and_move()

# grab the VOEvent .xml file from gracedb
voevent = split(urlparse.urlparse(streamdata['file']).path,'/')[-1]
os.system('gracedb download ' + streamdata['uid'] + ' ' + voevent)


##############################
## PRODUCE CONDOR SUB FILES ##
##############################

# write coinc_search.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = --graceid=%(uid)s --xml=%(voevent)s --direction=forward
getenv              = True
notification        = never

output              = coinc_search.out
error               = coinc_search.error

Queue
"""
with open('coinc_search.sub', 'w') as f:
    f.write(contents%{'script':coinc_search,'uid':streamdata['uid'],'voevent':voevent})


#################################
## WRITE CONDOR DAG AND SUBMIT ##
#################################

contents = """\
JOB COINCSEARCH coinc_search.sub

"""
with open('exttrig_runner.dag', 'w') as f:
    f.write(contents % {'gracedbcommand': gracedbcommand, 'uid': streamdata['uid']})

# Create uniquely named log file.
logfid, logpath = tempfile.mkstemp(suffix='.nodes.log', prefix=streamdata['uid'])

# Set environment variable telling condor to use this log file
# for communication with nodes.
os.environ['_CONDOR_DAGMAN_DEFAULT_NODE_LOG'] = logpath

# submit dag
condorargs=['condor_submit_dag','exttrig_runner.dag']
os.execlp('condor_submit_dag', *condorargs)
