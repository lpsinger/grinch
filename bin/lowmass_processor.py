#! /usr/bin/python

import os.path
import tempfile
import urlparse
import logging
import re
import ConfigParser

from subprocess     import Popen
from sys            import argv, exit, stdin

from glue.ligolw    import ligolw
from glue.ligolw    import utils as ligolwutils
from glue.ligolw    import table as ligolwtable
from glue.ligolw    import lsctables

## lowmass_processor logger
logfile = 'logs/lowmass_processor.log'
logger    = logging.getLogger('lowmass_processor')
hdlr      = logging.FileHandler(logfile)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
hdlr.setFormatter(formatter)
logger.addHandler(hdlr)
logger.setLevel(logging.DEBUG)
logger.info('\nStarting lowmass_processor')

## ligolw document
doc      = ligolw.Document()
handler  = ligolw.LIGOLWContentHandler(doc)
ligolw.make_parser(handler).parse(stdin)
lvatable = ligolwtable.get_table(doc,'LVAlert:table')

## bayestar initializations
subdir   = '/home/gdb_processor/leo/lib/python2.6/site-packages/bayestar/lvalert'
sitekeys = ['PTF','Pi of the Sky North','Pi of the Sky South','QUEST','ROTSE III-a','ROTSE III-b','ROTSE III-c','ROTSE III-d','Skymapper','TAROT','TAROT-S','Zadko']
dag = r"""
JOB log_started   %(subdir)s/gracedb_log.sub
JOB skymap2pickle %(subdir)s/skymap2pickle.sub
JOB plan_pointing %(subdir)s/plan_pointing.sub
JOB plot_pointing %(subdir)s/plot_pointing.sub
JOB make_web_page %(subdir)s/make_web_page.sub
JOB log_ready     %(subdir)s/gracedb_log.sub
JOB log_done      %(subdir)s/gracedb_log.sub

VARS log_started GRACEID="%(uid)s" LOGMSG="BAYESTAR: planning observations"
VARS log_ready   GRACEID="%(uid)s" LOGMSG="BAYESTAR: observation planning complete, rendering skymaps"
VARS log_done GRACEID="%(uid)s" LOGMSG="BAYESTAR: skymaps rendered: https://ldas-jobs.phys.uwm.edu/gracedb/data/%(uid)s/general/bayestar"

PARENT log_started CHILD skymap2pickle
PARENT skymap2pickle CHILD plan_pointing plot_pointing make_web_page
PARENT plan_pointing CHILD log_ready plot_pointing make_web_page
PARENT plot_pointing make_web_page CHILD log_done
"""

## if labeled EM_READY
if lvatable[0].alert_type == 'label' and lvatable[0].description == 'EM_READY':
    logger.info('Beginning EM_READY sequence')
#    sys.path.append('/home/gdb_processor/er1/gdb_processor/lib/python2.6/site-packages')
#    sys.path.append('/home/gdb_processor/er1/gdb_processor/bin')
    import bayestar.lvalert
    bayestar.lvalert.respond(lvatable[0].uid,submit=True)
    ## function ends processor

## check if new
elif lvatable[0].alert_type == 'new':
    logger.info('Beginning new event sequence')

## else
else:
     logger.info('Aborting lowmass_process, alert type %s not new or labeling EM_READY'%lvatable[0].alert_type)
     exit()

## read lowmass_config.ini
cp = ConfigParser.ConfigParser()
cp.read('lowmass_config.ini')

homedir            = os.getcwd()
private_gracedir   = os.path.split(urlparse.urlparse(lvatable[0].file)[2])[0]
general_gracedir   = private_gracedir.replace('private','general')
processor_gracedir = "".join([general_gracedir,'/gdb_processor/'])

gracedbcommand     = cp.get('executable','gracedbcommand')
dqwaitscript       = cp.get('executable','dqwaitscript')
dqtolabelscript    = cp.get('executable','dqtolabelscript')
skypointscript     = cp.get('executable','skypointscript')
coincdetscript     = cp.get('executable','coincdetscript')

vetodefinerfile    = cp.get('veto','vetodefinerfile')
ranksfile          = cp.get('skypoints','ranksfile')
gridsfile          = cp.get('skypoints','gridsfile')

## extract information about the event
if re.search('.xml',lvatable[0].file):
     coincfile = urlparse.urlparse(lvatable[0].file)[2]
     logger.info('The coincidence file...%s'%coincfile)
