#!/usr/bin/env python
"""
Helper module to handle workflow directory structure
"""
__author__ = "Alex Urban <alexander.urban@ligo.org>"

import os


home = os.getenv("HOME")

class directory(object):
    """ Instance of a working directory integrated into the workflow """
    def __init__(self, graceid):
        self.graceid = graceid # unique ID of event in GraCEDb
        self.event_type = graceid[:1] # first character of graceid encodes event type

        # organize events so that no more than 1000 live in one directory
        self.millenium = self.graceid[1:-3] + '000'

        # name the working directory for a given event
        self.name = home + '/working/' + self.event_type + '/' + self.millenium + '/' + self.graceid

    def build_and_move(self):
        """ Method that builds, and then moves to, the working directory """
        # try to build directory ${HOME}/working
        try:
            os.mkdir(home+'/working')
        except OSError:
            pass

        # try to build directory ${HOME}/working/${event_type}
        try:
            os.mkdir(home+'/working/'+self.event_type)
        except OSError:
            pass

        # try to build directory ${HOME}/working/${event_type}/${millenium}
        try:
            os.mkdir(home+'/working/'+self.event_type+'/'+self.millenium)
        except OSError:
            pass

        # try to build directory ${HOME}/working/${event_type}/${millenium}/${graceid}
        try:
            os.mkdir(self.name)
        except OSError:
            print 'Working directory %s already exists' % self.name
            pass

        os.chdir(self.name) # move to the working directory
