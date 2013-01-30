#
# Copyright (C) 2012  Leo Singer
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


#
# Hey, Alex,
#
# This setup.py script is copied from bayestar-localization. It includes an
# example of a Python namespace package (a directory containing an empty
# __init__.py file), a C extension (a Python module written in C), and a bunch
# of executable Python scripts. Of these three features, you may need only the
# last.
#
# One more thing: This script uses setuptools (a.k.a. Python Distribute)
# instead of the Python standard library's distutils. Setuptools and distutils
# are very similar; in fact almost all of the setuptools classes are subclasses
# of the corresponding classes in distutils with just a few extra features.
# After you have made your modifications, if you replace all occurrences of
# setuptools with distutils below, you should get the same results.
#
# Best,
# Leo
#


from setuptools import setup
from misc import *
from misc.setuptools_openmp import *
import numpy as np
import os


healpixdir = os.getenv('HEALPIXDIR')
if healpixdir is None:
    healpix_include_dirs = []
    healpix_library_dirs = []
else:
    healpix_include_dirs = [os.path.join(healpixdir, 'include')]
    healpix_library_dirs = [os.path.join(healpixdir, 'lib')]


setup(
    name='bayestar-localization',
    version='0.0.5',
    author='Leo Singer',
    author_email='leo.singer@ligo.org',
    description='Rapid Bayesian sky maps for gravitational wave inspirals',
    license='GNU General Public License Version 3',
    requires=['bayestar', 'healpy', 'numpy', 'glue', 'pylal', 'lal', 'lalsimulation'],
    namespace_packages=['bayestar'],
    packages=['bayestar'],
    ext_modules=[
        Extension('bayestar.sky_map', ['bayestar/sky_map.c', 'bayestar/bayestar_sky_map.c'],
            **copy_library_dirs_to_runtime_library_dirs(
            **pkgconfig('lal', 'lalsimulation', 'gsl',
                include_dirs=[np.get_include()] + healpix_include_dirs,
                library_dirs=healpix_library_dirs,
                libraries=['cfitsio', 'chealpix'],
                extra_compile_args=['-std=c99'],
                define_macros=[('HAVE_INLINE', None)],
                openmp=True
            ))
        )
    ],
    scripts=[
        'bin/bayestar_localize_gracedb',
        'bin/bayestar_localize_lvalert',
        'bin/bayestar_cluster_coincs',
        'bin/bayestar_realize_coincs',
        'bin/bayestar_localize_coincs',
        'bin/bayestar_sim_to_tmpltbank',
        'bin/ligolw_coire_to_coinc',
        'bin/littlehope'
    ],
    cmdclass={'build_ext': build_ext}
)