else:
     coincfile = "".join([private_gracedir,'/coinc.xml'])
doc        = ligolwutils.load_filename(coincfile)
coinctable = ligolwtable.get_table(doc,lsctables.CoincInspiralTable.tableName)
gpstime    = coinctable[0].end_time
ifonames   = ['H1','L1','V1']
if 'test' in cp.sections():
     ifos = cp.get('test','ifos')
else:
     ifos = coinctable[0].ifos
disable_ifos = [ifo for ifo in ifonames if ifo not in ifos]
itime        = str(int(float(gpstime)+0.5))

## gdb_processor directory on gracedb
try:
     os.makedirs(processor_gracedir)
except OSError:
     print 'Could not make directory %s'%processor_gracedir
     pass
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
subFile.write(contents%{'script':skypointscript,'coincfile':coincfile,'ranksfile':ranksfile,'gridsfile':gridsfile,'tmplog':tmplog,'uid':lvatable[0].uid})
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
subFile.write(contents%{'tmplog':tmplog,'uid':lvatable[0].uid})
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
subFile.write(contents%{'script':dqtolabelscript,'gdbcommand':gracedbcommand,'vetodefinerfile':vetodefinerfile,'tmplog':tmplog,'uid':lvatable[0].uid})
subFile.close()

## write coincdet.sub
contents   = """\
universe            = local

executable          = %(script)s
arguments           = test_lowmass %(uid)s %(coincfile)s
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
subFile.write(contents%{'script':coincdetscript,'coincfile':coincfile,'tmplog':tmplog,'uid':lvatable[0].uid})
subFile.close()

## write lowmass_runner.dag
dagfile = "".join([processor_gracedir,'/lowmass_runner.dag'])
f = open(dagfile,'w')
f.write('JOB SKYPOINTS skypoints.sub\n')
f.write(('SCRIPT PRE SKYPOINTS %s log %s Sky localization started\n' % (gracedbcommand, lvatable[0].uid)))
f.write(('SCRIPT POST SKYPOINTS %s log %s Sky localization complete\n' % (gracedbcommand, lvatable[0].uid)))

f.write('JOB DQ1 dq.sub\n')
#f.write(('SCRIPT PRE DQ1 %s --gps-time %s --ifos %s\n' % (dqwaitscript,itime,ifos)))
#f.write(('SCRIPT POST DQ1 %s -f %s -i %s -g %s --veto-definer-file %s --ifos %s\n' % (dqtolabelscript,'dq.xml',lvatable[0].uid,gracedbcommand,vetodefinerfile,ifos)))

f.write('JOB EMLABEL emlabel.sub\n')
f.write(('SCRIPT PRE EMLABEL %s log %s EM_READY labeling started  \n' % (gracedbcommand, lvatable[0].uid)))
f.write(('SCRIPT POST EMLABEL %s log %s EM_READY labeling complete\n' % (gracedbcommand, lvatable[0].uid)))

f.write('JOB COINCDET coincdet.sub\n')
f.write(('SCRIPT PRE COINCDET %s log %s Coincidence search started \n' % (gracedbcommand, lvatable[0].uid)))
f.write(('SCRIPT POST COINCDET %s log %s Coincidence search complete \n' % (gracedbcommand, lvatable[0].uid)))

f.write('PARENT DQ1 CHILD EMLABEL\n')
f.write('PARENT SKYPOINTS CHILD EMLABEL\n')
f.write('PARENT SKYPOINTS CHILD COINCDET\n')
f.close()

## submit dag
logger.info('Submitting DAG')
os.chdir(processor_gracedir)
condorargs=['condor_submit_dag','lowmass_runner.dag']
myenv={'PATH':'/usr/local/bin:/usr/bin:/bin:/home/gdb_processor/er1/gdb_processor',\
'PYTHONPATH':'/home/cbiwer/lib/python:/home/gdb_processor/er1/gdb_processor/lib/python2.6/site-packages',\
'LOGNAME':'gdb_processor',\
'X509_USER_CERT':'/home/gdb_processor/.globus/gdb-processor_marlin.phys.uwm.edu.cert.pem',\
'X509_USER_KEY':'/home/gdb_processor/.globus/gdb-processor_marlin.phys.uwm.edu.key.pem'}
Popen(condorargs,env=myenv)
logger.info('Completed new event sequence\n')
