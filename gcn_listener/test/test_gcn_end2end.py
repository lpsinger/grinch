#!/usr/bin/env python

import sys
from comet.utility import xml
from comet.plugins.eventcatch import EventCatcher

args = sys.argv[1:]
filename = args[0]

with open (filename, "r") as f:
    data = f.read()
voevent = xml.xml_document(data)

EventCatcher().__call__( voevent, test=True )
