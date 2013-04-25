#!/usr/bin/env python

# Copyright (C) 2011  Leo Singer
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


# Slight modifications made to the following code by Alex Urban of UWM;
# Originally a part of the bayestar-localization package, and written
# by Leo Singer


"""
Plot a pointing of several telescopes.
"""
__author__ = "Leo Singer <leo.singer@ligo.org> and Alex Urban <alexander.urban@ligo.org>"


# Command line interface

from optparse import Option, OptionParser
opts, args = OptionParser(
    description = __doc__,
    usage = "%prog [options] [INPUT]",
    option_list = [
        Option("-o", "--output", metavar="FILE.{pdf,png}",
            help="name of output file"),
        Option("--skymap", metavar="FILE.fits",
            help="name of HEALPix .fits file containing GW skymap"),
        Option("--colormap", default="jet",
            help="name of matplotlib colormap (default is jet)"),
        Option("--figure-width", type=float, default=12.,
            help="width of figure in inches (default = 12 in.)"),
        Option("--figure-height", type=float, default=9.,
            help="height of figure in inches (default = 9 in.)"),
        Option("--contour", metavar="PERCENT", type=float, action="append",
            default=[10,50,90], help="plot contour enclosing this percentage of"
            + " probability mass (may be specified multiple times; default is "
            + " 10%, 50% and 90%"),
        Option("-t","--trigger",metavar="FILE.fits",
            help="name of HEALPix .fits file containing skymap of external trigger")
    ]
).parse_args()

# Late imports

# Choose a matplotlib backend that is suitable for headless
# rendering if output to file is requested
import matplotlib
matplotlib.use('agg')

from matplotlib import patches
import numpy as np
import matplotlib.pyplot as plt
import healpy
import cPickle
from bayestar import io
from bayestar.site import data as site_data
from bayestar import plot

fig = plt.figure(figsize=(opts.figure_width, opts.figure_height), frameon=False)
ax = plt.subplot(111, projection='astro mollweide')
ax.cla()

if len(args) > 0:
    sitekeys, pointings, prob = cPickle.load(open(args[0], 'rb'))

    for key, (theta, phi) in zip(sitekeys, pointings):
        site = site_data[key]
        # FIXME: Remove this after all Matplotlib monkeypatches are obsolete.
        if plot.mpl_version < '1.2.0':
            vert_lists = plot.cut_dateline(plot.make_rect_poly(0.5 * site['w'], 0.5 * site['h'], theta, phi))
        else:
            vert_lists = plot.cut_prime_meridian(plot.make_rect_poly(0.5 * site['w'], 0.5 * site['h'], theta, phi))
        for vert_list in vert_lists:
            ax.add_patch(patches.Polygon(vert_list, edgecolor='k', facecolor='0.5', alpha=0.5))
    plt.title('Detection probability: %.2g' % prob, fontsize=10.)

if opts.skymap is not None:
    data = io.read_skymap(opts.skymap)
    skymap = data['skymap']
    #skymap = healpy.read_map(opts.skymap)
    nside = healpy.npix2nside(len(skymap))

    # Convert sky map from probability to probability per square degree.
    probperdeg2 = skymap / healpy.nside2pixarea(nside, degrees=True)

    # Plot sky map.
    vmax = probperdeg2.max()
    plot.healpix_heatmap(probperdeg2, vmin=0., vmax=vmax, cmap=plt.get_cmap(opts.colormap))

    # Plot colorbar.
    cb = plot.colorbar(vmax)

    # Set colorbar label.
    cb.set_label(r'$\mathrm{prob.}$ $\mathrm{per}$ $\mathrm{deg}^2$')

    # Add contours.
    if opts.contour:
        indices = np.argsort(-skymap)
        region = np.empty(skymap.shape)
        region[indices] = 100 * np.cumsum(skymap[indices])
        cs = plot.healpix_contour(region, colors='k', linewidths=0.5, levels=opts.contour)
        plt.clabel(cs, fmt='$\mathbf{%g\%%}$', fontsize=6, inline=True)

    # Add marker at sky location of external trigger, if there is one.
    if opts.trigger is not None:
        data = io.read_skymap(opts.trigger)
        trig_map = data['skymap']
        index, nside2 = np.argmax(trig_map), healpy.npix2nside(len(trig_map))
        theta, phi = healpy.pix2ang(nside2,index)
        ax.scatter([phi],[np.pi/2 - theta],s=90,c='w',marker='*')


# If we are using a new enough version of matplotlib, then
# add a white outline to all text to make it stand out from the background.
plot.outline_text(ax)

fig.patch.set_alpha(0.)
ax.patch.set_alpha(0.)
ax.set_alpha(0.)

tickmarks = np.arange(2,24,2)
ax.set_xticklabels(['$\mathbf{%s^{\mathrm{h}}}$'%n for n in tickmarks])

plt.savefig(opts.output)
