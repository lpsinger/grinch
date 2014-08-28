#!/usr/bin/env python

# Comet VOEvent Broker for LIGO
# John Swinbank, <swinbank@trtransientskp.org>, 2012.
# Matthew J. Graham, <mjg@caltech.edu>, 2012.
# Roy Williams, <roy.williams@ligo.org>, 2013.
# Alex Urban, <alexander.urban@ligo.org>, 2013

import lxml.etree as ElementTree
from zope.interface import implements
from twisted.plugin import IPlugin
from comet.icomet import IHandler
import os
import VOEventLib
import VOEventLib.Vutil

# store cache directory as global variable
home = os.getenv("HOME")
CACHE = home + "/comet/cache"

streams = {'ivo://nasa.gsfc.gcn/AGILE': 'AGILE',
           'ivo://nasa.gsfc.gcn/Fermi': 'Fermi',
           'ivo://nasa.gsfc.gcn/INTEGRAL': 'INTEGRAL',
           'ivo://nasa.gsfc.gcn/MAXI': 'MAXI',
           'ivo://nasa.gsfc.gcn/SWIFT': 'SWIFT',
           'ivo://voevent.phys.soton.ac.uk/voevent': '4PISKY'}

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
        print "in __call__"

        v = lib.Vutil.parseString(event.text)

        id = v.get_ivorn()
        tok = id.split('#')
        if len(tok) != 2:
            print "Illegal IVORN %s" % id
            return
        stream = tok[0]
        print "Stream: ", stream
        localid = tok[1]
        if not streams.has_key(stream):
            print "Not in list -- rejected"

        role = v.get_role()
        print "Role ", role
        if role == 'utility':
            print "Utility events not used here %s" % ivorn
            return

#        if role == 'test':
#            print "Test events not used here %s" % ivorn
#            return

# SWIFT-BAT tester, i.e. packet type == 61
#        if stream == 'ivo://nasa.gsfc.gcn/SWIFT':
#            p = findParam(v, '', 'Packet_Type')
#            if paramValue(p) != 61:
#                return

        text = lib.Vutil.stringVOEvent(v)
        f = open("%s/%s/%s-%s.xml" % (CACHE, role, streams[stream], localid), 'w')
        f.write(text)
        f.close()

# This instance of the handler is what actually constitutes our plugin.
catch_event = EventCatcher()
print catch_event.name
