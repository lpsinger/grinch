# PyGCN VOEvent Handler for LIGO
# John Swinbank, <swinbank@trtransientskp.org>, 2012.
# Matthew J. Graham, <mjg@caltech.edu>, 2012.
# Roy Williams, <roy.williams@ligo.org>, 2013.
# Alex Urban, <alexander.urban@ligo.org>, 2013.

# Imports.
import logging

import VOEventLib.VOEvent
import VOEventLib.Vutil

import os, json
from ligo.gracedb.rest import GraceDb


# Create instance of gracedb REST API.
gracedb = GraceDb()

# Create instance of the logging module, with the appropriate logger.
logger = logging.getLogger('grinch.gcnhandler.archive')


def sendit(eventFile, group, pipeline, search="GRB"):
    """ Function for sending events to GraceDB. """
    r = gracedb.createEvent(group, pipeline, eventFile, search).json()
    graceid = r["graceid"]
    logger.info( "Link is https://gracedb.ligo.org/events/%s " % graceid )
    return graceid

def replaceit(graceid, eventFile):
    """ Function for replacing event files with updated information in GraceDB. """
    gracedb.replaceEvent(graceid, eventFile)
    logger.info( "VOEvent file for %s has been updated; Link is https://gracedb.ligo.org/events/%s " % (graceid, graceid) )


