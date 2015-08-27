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
    name='grinch',
    version='1.0',
    url='http://gracedb.ligo.org',
    author='Alex Urban',
    author_email='alexander.urban@ligo.org',
    description='Coordinate between GCN notices, LV alerts, gracedb, and condor job submission automatically',
    license='GNU General Public License Version 3',
    py_modules=['argparse'],
    packages=['grinch'],
    scripts=[
        'bin/gdb_processor',
        'bin/gcn_listener',
        'bin/pygcn_listen',
        'bin/cbc_processor',
        'bin/burst_processor',
        'bin/exttrig_processor',
        'bin/dqtolabel',
        'bin/lvalertlisten',
        'bin/unblind_inj_search',
        'bin/find_data',
        'bin/start_comet',
        'bin/approval_processor',
        'bin/lvalert-init_approval_processor',
        'bin/event_supervisor',
        'bin/event_supervisor_wrapper',
        'bin/lvalert-init_event_supervisor',
        'bin/lvalert-run_event_supervisor_wrapper'
    ],
    data_files=[('etc',['etc/cbc_config.ini', 'etc/burst_config.ini', 'etc/exttrig_config.ini',
        'etc/lvalertconfig.ini', 'etc/gcn_config.ini', 'etc/approval_processor_config.ini',
        'etc/approval_processor_lvalert.ini', 'etc/event_supervisor_config.ini',
        'etc/event_supervisor-lvalertconfig.ini', 'etc/event_supervisor.sub'])]
)



