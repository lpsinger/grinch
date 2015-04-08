#!/usr/bin/env python

import os, sys
import logging
from grinch.gcnhandler import archive  # Function that filters GCN notices

# Pass a VOEvent file as a positional command line argument
args = sys.argv[1:]
filename = args[0]

# Set up logger
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Store the textual content of the VOEvent
with open (filename, "r") as f:
    payload = f.read()

# Call the event filter
archive( payload, test=True )
