#!/usr/bin/env python
# Eclipse SUMO, Simulation of Urban MObility; see https://eclipse.org/sumo
# Copyright (C) 2010-2021 German Aerospace Center (DLR) and others.
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# https://www.eclipse.org/legal/epl-2.0/
# This Source Code may also be made available under the following Secondary
# Licenses when the conditions for such availability set forth in the Eclipse
# Public License 2.0 are satisfied: GNU General Public License, version 2
# or later which is available at
# https://www.gnu.org/licenses/old-licenses/gpl-2.0-standalone.html
# SPDX-License-Identifier: EPL-2.0 OR GPL-2.0-or-later

# @file    citybrain_infostep.py
# @author  Jakob Erdmann
# @date    2021-05-07

import os
import sys
import glob
from collections import defaultdict

if 'SUMO_HOME' in os.environ:
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools'))
    sys.path.append(os.path.join(os.environ['SUMO_HOME'], 'tools', 'route'))
import sumolib  # noqa
from sort_routes import sort_departs  # noqa


def get_options(args=None):
    optParser = sumolib.options.ArgumentParser(description="Import citybrains step info")
    optParser.add_argument("-i", "--info-dir", dest="infodir",
                           help="folder for citybrains step info file to import")
    optParser.add_argument("-o", "--output", dest="output",
                           help="define edgeData output filename")
    options = optParser.parse_args(args=args)
    if not options.infodir or not options.output:
        optParser.print_help()
        sys.exit(1)

    return options


def main(options):
    # unsorted temporary file

    waitingTimes = defaultdict(lambda : 0)    
    files = glob.glob(options.infodir + "/info_step*")
    files.sort(key=lambda f : int(f.split()[1].split('.')[0]))
    for infofile in files:
        vehLine = 0
        vehID = None
        pos = None
        edges = []
        speed = None
        lane = None
        seenVehs = 0
        writtenVehs = 0
        numWaiting = 0
        numRunning = 0
        for i, line in enumerate(open(infofile)):
            if i > 0:
                if vehLine == 0:
                    vehID = line.split()[-1]
                elif vehLine == 1:
                    pos = float(line.split()[-1])
                elif vehLine == 2:
                    # assume 3-lane roads
                    lane = 2 - (int(float(line.split()[-1])) % 100)
                elif vehLine == 4:
                    edges = [str(int(float(e))) for e in line.split(":")[-1].split()]
                elif vehLine == 5:
                    speed = line.split()[-1]

                    seenVehs += 1
                    if len(edges) > 1:
                        numRunning += 1
                        if float(speed) <= 0.1:
                            waitingTimes[edges[0]] += 1
                            numWaiting += 1

                vehLine = (vehLine + 1) % 10
        print("parsed %s vehs (%s running, %s waiting, %s%% waiting) from %s" % (seenVehs,
            numRunning, numWaiting, numWaiting * 100 / numRunning, infofile))

    with open(options.output, "w") as outf:
        sumolib.writeXMLHeader(outf, "$Id$", "edgeData")  # noqa
        outf.write('<interval begin="0" end="3600">\n')
        for edge, waitTime in waitingTimes.items():
            outf.write('<edge id="%s" waitingTime="%s"/>\n' % (edge, waitTime))
        outf.write('</interval>\n')
        outf.write('</edgeData>\n')


if __name__ == "__main__":
    if not main(get_options()):
        sys.exit(1)
