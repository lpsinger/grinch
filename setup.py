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
	version='1.3',
	url='http://gracedb.ligo.org',
	author='Alex Urban',
	author_email='alexander.urban@ligo.org',
	description='Coordinate between LV alerts, gracedb, and condor job submission automatically',
	license='GNU General Public License Version 3',
	packages=['gracedb_events'],
	py_modules=['workflow_helper', 'argparse', 'GWDataFindClient'],
	scripts=[
		'bin/gdb_processor',
		'bin/lowmass_processor',
		'bin/exttrig_processor',
		'bin/dqtolabel',
		'bin/lvalertlisten',
		'bin/raven_coinc_search_gracedb',
		'bin/unblind_inj_search',
		'bin/find_data'
	],
	data_files=[('etc',['etc/lowmass_config.ini','etc/exttrig_config.ini',
		'etc/lvalertconfig.ini'])]
)
