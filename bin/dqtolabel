#!/usr/bin/python
"""Label gracedb events with data quality information"""

import sys
import optparse
import ConfigParser
import urlparse

from glue.segmentdb.query_engine import LdbdQueryEngine
from glue.segmentdb import segmentdb_utils

from glue.segments import segmentlistdict

from glue.ligolw import utils as ligolwutils
from glue.ligolw import table as ligolwtable
from glue.ligolw import ligolw
from glue.ligolw import lsctables
from glue.ligolw.utils import process
from ligo.gracedb.rest import GraceDb

# initialize instance of gracedb interface
gracedb = GraceDb()

#
# Utility functions
#

def query_segments_db(db_location, gps_start, gps_end, spec):
  """
  Query db_location to get segments between (gps_start, gps_end), with definer spec.
  """
  engine = LdbdQueryEngine( segmentdb_utils.setup_database(db_location) )
  definer_args = []
  for vdef in spec:
    ifo, definer, version = vdef.split(":")
    # FIXME: padding
    definer_args.append([ifo, definer, int(version), gps_start, gps_end, 0, 0])
  result = segmentdb_utils.query_segments(engine, "segment", definer_args)
  return segmentlistdict(zip(spec, result))

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
parser.add_option("-i","--graceid",action="store",type="string",default=None, help="gracedb unique id" )
#parser.add_option("-f","--segment-definer-file",action="store",type="string",default=None, help="name of the file with segment definer DQ information" )
parser.add_option("-u","--segment-db-url", action="store", help="Segment database to query for segment information.")
parser.add_option("-V","--veto-definer-file",action="store",type="string",default=None, help="name of the file with definitions of DQ veto flags" )
parser.add_option("-m", "--max-category", action="store", type=int, default=2, help="Maximum category to consider as a veto. Default is 2.")
parser.add_option("-v", "--verbose", action="store_true", help="Be verbose.")

(options,args) = parser.parse_args()

#
# Options checking
#
if not options.graceid:
  print "Error: You must supply a graceid and a segment definer file"
  sys.exit(1)

if not options.segment_db_url:
  sys.exit("Error: You must provide a URL to query against.")

verbose = options.verbose
#
# get up to category N veto flags
#
max_category = options.max_category

result = list(gracedb.events(options.graceid))[0]
gps_time = result['gpstime']
# FIXME: This
padding = 10
gps_start = gps_time - padding
gps_end = gps_time + padding

#
# Instruments
#

instruments = result['instruments'].split(",")
if verbose:
  print "Event instruments: %s" % ", ".join(instruments)

#
# read veto definer file
#
veto_doc = ligolwutils.load_filename(options.veto_definer_file)
vetodeftable = ligolwtable.get_table(veto_doc,lsctables.VetoDefTable.tableName)

#
# filter out injection flags, keep only bad data DQ flags
#
bad_dq_veto_defs = []
for veto_def in vetodeftable:
  if veto_def.category > max_category or veto_def.ifo not in instruments:
    continue
  if not veto_def.name in inj_segments:
    bad_dq_veto_defs.append(veto_def.ifo + ":" + veto_def.name + ":" + str(veto_def.version))

# TODO: Read from segment XML, that's what I think this is for
"""
# read file with flags that are active at gps time of the event 
doc = ligolwutils.load_filename(options.file)
segdeftable = ligolwtable.get_table(doc,lsctables.SegmentDefTable.tableName)
segment_names = segdeftable.getColumnByName('name')
"""
veto_times = query_segments_db(options.segment_db_url, gps_start, gps_end, bad_dq_veto_defs)

# TODO: Make more types of labels
labels = []
for name, segl in veto_times.iteritems():
  if len(segl) > 0:
     if verbose:
       print "Bad DQ Flag %s" % name
     if "DQV" not in labels:
        labels.append("DQV")

# FIXME: What to do about this?
"""
for name in inj_segments:
  if name in segment_names:
    labels.append("INJ")
    break

# check for science mode, but not if the trigger already has a DQV flag
if options.ifos and not "DQV" in labels:
  ifos=options.ifos.split(",")
  for ifo in ifos:
    if not science_segments[ifo] in segment_names:
      labels.append("DQV")
      print "%s is not in science mode" % ifo
      break
"""

exitcode=0
for label in labels:
  print "Labelling the event with %s" % label
  try: gracedb.writeLabel(options.graceid, label)
  except: exitcode = 1 

#
# Build output document
#

xmldoc = ligolw.Document()
xmldoc.appendChild(ligolw.LIGO_LW())
proc = process.register_to_xmldoc(xmldoc, sys.argv[0], options.__dict__)
for name, segl in veto_times.iteritems():
	ifo, defname, version = segmentdb_utils.split_segment_ids([name])[0]
	seg_def_id = segmentdb_utils.add_to_segment_definer(xmldoc, proc.process_id, ifo, defname, version)
	segmentdb_utils.add_to_segment(xmldoc, proc.process_id, seg_def_id, segl)

# FIXME: Should go in work directory
tmpfname = "/tmp/%s-DATA_QUALITY-%d-%d.xml.gz" % ("".join(instruments), gps_start, gps_end-gps_start)
ligolwutils.write_filename(xmldoc, tmpfname, gz=True, verbose=verbose)

try: gracedb.writeLog(options.graceid, message="Data quality check completed", filename=tmpfname, tagname="data_quality")
except: exitcode = 1

sys.exit(exitcode)
