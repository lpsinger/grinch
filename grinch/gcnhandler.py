# PyGCN VOEvent Handler for LIGO
# John Swinbank, <swinbank@trtransientskp.org>, 2012.
# Matthew J. Graham, <mjg@caltech.edu>, 2012.
# Roy Williams, <roy.williams@ligo.org>, 2013.
# Alex Urban, <alexander.urban@ligo.org>, 2013.

# Imports.
import logging
import ConfigParser
import VOEventLib.VOEvent
import VOEventLib.Vutil

import os, json
from ligo.gracedb.rest import GraceDb
from grinch.workflow_helper import home


# Create instance of gracedb REST API.
gracedb = GraceDb()

# Create instance of the logging module, with the appropriate logger.
logger = logging.getLogger('grinch.gcnhandler.archive')

# Read gcn_config.ini.
cp = ConfigParser.ConfigParser()
etc = home + '/opt/etc/'
cp.read( etc + 'gcn_config.ini' )

# Set file path to event cache.
cache = cp.get('working', 'event_cache')


# Define event streams (only listening to Swift, Fermi, and SNEWS for now.
#streams = {'ivo://nasa.gsfc.gcn/AGILE': 'AGILE',
#           'ivo://nasa.gsfc.gcn/Fermi': 'Fermi',
#           'ivo://nasa.gsfc.gcn/INTEGRAL': 'INTEGRAL',
#           'ivo://nasa.gsfc.gcn/MAXI': 'MAXI',
#           'ivo://nasa.gsfc.gcn/SWIFT': 'SWIFT',
#           'ivo://voevent.phys.soton.ac.uk/voevent': '4PISKY',
#}
streams = { 'ivo://nasa.gsfc.gcn/Fermi': 'Fermi',
           'ivo://nasa.gsfc.gcn/SWIFT': 'SWIFT',
           'ivo://nasa.gsfc.gcn/SNEWS': 'SNEWS' }


# Function definitions.
def sendit(eventFile, group, pipeline, search="GRB"):
    """ Function for sending events to GraceDB. """
    r = gracedb.createEvent(group, pipeline, eventFile, search).json()
    graceid = r["graceid"]
    logger.info( "Event uploaded to GraceDB; Link is https://gracedb.ligo.org/events/%s " % graceid )
    return graceid

def replaceit(graceid, eventFile):
    """ Function for replacing event files with updated information in GraceDB. """
    gracedb.replaceEvent(graceid, eventFile)
    logger.info( "VOEvent file for %s has been updated; Link is https://gracedb.ligo.org/events/%s " % (graceid, graceid) )


