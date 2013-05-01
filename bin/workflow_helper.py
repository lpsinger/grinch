#!/usr/bin/env python

__author__ = "Alex Urban <alexander.urban@ligo.org>"

import os


home = os.getenv("HOME")

class directory:
    """ Instance of a working directory integrated into the workflow """
    def __init__(self, graceid):
        self.graceid = graceid # unique ID of event in GraCEDb
        self.char = graceid[:1] # first character of graceid

        # unpack event type
        if self.char == 'G':
            self.event_type = 'GW_Candidate'
        elif self.char == 'E':
            self.event_type = 'ExtTrig'
        else:
            self.event_type = 'Test'

        # organize events so that no more than 1000 live in one directory
        self.millenium = self.graceid[1:-3] + '000'

    def build_and_move(self):
        """ Method that actually builds the working directory """
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
        work = home+'/working/'+self.event_type+'/'+self.millenium+'/'+self.graceid
        try:
            os.mkdir(work)
        except OSError:
            print 'Working directory %s already exists' % work
            pass

        os.chdir(work) # move to the working directory
