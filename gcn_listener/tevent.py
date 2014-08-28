# Comet VOEvent Broker for LIGO
# John Swinbank, <swinbank@trtransientskp.org>, 2012.
# Matthew J. Graham, <mjg@caltech.edu>, 2012.
# Roy Williams, <roy.williams@ligo.org>, 2013.
# Alex Urban, <alexander.urban@ligo.org>, 2013.

import lxml.etree as ElementTree
from zope.interface import implements
from twisted.plugin import IPlugin
from ..icomet import IHandler

import VOEventLib.VOEvent
import VOEventLib.Vutil

import os, json
from ligo.gracedb.rest import GraceDb


# create instance of gracedb REST API
gracedb = GraceDb()

def sendit(eventFile, group):
    r = gracedb.createEvent(group,"GRB", eventFile).json()
    graceid = r["graceid"]
    print "Link is https://gracedb.ligo.org/events/%s " % graceid
    return graceid

def replaceit(graceid, eventFile):
    gracedb.replaceEvent(graceid, eventFile)
    print "VOEvent file for %s has been updated; Link is https://gracedb.ligo.org/events/%s " % (graceid, graceid)


CACHE = "/home/gdb_processor/gracedb-voevent/comet/comet/cache"

#streams = {'ivo://nasa.gsfc.gcn/AGILE': 'AGILE',
#           'ivo://nasa.gsfc.gcn/Fermi': 'Fermi',
#           'ivo://nasa.gsfc.gcn/INTEGRAL': 'INTEGRAL',
#           'ivo://nasa.gsfc.gcn/MAXI': 'MAXI',
#           'ivo://nasa.gsfc.gcn/SWIFT': 'SWIFT',
#           'ivo://voevent.phys.soton.ac.uk/voevent': '4PISKY',
#}

streams = { 'ivo://nasa.gsfc.gcn/Fermi': 'Fermi',
           'ivo://nasa.gsfc.gcn/SWIFT': 'SWIFT' }

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
         
class EventCatcher(object):
    # Simple example of an event handler plugin. 
    # Selects on stream and role, and saves the good ones.

    # Event handlers must implement IPlugin and IHandler.
    implements(IPlugin, IHandler)

    # The name attribute enables the user to specify plugins they want on the
    # command line.
    name = "catch-event"

    # When the handler is called, it is passed an instance of
    # comet.utility.xml.xml_document.
    def __call__(self, event):
        """
        Print an event to standard output.
        """

        v = VOEventLib.Vutil.parseString(event.text)

        id = v.get_ivorn()
        tok = id.split('#')
        if len(tok) != 2:
            print "Illegal IVORN %s" % id
            return
        stream = tok[0]
        print "Ivorn", id
        localid = tok[1]
        if not streams.has_key(stream):
#            print "Not in list -- rejected"
            return

        role = v.get_role()
#        print "Role ", role

        if role == 'utility':
            print "Utility events not used here %s" % ivorn
            return

        if role == 'test':
            print "Test events not used here %s" % ivorn
            return

# if it is a GCN, it will have a packet type
        p = VOEventLib.Vutil.findParam(v, '', 'Packet_Type')
        if p:
            pt = int(VOEventLib.Vutil.paramValue(p))
            print "Packet type ", pt
        else:
            print "No Packet_Type"
            return     #   WARNING we are ignoring all non-GCN events!

        keep = 0  # save it in the cache
        send = 0  # send it to Gracedb
# SWIFT events, 
# packet type == 61 means BAT alert    SEND to Gracedb
# packet_type == 124 means GBM_Test_Pos
        if stream == 'ivo://nasa.gsfc.gcn/SWIFT':
            if pt == 61: 
                keep = 1
                send = 1
                print 'SWIFT BAT Alert'

# Fermi events
# packet_type == 110 means GBM_Alert      SEND to Gracedb
# packet_type == 111 means GBM_Flt_Pos    SEND to Gracedb
# packet_type == 112 means GBM_Gnd_Pos    SEND to Gracedb
# packet_type == 115 means GBM_Fin_Pos    SEND to Gracedb
# packet_type == 124 means GBM_Test_Pos
        qt = 0
        if stream == 'ivo://nasa.gsfc.gcn/Fermi':
            if pt == 110: 
                keep = 1
                send = 1
                print 'Fermi GBM_Alert'
            elif pt == 111 or pt == 112 :
                q = VOEventLib.Vutil.findParam(v, '', 'Most_Likely_Index')
                qt = int(VOEventLib.Vutil.paramValue(q))
                print "param value q is: ", qt
                print 'Fermi most likely is ', Fermi_Likely[qt]
                send = 1
            elif pt == 115: 
                print 'Fermi GBM_Fin_Pos'
                send = 1

        pfname = id[6:].replace('/','_')
        pfdir = "%s/%s/%s" % (CACHE, role, pfname)

        cc = v.get_Citations()    # does it cite a portfolio we already have?
        if cc and cc.get_EventIVORN():
            for c in cc.get_EventIVORN():
                citedivorn = c.get_valueOf_()
                print "Cites ", citedivorn
                qfname = citedivorn[6:].replace('/','_')
                qfdir = "%s/%s/%s" % (CACHE, role, qfname)
                if os.path.exists(qfdir):
                    print "Found portfolio ", qfdir
                    pfdir = qfdir
                    keep = 1
                    break

        hasDesignation = False
        if v.Why.Inference[0].get_Name() and send == 1:
            pfname = v.Why.Inference[0].get_Name()[0].replace(' ', '')
            hasDesignation = True

        text = VOEventLib.Vutil.stringVOEvent(v)

        if keep == 1:
            if not os.path.exists(pfdir): 
                print 'Making directory ', pfdir
                os.mkdir(pfdir)
            filename = "%s/%s.xml" % (pfdir, pfname)
            print "Saving to ", filename
            f = open(filename, 'w')
            f.write(text)
            f.close()

        if send == 1:
            from lalinference.bayestar.fits import iso8601_to_gps
            eventType = 'Test'
            isotime = VOEventLib.Vutil.getWhereWhen(v)['time'] 
            gpstime = int(floor(iso8601_to_gps(isotime)))
            event = list(gracedb.events('%s %s' % (eventType, gpstime)))
            if event:
                gid = event[0]['graceid']
                replaceit(gid, filename)
            else: 
                gid = sendit(filename, eventType)
                # FIXME: How likely is it that one event could be seen by more than one instrument?
                gracedb.writeLog(gid, 'This event detected by %s' % v.How.get_Description()[0], tagname='analyst_comments')
            #FIXME: In the future, .fits files for GRBs ought to be uploaded here and not as part of the coincidence search
            # During ER4 this is acceptable because not all GRBs are real
            if hasDesignation: gracedb.writeLog(gid, 'This event has been designated %s' % pfname, tagname='analyst_comments')

# This instance of the handler is what actually constitutes our plugin.
catch_event = EventCatcher()
print catch_event.name
