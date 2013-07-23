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
#dqtolabelscript    = cp.get('executable','dqtolabelscript')
#coincdetscript     = cp.get('executable','coincdetscript')
#gracedbcommand     = cp.get('executable','gracedbcommand')
coinc_search       = cp.get('executable','coincscript')

#vetodefinerfile    = cp.get('veto','vetodefinerfile')


# build and move to a unique working directory
working = directory(streamdata['uid'])
working.build_and_move()


## if labeled EM_READY
#if streamdata['alert_type'] == 'label' and streamdata['description'] == 'EM_READY':
#    import bayestar.lvalert
#    bayestar.lvalert.respond(streamdata['uid'],submit=True)
    ## function ends processor

## check if new
elif  streamdata['alert_type'] == 'new':
    pass

## elsewise, end the processor
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


##############################
## PRODUCE CONDOR SUB FILES ##
##############################

# write coinc_search.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = " --graceid=%(uid)s --direction=backward "
getenv              = True
notification        = never

output              = coinc_search_%(uid)s.out
error               = coinc_search_%(uid)s.error

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True

+LVAlertListen      = %(uid)s_coinc_search

Queue
"""
with open('coinc_search.sub', 'w') as f:
    f.write(contents%{'script':coinc_search,'uid':streamdata['uid']})

## write data quality.sub
#contents   = """\
#universe            = local
#
#executable          = /bin/cp
#arguments           = /home/gdb_processor/dq-fake.xml dq.xml
#getenv              = True
#notification        = never
#
#output              = dq_%(uid)s.out
#error               = dq_%(uid)s.error
#
#+Online_CBC_EM_FOLLOWUP = True
#Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True
#
#+LVAlertListen      = %(uid)s_dq
#Queue
#"""
#with open('dq.sub', 'w') as f:
#    f.write(contents%{'uid':streamdata['uid']})
#
#    f.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'uid':streamdata['uid']})

## write emlabel.sub
#contents   = """\
#universe            = local
#
#executable          = %(script)s
#arguments           = " --set-em-ready -f dq.xml -i %(uid)s -g %(gdbcommand)s --veto-definer-file %(vetodefinerfile)s "
#getenv              = True
#notification        = never
#
#+Online_CBC_EM_FOLLOWUP = True
#Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True
#
#error               = emlabel_%(uid)s.err
#output              = emlabel_%(uid)s.out
#
#+LVAlertListen      = %(uid)s_emlabel
#Queue
#"""
#with open('emlabel.sub','w') as f:
#    f.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'uid':streamdata['uid']})

## write localize.sub
contents   = """\
universe            = local

executable          = /usr/bin/env
arguments           = bayestar_localize_lvalert %(uid)s
getenv              = True
notification        = never

error               = localize_%(uid)s.err
output              = localize_%(uid)s.out

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True

+LVAlertListen      = %(uid)s_localize

Queue
"""
with open('localize.sub', 'w') as f:
    f.write(contents%{'uid':streamdata['uid']})

## write plot_allsky.sub
contents   = """\
universe            = local

executable          = /usr/bin/env
arguments           = bayestar_plot_allsky -o skymap.png --contour=50 --contour=90 skymap.fits \
&& /usr/bin/gracedb upload %(uid)s skymap.png
getenv              = True
notification        = never

error               = allsky_%(uid)s.err
output              = allsky_%(uid)s.out

+Online_CBC_EM_FOLLOWUP = True
Requirements        = TARGET.Online_CBC_EM_FOLLOWUP =?= True

+LVAlertListen      = %(uid)s_plot_allsky

Queue
"""
with open('plot_allsky.sub', 'w') as f:
    f.write(contents%{'uid':streamdata['uid']})


#################################
## WRITE CONDOR DAG AND SUBMIT ##
#################################

## write lowmass_runner.dag
contents = """\
JOB LOCALIZE localize.sub

JOB PLOTALLSKY plot_allsky.sub

JOB COINCSEARCH coinc_search.sub

PARENT LOCALIZE CHILD PLOTALLSKY
PARENT LOCALIZE CHILD COINCSEARCH
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
