#!/usr/bin/env python

#
# Coordinator: Alex Urban 
# 	       UW-Milwaukee Department of Physics
#	       Center for Gravitation & Cosmology
#	       <alexander.urban@ligo.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


from distutils.core import setup


setup(
    name='gdb-processor',
    version='0.1',
    url='http://gracedb.ligo.org',
    author='Alex Urban',
    author_email='alexander.urban@ligo.org',
    description='Coordinate between LV alerts, gracedb, and condor job submission automatically; for specifics see README',
    license='GNU General Public License Version 3',
    scripts=[
        'gdb_processor/bin/lowmass_processor.py',
        'gdb_processor/bin/exttrig_processor.py',
        'gdb_processor/bin/dqtolabel.py',
        'gdb_processor/bin/GRB.py',
        'gdb_processor/bin/GW.py',
        'gdb_processor/bin/workflow_helper.py',
        'gdb_processor/bin/lvalertlisten',
        'gdb_processor/bin/plot_allsky',
        'gdb_processor/bin/plot_xcorrelate',
        'gdb_processor/bin/coinc_search',
        'gdb_processor/bin/lowmass_processor_test.py',
        'gdb_processor/etc/lowmass_config.ini',
        'gdb_processor/etc/exttrig_config.ini',
        'gdb_processor/etc/gw_config.ini',
        'gdb_processor/etc/coincdet.ini',
        'gdb_processor/etc/lvalertconfig.ini',
        'gdb_processor/etc/lvalertlisten.sub'
    ]
)
