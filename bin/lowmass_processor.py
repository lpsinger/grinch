#! /usr/bin/python

import os
import os.path
import tempfile
import urlparse
import re
import ConfigParser

from sys            import exit, stdin

from subprocess	    import call

from glue.ligolw    import ligolw
from glue.ligolw    import utils
from glue.ligolw    import table
from glue.ligolw    import lsctables
from ligo.lvalert.utils import get_LVAdata_from_stdin

## create dict from gracedb table
streamdata = get_LVAdata_from_stdin(stdin, as_dict=True)

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

## read lowmass_config.ini
cp = ConfigParser.ConfigParser()
cp.read('lowmass_config.ini')

private_gracedir   = os.path.split(urlparse.urlparse(streamdata['file'])[2])[0]
general_gracedir   = private_gracedir.replace('private','general')
processor_gracedir = '/home/gdb_processor/working/ER3/%s'%streamdata['uid'] # "".join([general_gracedir,'/gdb_processor/'])

gracedbcommand     = cp.get('executable','gracedbcommand')
dqwaitscript       = cp.get('executable','dqwaitscript')
dqtolabelscript    = cp.get('executable','dqtolabelscript')
skypointscript     = cp.get('executable','skypointscript')
coincdetscript     = cp.get('executable','coincdetscript')

vetodefinerfile    = cp.get('veto','vetodefinerfile')
ranksfile          = cp.get('skypoints','ranksfile')
gridsfile          = cp.get('skypoints','gridsfile')
coincdetconfig     = cp.get('coincdet','configfile')

## gdb_processor directory on gracedb
try:
     os.makedirs(processor_gracedir)
except OSError:
     print 'Could not make directory %s'%processor_gracedir
     pass

## extract information about the event
if re.search('.xml',streamdata['file']):
     coincfile = urlparse.urlparse(streamdata['file'])[2]
else: # download coinc file from gracedb web client; stick it in processor_gracedir
     call('gracedb download' + ' %s'%streamdata['uid'] + ' coinc.xml', shell=True)
     call('mv' + ' coinc.xml' + ' %s'%processor_gracedir, shell=True)
     coincfile = "".join([private_gracedir,'/coinc.xml'])
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

os.chdir(processor_gracedir)

## write skypoints.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = --glob=%(coincfile)s --ranks=%(ranksfile)s --grids=%(gridsfile)s
getenv              = True
notification        = never

log                 = %(tmplog)s
output              = skypoints.out
error               = skypoints.error

+LVAlertListen      = %(uid)s_skypoints
Queue
"""
tmplog  = tempfile.mkstemp()[1]
subFile = open('skypoints.sub','w')
subFile.write(contents%{'script':skypointscript,'coincfile':coincfile,'ranksfile':ranksfile,'gridsfile':gridsfile,'tmplog':tmplog,'uid':streamdata['uid']})
subFile.close()

## write data quality.sub
contents   = """\
universe            = local

executable          = /bin/cp
arguments           = /home/gdb_processor/dq-fake.xml dq.xml
getenv              = True
notification        = never

log                 = %(tmplog)s
output              = dq.out
error               = dq.error

+LVAlertListen      = %(uid)s_dq
Queue
"""
tmplog  = tempfile.mkstemp()[1]
subFile = open('dq.sub','w')
subFile.write(contents%{'tmplog':tmplog,'uid':streamdata['uid']})
subFile.close()

## write emlabel.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = --set-em-ready -f dq.xml -i %(uid)s -g %(gdbcommand)s --veto-definer-file %(vetodefinerfile)s
getenv              = True
notification        = never

log                 = %(tmplog)s
error               = emlabel.err
output              = emlabel.out

+LVAlertListen      = %(uid)s_emlabel
Queue
"""
tmplog  = tempfile.mkstemp()[1]
subFile = open('emlabel.sub','w')
subFile.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'tmplog':tmplog,'uid':streamdata['uid']})
subFile.close()

## write coincdet.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = test_lowmass %(uid)s %(coincfile)s %(configfile)s
getenv              = True
notification        = never

log                 = %(tmplog)s
error               = coincdet.err
output              = coincdet.out

+LVAlertListen      = %(uid)s_coincdet

Queue
"""
tmplog  = tempfile.mkstemp()[1]
subFile = open('coincdet.sub','w')
subFile.write(contents%{'script':coincdetscript,'coincfile':coincfile,'configfile':coincdetconfig,'tmplog':tmplog,'uid':streamdata['uid']})
subFile.close()

## write lowmass_runner.dag
contents = """\
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
f = open('lowmass_runner.dag','w')
f.write(contents % {'gracedbcommand': gracedbcommand, 'uid': streamdata['uid']})
f.close()

# submit dag
condorargs=['condor_submit_dag','lowmass_runner.dag']
os.execlp('condor_submit_dag', *condorargs)
