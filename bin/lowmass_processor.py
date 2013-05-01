#! /usr/bin/python

import os
import os.path
import tempfile
import urlparse
import re
import ConfigParser
import shutil

from sys             import exit, stdin

from workflow_helper import directory
from glue.ligolw     import ligolw
from glue.ligolw     import utils
from glue.ligolw     import table
from glue.ligolw     import lsctables
from ligo.lvalert.utils import get_LVAdata_from_stdin
import ligo.gracedb.rest


## create dict from gracedb table
streamdata = get_LVAdata_from_stdin(stdin, as_dict=True)


## read lowmass_config.ini
cp = ConfigParser.ConfigParser()
home = os.getenv("HOME")
etc = home + '/opt/etc/'
cp.read(etc+'lowmass_config.ini')

gracedbcommand     = cp.get('executable','gracedbcommand')
dqwaitscript       = cp.get('executable','dqwaitscript')
dqtolabelscript    = cp.get('executable','dqtolabelscript')
skypointscript     = cp.get('executable','skypointscript')
coincdetscript     = cp.get('executable','coincdetscript')

vetodefinerfile    = cp.get('veto','vetodefinerfile')
ranksfile          = cp.get('skypoints','ranksfile')
gridsfile          = cp.get('skypoints','gridsfile')
coincdetconfig     = cp.get('coincdet','configfile')


# build and move to a unique working directory
working = directory(streamdata['uid'])
working.build_and_move()


## if labeled EM_READY
if streamdata['alert_type'] == 'label' and streamdata['description'] == 'EM_READY':
    import bayestar.lvalert
    bayestar.lvalert.respond(streamdata['uid'],submit=True)
    ## function ends processor

## check if new
elif  streamdata['alert_type'] == 'new':
    pass

## else
else:
     exit()

## extract information about the event
if re.search('.xml',streamdata['file']):
     coincfile = urlparse.urlparse(streamdata['file'])[2]
else: # download coinc file from gracedb web client; stick it in the working directory
    gracedb_client = ligo.gracedb.rest.GraceDb()
    remote_file = gracedb_client.files(streamdata['uid'], 'coinc.xml')
    with open('coinc.xml', 'w') as local_file:
        shutil.copyfileobj(remote_file, local_file)
    coincfile = 'coinc.xml'
doc        = utils.load_filename(coincfile)
coinctable = table.get_table(doc,lsctables.CoincInspiralTable.tableName)

gpstime    = coinctable[0].end_time
ifonames   = ['H1','L1','V1']
if 'test' in cp.sections():
     ifos = cp.get('test','ifos')
else:
     ifos = coinctable[0].ifos
disable_ifos = [ifo for ifo in ifonames if ifo not in ifos]
itime        = str(int(float(gpstime)+0.5))


## write skypoints.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = --glob=%(coincfile)s --ranks=%(ranksfile)s --grids=%(gridsfile)s
getenv              = True
notification        = never

output              = skypoints.out
error               = skypoints.error

+LVAlertListen      = %(uid)s_skypoints
Queue
"""
with open('skypoints.sub', 'w') as f:
    f.write(contents%{'script':skypointscript,'coincfile':coincfile,'ranksfile':ranksfile,'gridsfile':gridsfile,'uid':streamdata['uid']})

## write data quality.sub
contents   = """\
universe            = local

executable          = /bin/cp
arguments           = /home/gdb_processor/dq-fake.xml dq.xml
getenv              = True
notification        = never

output              = dq.out
error               = dq.error

+LVAlertListen      = %(uid)s_dq
Queue
"""
with open('dq.sub', 'w') as f:
    f.write(contents%{'uid':streamdata['uid']})

## write emlabel.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = --set-em-ready -f dq.xml -i %(uid)s -g %(gdbcommand)s --veto-definer-file %(vetodefinerfile)s
getenv              = True
notification        = never

error               = emlabel.err
output              = emlabel.out

+LVAlertListen      = %(uid)s_emlabel
Queue
"""
with open('emlabel.sub','w') as f:
    f.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'uid':streamdata['uid']})

## write coincdet.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = test_lowmass %(uid)s %(coincfile)s %(configfile)s
getenv              = True
notification        = never

error               = coincdet.err
output              = coincdet.out

+LVAlertListen      = %(uid)s_coincdet

Queue
"""
with open('coincdet.sub', 'w') as f:
    f.write(contents%{'script':coincdetscript,'coincfile':coincfile,'configfile':coincdetconfig,'uid':streamdata['uid']})

## write localize.sub
contents   = """\
universe            = local

executable          = /usr/bin/env
arguments           = bayestar_localize_lvalert %(uid)s
getenv              = True
notification        = never

error               = localize.err
output              = localize.out

+LVAlertListen      = %(uid)s_localize

Queue
"""
with open('localize.sub', 'w') as f:
    f.write(contents%{'uid':streamdata['uid']})


## write lowmass_runner.dag
contents = """\
JOB LOCALIZE localize.sub

JOB SKYPOINTS skypoints.sub
SCRIPT PRE SKYPOINTS %(gracedbcommand)s log %(uid)s Sky localization started
SCRIPT POST SKYPOINTS %(gracedbcommand)s log %(uid)s Sky localization complete

JOB DQ1 dq.sub

JOB EMLABEL emlabel.sub
SCRIPT PRE EMLABEL %(gracedbcommand)s log %(uid)s EM_READY labeling started
SCRIPT POST EMLABEL %(gracedbcommand)s log %(uid)s EM_READY labeling complete

JOB COINCDET coincdet.sub
SCRIPT PRE COINCDET %(gracedbcommand)s log %(uid)s Coincidence search started
SCRIPT POST COINCDET %(gracedbcommand)s log %(uid)s Coincidence search complete

PARENT DQ1 CHILD EMLABEL
PARENT SKYPOINTS CHILD EMLABEL
PARENT SKYPOINTS CHILD COINCDET
"""
with open('lowmass_runner.dag', 'w') as f:
    f.write(contents % {'gracedbcommand': gracedbcommand, 'uid': streamdata['uid']})

# Create uniquely named log file.
logfid, logpath = tempfile.mkstemp(suffix='.nodes.log', prefix=streamdata['uid'])

# Set environment variable telling condor to use this log file
# for communication with nodes.
os.environ['_CONDOR_DAGMAN_DEFAULT_NODE_LOG'] = logpath

# submit dag
condorargs=['condor_submit_dag','lowmass_runner.dag']
os.execlp('condor_submit_dag', *condorargs)