CACHE = "/home/gdb_processor/working/gcn_listener/cache"

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
    v = VOEventLib.Vutil.parseString( payload )
    logger.debug( "VOEvent string successfully parsed." )

    # Parse and save the IVORN.
    id = v.get_ivorn()
    tok = id.split('#')
    if len(tok) != 2:
        logger.info( "Illegal IVORN: %s" % id )
        return
    stream = tok[0]
    logger.info( "Ivorn: %s" % id )
    localid = tok[1]
    if not streams.has_key(stream):
        return

    # Parse the role of this event.
    role = v.get_role()
    logger.debug( "Event role successfully parsed; role is %s" % role )

    # Ignore all alerts with role "utility."
    if role == 'utility':
        logger.info( "Utility events not used here; rejecting %s" % id )
        return

    # Let SNEWS test events through, but ignore all other tests.
    if stream != 'ivo://nasa.gsfc.gcn/SNEWS' and role == 'test':
        logger.info( "Test events not used here; rejecting %s" % id )
        return

    # If it is a GCN, it will have a packet type.
    p = VOEventLib.Vutil.findParam(v, '', 'Packet_Type')
    if p:
        pt = int(VOEventLib.Vutil.paramValue(p))
        logger.info( "Packet type %s" % pt )
    else:
        logger.info( "No Packet_Type" )
        logger.debug( "This is a non-GCN event; it will be ignored." )
        return     # WARNING we are ignoring all non-GCN events!

    keep = 0  # Save it in the cache: 0 for no save, 1 for save.
    send = 0  # Send it to Gracedb:   0 for no save, 1 for save.

    # SWIFT events: 
    # packet type == 61 means BAT alert       SEND to Gracedb
    # packet_type == 124 means GBM_Test_Pos
    if stream == 'ivo://nasa.gsfc.gcn/SWIFT':
        if pt == 61: 
            keep = 1
            send = 1
            eventObservatory = 'Swift'
            logger.info( 'SWIFT BAT Alert' )

    # Fermi events:
    # packet_type == 110 means GBM_Alert
    # packet_type == 111 means GBM_Flt_Pos
    # packet_type == 112 means GBM_Gnd_Pos    SEND to Gracedb
    # packet_type == 115 means GBM_Fin_Pos    SEND to Gracedb
    # packet_type == 124 means GBM_Test_Pos
    if stream == 'ivo://nasa.gsfc.gcn/Fermi':
        if pt == 110:
            keep = 1
            logger.info( 'Fermi GBM_Alert' )
        # GBM_Flt_Pos notices will be stored because they reference GBM_Alert notices.
        elif pt == 112:
            keep = 1
            send = 1
            eventObservatory = 'Fermi'
            logger.info( 'Fermi GBM_Gnd_Pos' )
        elif pt == 115:
            keep = 1
            send = 1
            logger.info( 'Fermi GBM_Fin_Pos' )

    try:
        # FIXME: It appears that only GBM_Flt_Pos notices contain a Fermi_Likely index,
        #        and we won't be paying attention to them in the future.
        q = VOEventLib.Vutil.findParam(v, '', 'Most_Likely_Index')
        qt = int( VOEventLib.Vutil.paramValue(q) )
        logger.info( "param value q is: %s" % qt )
        logger.info( 'Fermi most likely is %s' % Fermi_Likely[qt] )
    except:
        pass

    # Send all SNEWS events to Gracedb.
    if stream == 'ivo://nasa.gsfc.gcn/SNEWS':
        keep = 1
        send = 1
        eventObservatory = 'SNEWS'
        logger.info( 'SNEWS Alert (may be a test)' )

    # Create a unique label for this event's portfolio.
    pfname = id[6:].replace('/','_')
    pfdir = "%s/%s/%s" % (CACHE, role, pfname)
    logger.debug( "The name for this event's portfolio (derived from its IVORN) is: %s" % pfname )

    # Determine whether this is a portfolio we already have.
    cc = v.get_Citations()
    if cc and cc.get_EventIVORN():
        for c in cc.get_EventIVORN():
            citedivorn = c.get_valueOf_()
            logger.info( "Cites %s" % citedivorn )
            qfname = citedivorn[6:].replace('/','_')
            qfdir = "%s/%s/%s" % (CACHE, role, qfname)
            if os.path.exists(qfdir):
                logger.info( "Found portfolio %s" % qfdir )
                pfdir = qfdir
                keep = 1
                break
            else:
                logger.debug( "No existing event portfolio found; now assuming this event is new." )

    # Determine whether this event has a designation.
    # FIXME: What if it doesn't?
    hasDesignation = False
    if v.Why.Inference[0].get_Name() and send == 1:
        desig = v.Why.Inference[0].get_Name()[0]
        pfname = desig.replace(' ', '')
        hasDesignation = True
        logger.debug( "This event has designation %s; this will be reflected in the filename it is saved under." % desig )

    # If this event has been flagged as one we want to keep, save it to disk.
    if keep == 1:
        if not os.path.exists(pfdir): 
            logger.info( 'Making directory %s' % pfdir )
            if not test:
                os.mkdir(pfdir)
            else:
                logger.warning( "Because the test flag was passed, this directory was not actually made." )

        filename = "%s/%s.xml" % (pfdir, pfname)

        # Continue only if we have NOT already saved this file.
        if test or not os.path.isfile(filename):
            logger.info( "Saving to %s" % filename )
            if not test:
                try:
                    with open(filename, 'w') as f:
                        f.write(payload)
                except:
                    logger.warning( "VOEvent file %s failed to save on disk." % filename )
            else:
                logger.warning( "Because the test flag was passed, this event was not actually saved." )
        else:
            logger.info( "File %s has already been stored; ignoring this Notice." % filename )
            send = 0

    # If it has also been flagged as one to send to GraceDB, send it to GraceDB.
    if send == 1:
        from lalinference.fits import iso8601_to_gps
        from math import floor
        eventType = 'External'
        isotime = VOEventLib.Vutil.getWhereWhen(v)['time'] 
        gpstime = int( floor(iso8601_to_gps(isotime)) )
        event = list( gracedb.events('%s %s..%s' % (eventType, gpstime, gpstime + 1)) )
        if event:
            gid = event[0]['graceid']
            if not test:
                try:
                    replaceit(gid, filename)
                except UnboundLocalError:
                    logger.critical( "GraceDB event %s was not updated because the event was not saved!" % gid )
            else:
                logger.warning( "Because the test flag was passed, GraceDB event %s was not updated." % gid )
        else: 
            if not test:
                try:
                    gid = sendit(filename, eventType, eventObservatory)
                    # FIXME: SNEWS events will ultimately need a Search label other than the default ("GRB").
                    gracedb.writeLog(gid, 'This event detected by %s' % v.How.get_Description()[0], tagname='analyst_comments')
                except UnboundLocalError:
                    logger.critical( "This event failed to save, and therefore could not be uploaded to GraceDB!" )
            else:
                logger.warning( "Because the test flag was passed, this new event was not uploaded to GraceDB." )

        if hasDesignation and not test: gracedb.writeLog(gid, 'This event has been designated %s' % desig, tagname='analyst_comments')

    return
