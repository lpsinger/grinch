#!/usr/bin/env python

import sys
from comet.utility import xml  # Needed to pass a VOEvent to the event filter
from comet.plugins.eventcatch import EventCatcher  # Class that filters GCN notices

# Pass a VOEvent file as a positional command line argument
args = sys.argv[1:]
filename = args[0]

# Convert the contents of that VOEvent to an instance of the class xml_document
with open (filename, "r") as f:
    data = f.read()
voevent = xml.xml_document(data)

# Call the event catcher
EventCatcher().__call__( voevent, test=True )
