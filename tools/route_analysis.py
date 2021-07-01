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

# @file    flow_analysis.py
# @author  Jakob Erdmann
# @author  Michael Behrisch
# @date    2021-06-16

import os
import sys
import argparse
import json
from collections import defaultdict

import numpy


def get_options(args=None):
    optParser = argparse.ArgumentParser(description="Import citybrains traffic demand")
    optParser.add_argument("flows", nargs="+",
                           help="citybrains flow file to import")
    optParser.add_argument("-o", "--output", default="routes.py",
                           help="define the output route analysis file")
    optParser.add_argument("-n", "--netfile", default=os.path.join(os.path.dirname(__file__), "../data/roadnet_round3.txt"),
                           help="define the network file")
    optParser.add_argument("-d", "--depth", type=int, default=2,
                           help="depth to look")
    return optParser.parse_args(args=args)


def main(options):
    edgeTT = {}
    lastEdge = 0
    for i, line in enumerate(open(options.netfile)):
        if i == 0:
            numNodes = int(line)
        elif i == numNodes + 1:
            numEdges = int(line)
            lastEdge = numNodes + 2 + numEdges * 3
            edgeLine = 0
        elif i < lastEdge:
            if edgeLine == 0:
                fromID, toID, length, speed, nLanes1, nLanes2, edgeID1, edgeID2 = line.split()
                edgeTT[int(edgeID1)] = edgeTT[int(edgeID2)] = float(length) / float(speed)
            edgeLine = (edgeLine + 1) % 3
        elif i == lastEdge:
            break

    edgeMap = defaultdict(lambda: defaultdict(int))
    travelTimes = defaultdict(list)
    volumes = defaultdict(float)
    flowLine = 0
    for flowfile in options.flows:
        for i, line in enumerate(open(flowfile)):
            if i > 0:
                if flowLine == 0:
                    begin, end, period = [float(i) for i in line.split()]
                elif flowLine == 2:
                    edges = [int(e) for e in line.split()]
                    for idx, edge in enumerate(edges):
                        subroute = tuple(edges[idx:idx+options.depth+1])
                        volume = (end - begin) / period
                        edgeMap[edge][subroute] += volume
                        travelTimes[edge].append(sum(edgeTT[e] for e in edges[idx+1:]))
                        volumes[edge] += volume
                flowLine = (flowLine + 1) % 3
    with open(options.output, "w") as outf:
        print("dist = {", file=outf)
        for edge, freq in edgeMap.items():
#            print('  %s : {' % edge, file=outf)
            total = 0
            for subroute, count in freq.items():
                total += count
            for subroute, count in freq.items():
                if count / total > 0.9:
                    print('  %s:  { %s : %s },' % (edge, subroute, count / total), file=outf)
#            print('  },', file=outf)
        print("}", file=outf)
        print("tt = {", file=outf)
        for edge, tt in travelTimes.items():
            avg = numpy.average(tt)
            print('  %s:  ( %s, %s, %s ),' % (edge, numpy.average(tt), numpy.std(tt), volumes[edge]), file=outf)
        print("}", file=outf)


if __name__ == "__main__":
    if not main(get_options()):
        sys.exit(1)
