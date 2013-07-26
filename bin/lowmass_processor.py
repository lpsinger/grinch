#! /usr/bin/python

import os
import os.path
import tempfile
import urlparse
import re
import ConfigParser
import shutil

from sys             import exit, stdin

from workflow_helper import directory, home
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
etc = home + '/opt/etc/'
cp.read(etc+'lowmass_config.ini')

#dqwaitscript       = cp.get('executable','dqwaitscript')
dqtolabelscript    = cp.get('executable','dqtolabelscript')
#coincdetscript     = cp.get('executable','coincdetscript')
gracedbcommand     = cp.get('executable','gracedbcommand')
coinc_search       = cp.get('executable','coincscript')

vetodefinerfile    = cp.get('veto','vetodefinerfile')


# build and move to a unique working directory
working = directory(streamdata['uid'])
working.build_and_move()


## if labeled EM_READY
#if streamdata['alert_type'] == 'label' and streamdata['description'] == 'EM_READY':
#    import bayestar.lvalert
#    bayestar.lvalert.respond(streamdata['uid'],submit=True)
    ## function ends processor

## check if new
if streamdata['alert_type'] == 'new':
    pass

## elsewise, end the processor
else:
     exit()

## extract information about the event
## FIXME: streamdata['file'] is not used at all to determine what the coincfile is.
##        This is because an implicit assumption is that this file will always be
##        called 'coinc.xml,' as a prerequisite for a graceid even being generated
##        in the first place. This is a potential issue that needs to be addressed
##        in the future.
coincfile = 'coinc.xml'
gracedb_client = ligo.gracedb.rest.GraceDb()
remote_file = gracedb_client.files(streamdata['uid'], coincfile)
with open(coincfile, 'w') as local_file:
    shutil.copyfileobj(remote_file, local_file)
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


##############################
## PRODUCE CONDOR SUB FILES ##
##############################

# write coinc_search.sub
contents   = """\
universe            = vanilla

executable          = %(script)s
arguments           = " --graceid=%(uid)s --direction=backward "
getenv              = True
notification        = never

output              = coinc_search_%(uid)s.out
error               = coinc_search_%(uid)s.error
log                 = coinc_search_%(uid)s.log

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True
+LVAlertListen      = %(uid)s_coinc_search

Queue
"""
with open('coinc_search.sub', 'w') as f:
    f.write(contents%{'script':coinc_search,'uid':streamdata['uid']})

## write data quality.sub
#contents   = """\
#universe            = vanilla
#
#executable          = /bin/cp
#arguments           = /home/gdb_processor/dq-fake.xml dq.xml
#getenv              = True
#notification        = never
#
#output              = dq_%(uid)s.out
#error               = dq_%(uid)s.error
#log                 = dq_%(uid)s.log
#
#+LVAlertListen      = %(uid)s_dq
#Queue
#"""
#with open('dq.sub', 'w') as f:
#    f.write(contents%{'uid':streamdata['uid']})
#
#    f.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'uid':streamdata['uid']})

## write emlabel.sub
contents   = """\
universe            = vanilla

executable          = %(script)s
arguments           = " --set-em-ready -f /home/gdb_processor/dq-fake.xml -i %(uid)s -g %(gdbcommand)s --veto-definer-file %(vetodefinerfile)s "
getenv              = True
notification        = never

error               = emlabel_%(uid)s.err
output              = emlabel_%(uid)s.out
log                 = emlabel_%(uid)s.log

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True
+LVAlertListen      = %(uid)s_emlabel
Queue
"""
with open('emlabel.sub','w') as f:
    f.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'uid':streamdata['uid']})

## write localize.sub
contents   = """\
universe            = vanilla

executable          = /usr/bin/env
arguments           = bayestar_localize_lvalert %(uid)s
getenv              = True
notification        = never

error               = localize_%(uid)s.err
output              = localize_%(uid)s.out
log                 = localize_%(uid)s.log

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True
+LVAlertListen      = %(uid)s_localize

Queue
"""
with open('localize.sub', 'w') as f:
    f.write(contents%{'uid':streamdata['uid']})

## write plot_allsky.sub
contents   = """\
universe            = vanilla

executable          = /usr/bin/env
arguments           = bayestar_plot_allsky -o %(output)s --contour=50 --contour=90 %(fits)s
getenv              = True
notification        = never

error               = allsky_%(uid)s.err
output              = allsky_%(uid)s.out
log                 = allsky_%(uid)s.log

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True
+LVAlertListen      = %(uid)s_plot_allsky

Queue
"""
with open('plot_allsky.sub', 'w') as f:
    f.write(contents%{'output':'skymap.png','fits':'skymap.fits.gz','uid':streamdata['uid']})


#################################
## WRITE CONDOR DAG AND SUBMIT ##
#################################

## write lowmass_runner.dag
contents = """\
JOB LOCALIZE localize.sub

JOB EMLABEL emlabel.sub

JOB PLOTALLSKY plot_allsky.sub
SCRIPT POST PLOTALLSKY %(gracedbcommand)s upload %(uid)s %(skymap)s

JOB COINCSEARCH coinc_search.sub

PARENT LOCALIZE CHILD EMLABEL 
PARENT EMLABEL CHILD PLOTALLSKY COINCSEARCH
"""
with open('lowmass_runner.dag', 'w') as f:
    f.write(contents % {'gracedbcommand': gracedbcommand,'skymap':'skymap.png','uid': streamdata['uid']})

# Create uniquely named log file.
logfid, logpath = tempfile.mkstemp(suffix='.nodes.log', prefix=streamdata['uid'])

# Set environment variable telling condor to use this log file
# for communication with nodes.
os.environ['_CONDOR_DAGMAN_DEFAULT_NODE_LOG'] = logpath

# submit dag
condorargs=['condor_submit_dag','lowmass_runner.dag']
os.execlp('condor_submit_dag', *condorargs)
