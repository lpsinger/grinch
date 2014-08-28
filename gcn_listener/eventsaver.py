# Comet VOEvent Broker.
# SkyAlert event handler: save a local copy and publish the event to SkyAlert
# Matthew J. Graham, <mjg@caltech.edu>, 2012.

import lxml.etree as ElementTree
import urllib
import os
from zope.interface import implements
from twisted.plugin import IPlugin
from ..icomet import IHandler

#cacheDirectory = "/Users/mjg/Projects/python/voevent/comet/events"
#cacheDirectory = "/envoy5/home/mjg/comet/events"
cacheDirectory = "/home/roy/comet/data"


class EventSaver(object):
    # Simple example of an event handler plugin. This simply prints the
    # received event to standard output.

    # Event handlers must implement IPlugin and IHandler.
    implements(IPlugin, IHandler)

    # The name attribute enables the user to specify plugins they want on the
    # command line.
    name = "save-event"

    # When the handler is called, it is passed an instance of
    # comet.utility.xml.xml_document.
    def __call__(self, event):
        """
        Print an event to standard output and submit it to SkyAlert (if appropriate)
        """
        streams = {'ivo://nasa.gsfc.gcn/AGILE': 'AGILE', 
                   'ivo://nasa.gsfc.gcn/Fermi': 'Fermi', 
                   'ivo://nasa.gsfc.gcn/INTEGRAL': 'INTEGRAL', 
                   'ivo://nasa.gsfc.gcn/MAXI': 'MAXI', 
                   'ivo://nasa.gsfc.gcn/SWIFT': 'SWIFT'} 
        namespaces = {'voe': 'http://www.ivoa.net/xml/VOEvent/v1.1',
                      'von': 'http://www.ivoa.net/xml/VOEvent/v2.0'}
        id = event.element.xpath('/voe:VOEvent/@ivorn', namespaces = namespaces)
        if len(id) == 0: id = event.element.xpath('/von:VOEvent/@ivorn', namespaces = namespaces)
        stream = id[0][:id[0].index("#")]
        print "Stream: ", stream
        id = id[0][6:].replace('/', '_').replace('#', '+')

        role = event.element.xpath('/voe:VOEvent/@role', namespaces = namespaces)
        if len(role) == 0: role = event.element.xpath('/von:VOEvent/@role', namespaces = namespaces)
        print "Role ", role[0]
        if role[0] == 'utility':
            print "Utility events not used here %s" % ivorn
            return

        text = ElementTree.tostring(event.element)
        filename = "%s/%s.xml" % (cacheDirectory, id)
        file = open(filename, 'w')
        file.write(event.text)
        file.close()

#        if stream in streams:
        cmd = 'cd /home/roy/skyalert/loaders; python loader.py file %s' % filename
        print 'executing ', cmd
        os.system(cmd)
        
# This instance of the handler is what actually constitutes our plugin.
save_event = EventSaver()
