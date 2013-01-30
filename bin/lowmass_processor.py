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

homedir            = os.getcwd()
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
dagfile = "".join([processor_gracedir,'/lowmass_runner.dag'])
f = open(dagfile,'w')
f.write('JOB SKYPOINTS skypoints.sub\n')
f.write(('SCRIPT PRE SKYPOINTS %s log %s Sky localization started\n' % (gracedbcommand, streamdata['uid'])))
f.write(('SCRIPT POST SKYPOINTS %s log %s Sky localization complete\n' % (gracedbcommand, streamdata['uid'])))

f.write('JOB DQ1 dq.sub\n')
#f.write(('SCRIPT PRE DQ1 %s --gps-time %s --ifos %s\n' % (dqwaitscript,itime,ifos)))
#f.write(('SCRIPT POST DQ1 %s -f %s -i %s -g %s --veto-definer-file %s --ifos %s\n' % (dqtolabelscript,'dq.xml',lvatable[0].uid,gracedbcommand,vetodefinerfile,ifos)))

f.write('JOB EMLABEL emlabel.sub\n')
f.write(('SCRIPT PRE EMLABEL %s log %s EM_READY labeling started  \n' % (gracedbcommand, streamdata['uid'])))
f.write(('SCRIPT POST EMLABEL %s log %s EM_READY labeling complete\n' % (gracedbcommand, streamdata['uid'])))

f.write('JOB COINCDET coincdet.sub\n')
f.write(('SCRIPT PRE COINCDET %s log %s Coincidence search started \n' % (gracedbcommand, streamdata['uid'])))
f.write(('SCRIPT POST COINCDET %s log %s Coincidence search complete \n' % (gracedbcommand, streamdata['uid'])))

f.write('PARENT DQ1 CHILD EMLABEL\n')
f.write('PARENT SKYPOINTS CHILD EMLABEL\n')
f.write('PARENT SKYPOINTS CHILD COINCDET\n')
f.close()

# submit dag
os.chdir(processor_gracedir)
condorargs=['condor_submit_dag','lowmass_runner.dag']
os.execlp('condor_submit_dag', *condorargs)