Fermi_Likely = {
    0  :'An error has occurred',
    1  :'UNRELIABLE_LOCATION: Location not trusted',
    2  :'PARTICLES: Local particles, equal rates in opposite detectors',
    3  :'BELOW_HORIZON: Distant particles, assumed to come from the horizon',
    4  :'GRB: Burst with good localization',
    5  :'GENERIC_SGR: Soft Gamma Repeater (except 1806-20)',
    6  :'GENERIC_TRANSIENT: Astrophysical transient of unknown class',
    7  :'DISTANT_PARTICLES: Particles at a distance',
    8  :'SOLAR_FLARE: This is a Solar Flare event',
    9  :'CYG_X1: Thi: This trigger came from SGR 1806-20',
    11 :'GROJ_0422_32: This trigger came from GRO J0422-32',
    12 :'unrec_value: Unrecognized value',
    19 :'TGF: Terrestrial Gamma Flash',
}

         
def archive(payload, root=None, test=False):
    """
    Simple example of an event handler plugin. 
    Selects on stream and role, and saves the ones we're interested in
    (Swift, Fermi and SNEWS triggers that meet our criteria).
    """

    # Get VOEvent string.
    try:
        v = VOEventLib.Vutil.parseString( payload )
        logger.debug( "VOEvent string successfully parsed." )
    except:
        logger.error( "Problem parsing VOEvent string; possibly corrupted XML file." )
        return

    # Parse and save the IVORN.
    id = v.get_ivorn()
    tok = id.split('#')
    if len(tok) != 2:
        logger.error( "Illegal IVORN: %s" % id )
        return
    stream = tok[0]
    logger.info( "Ivorn: %s" % id )
    localid = tok[1]
    if not streams.has_key(stream):
        logger.error( "Stream %s not handled." % stream )
        return

    # Parse the role of this event.
    role = v.get_role()
    logger.debug( "Event role successfully parsed; role is %s" % role )

    # Ignore all alerts with role "utility."
    if role == 'utility':
        logger.info( "Utility events not used here; rejecting %s" % id )
        return

    # Let SNEWS test events through, but ignore all other tests.
    elif stream != 'ivo://nasa.gsfc.gcn/SNEWS' and role == 'test':
        logger.info( "Test events not used here; rejecting %s" % id )
        return

    # Is the role variable something weird?
    elif role != 'observation':
        logger.error( "Role %s not recognized; rejecting %s" % (role, id) )
        return

    # If it is a GCN, it will have a packet type.
    p = VOEventLib.Vutil.findParam(v, '', 'Packet_Type')
    if p:
        pt = int(VOEventLib.Vutil.paramValue(p))
        logger.info( "Packet type %s" % pt )
    else:
        logger.error( "No Packet_Type" )
        logger.debug( "This is a non-GCN event with no packet type; it will be ignored." )
        return     # WARNING we are ignoring all non-GCN events!

    keep = 0  # Save it in the cache: 0 for no save, 1 for save.
    send = 0  # Send it to Gracedb:   0 for no save, 1 for save.

    # SWIFT events: 
    # packet type == 61 means BAT alert       SEND to Gracedb
    # packet_type == 124 means GBM_Test_Pos
    if stream == 'ivo://nasa.gsfc.gcn/SWIFT':
        eventObservatory = 'Swift'
        if pt == 61: 
            keep = 1
            send = 1
            logger.info( 'Swift BAT_Pos' )
        else:
            logger.debug( 'Swift packet type %s not handled; ignoring unless it cites an IVORN we already have.' % pt )

    # Fermi events:
    # packet_type == 110 means GBM_Alert
    # packet_type == 111 means GBM_Flt_Pos
    # packet_type == 112 means GBM_Gnd_Pos    SEND to Gracedb
    # packet_type == 115 means GBM_Fin_Pos    SEND to Gracedb
    # packet_type == 124 means GBM_Test_Pos
    if stream == 'ivo://nasa.gsfc.gcn/Fermi':
        eventObservatory = 'Fermi'
        if pt == 110:
            keep = 1
            send = 0
            logger.info( 'Fermi GBM_Alert' )
        elif pt == 111:
            keep = 1
            send = 0
            logger.info( 'Fermi Flt_Pos' )
        elif pt == 112:
            keep = 1
            send = 1
            logger.info( 'Fermi GBM_Gnd_Pos' )
        elif pt == 115:
            keep = 1
            send = 1
            logger.info( 'Fermi GBM_Fin_Pos' )
        else:
            logger.debug( 'Fermi packet type %s not handled; ignoring unless it cites an IVORN we already have.' % pt )

    # Send all SNEWS events to Gracedb.
    if stream == 'ivo://nasa.gsfc.gcn/SNEWS':
        eventObservatory = 'SNEWS'
        keep = 1
        send = 1
        logger.info( 'SNEWS Alert (may be a test)' )

    # Create a unique label for this event's portfolio.
    pfname = id[6:].replace('/','_')
    pfdir = "%s/%s/%s" % (cache, role, pfname)
    logger.debug( "The name for this event's portfolio (derived from its IVORN) is: %s" % pfname )

    # Determine whether this is a portfolio we already have.
    cc = v.get_Citations()
    if cc and cc.get_EventIVORN():
        for c in cc.get_EventIVORN():
            citedivorn = c.get_valueOf_()
            logger.info( "Cites %s" % citedivorn )
            qfname = citedivorn[6:].replace('/','_')
            qfdir = "%s/%s/%s" % (cache, role, qfname)
            if os.path.exists(qfdir):
                logger.info( "Found portfolio %s" % qfdir )
                pfdir = qfdir
                keep = 1
                break
            else:
                logger.debug( "No existing event portfolio found; now assuming this event is new." )

    if keep == 0:
        logger.debug( "Ignoring event %s because is not flagged for saving on-disk." % pfname )
        return
    else:
        logger.debug( "Event %s is flagged for saving on-disk." % pfname )

    # Determine whether this event has a designation.
    # FIXME: What if it doesn't?
    hasDesignation = False
    if v.Why.Inference[0].get_Name() and send == 1:
        desig = v.Why.Inference[0].get_Name()[0]
        pfname = desig.replace(' ', '')
        hasDesignation = True
        logger.debug( "This event has designation %s; this will be reflected in the filename it is saved under." % desig )

    # Determine the filename for this event.
    filename = "%s/%s.xml" % (pfdir, pfname)
    logger.debug( "The name of the file to which this event will be saved on disk is: %s" % filename )

    # If this event has been flagged as one we want to keep, save it to disk.
    if not os.path.exists(pfdir): 
        logger.info( 'Making directory %s' % pfdir )
        if not test:
            os.mkdir(pfdir)
        else:
            logger.warning( "Because the test flag was passed, this directory was not actually made." )

    # Continue only if we have NOT already saved this file.
    if not os.path.isfile(filename):
        logger.info( "Saving to %s" % filename )
        if not test:
            try:
                with open(filename, 'w') as f:
                    f.write(payload)
            except:
                logger.critical( "VOEvent file %s failed to save on disk." % filename )
        else:
            logger.warning( "Because the test flag was passed, this event was not actually saved." )
    else:
        logger.info( "File %s has already been stored; ignoring this Notice." % filename )
        return

    # If it has also been flagged as one to send to GraceDB, send it to GraceDB.
    if send == 1:
        eventType = 'External'
        trigID = VOEventLib.Vutil.findParam(v, '', 'TrigID').get_value()
        event = list( gracedb.events('%s grbevent.trigger_id = "%s"' % (eventType, trigID)) )
        if event:
            gid = event[0]['graceid']
            if not test:
                try:
                    replaceit(gid, filename)
                except:
                    logger.critical( "GraceDB event %s was not updated because the event was not saved!" % gid )
            else:
                logger.warning( "Because the test flag was passed, GraceDB event %s was not updated." % gid )
        else: 
            if not test:
                try:
                    gid = sendit(filename, eventType, eventObservatory)
                    # FIXME: SNEWS events will ultimately need a Search label other than the default ("GRB").
                    gracedb.writeLog(gid, 'This event detected by %s' % v.How.get_Description()[0], tagname='analyst_comments')
                except:
                    logger.critical( "This event failed to save, and therefore could not be uploaded to GraceDB!" )
            else:
                logger.warning( "Because the test flag was passed, this new event was not uploaded to GraceDB." )

        if hasDesignation and not test: gracedb.writeLog(gid, 'This event has been designated %s' % desig, tagname='analyst_comments')

    return
