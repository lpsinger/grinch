#!/usr/bin/python

import tempfile
import time
import os
import sys
from subprocess import Popen, PIPE, STDOUT, call
import optparse
import ConfigParser
import urlparse

from glue.ligolw import ligolw
from glue.ligolw import utils as ligolwutils
from glue.ligolw import table as ligolwtable
from glue.ligolw import lsctables
from ligo.lvalert import utils as lvalertutils

inj_segments=["DMT-INJECTION_BURST","DMT-INJECTION_INSPIRAL","INJECTION_BURST","INJECTION_INSPIRAL", "INJECTION_BURST_BLIND", "INJECTION_STOCHASTIC"]

science_segments={"H1":"DMT-SCIENCE","L1":"DMT-SCIENCE","V1":"ITF_SCIENCEMODE"}

#################################################################
# help message
usage = """\
%prog [options]
------------------------------------------------------------------------------
  Turn DQ information into labels for GraceDB events
"""
parser = optparse.OptionParser( usage=usage )
#input file
parser.add_option("-i","--graceid",action="store",type="string",default=None,\
      help="gracedb unique id" )
parser.add_option("-f","--file",action="store",type="string",default=None,\
      help="name of the file with DQ information" )
parser.add_option("-v","--veto-definer-file",action="store",type="string",default=None,\
      help="name of the file with definitions of DQ veto flags" )
parser.add_option("-g","--gracedb-command",action="store",type="string",default="gracedb",\
      help="where to find the gracedb command" )
parser.add_option("-e", "--set-em-ready",action="store_true", default=False,\
      help="set EM_READY label and send lv alert")
parser.add_option("-I","--ifos",action="store",type="string",default=None,\
      help="a comma separated list of the interferometers to check for science mode (default is none)" )

(options,args) = parser.parse_args()

if not options.graceid or not options.file:
  print "Error: You must supply a graceid and a file"
  sys.exit(1)

# read veto definer file
veto_doc = ligolwutils.load_filename(options.veto_definer_file)
vetodeftable = ligolwtable.get_table(veto_doc,lsctables.VetoDefTable.tableName)

# get up to category 2 veto flags   
max_category = 2

veto_defs = []
for row in vetodeftable:
  if row.category <= max_category:
    veto_defs.append(row.name)

# filter out injection flags, keep only bad data DQ flags
bad_dq_veto_defs = []
for veto_def in veto_defs:
  if not veto_def in inj_segments:
    bad_dq_veto_defs.append(veto_def) 

# read file with flags that are active at gps time of the event 
doc = ligolwutils.load_filename(options.file)
segdeftable = ligolwtable.get_table(doc,lsctables.SegmentDefTable.tableName)
segment_names = segdeftable.getColumnByName('name')

labels=[]
for name in inj_segments:
  if name in segment_names:
    labels.append("INJ")
    break
for name in bad_dq_veto_defs:
  if name in segment_names:
    labels.append("DQV")
    print "Bad DQ Flag is %s" % name
    break

# check for science mode, but not if the trigger already has a DQV flag
if options.ifos and not "DQV" in labels:
  ifos=options.ifos.split(",")
  for ifo in ifos:
    if not science_segments[ifo] in segment_names:
      labels.append("DQV")
      print "%s is not in science mode" % ifo
      break

# RUSLAN: add code here to check that sky map exists if the option is set 
# if skymap exists:
#   if not labels:
#     labels.append("EM_READY") 
# 
if options.set_em_ready:
  # check if skymap.txt exist
#  if os.path.isfile("skymap.txt"):
  if os.path.isfile("skymap_no_galaxies.txt"):
    # onliny label as EM_READY if neither vetoed nor hardware injection
    # XXX this is changed for testing: be sure to change back XXX
    if not "DQV" in labels:
      labels.append("EM_READY")
    #if not labels:
     # labels.append("EM_READY")

exitcode=0
for label in labels:
  print "Labelling the event with %s" % label
  # RUSLAN:  you need to add the --alert option if we are labeling with EM_READY I think. 
  # This gracedbargs is an array, so it would be the second element in the array. 
  if label == "EM_READY":
    gracedbargs=[options.gracedb_command,"--alert","label",options.graceid,label]
  else:
    gracedbargs=[options.gracedb_command,"label",options.graceid,label]
  print gracedbargs
  ret=call( gracedbargs )
  if ret:
    exitcode = ret

if not options.set_em_ready:
  gracedbargs=[options.gracedb_command,"upload",options.graceid,options.file,"Data quality check completed"]
  ret=call( gracedbargs )
  if ret:
    exitcode = ret

sys.exit(exitcode)
