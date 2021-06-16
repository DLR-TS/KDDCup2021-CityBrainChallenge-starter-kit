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


def get_options(args=None):
    optParser = argparse.ArgumentParser(description="Import citybrains traffic demand")
    optParser.add_argument("flows", nargs="+",
                           help="citybrains flow file to import")
    optParser.add_argument("-o", "--output", default="routes.py",
                           help="define the output route analysis file")
    optParser.add_argument("-d", "--depth", type=int, default=2,
                           help="depth to look")
    return optParser.parse_args(args=args)


def main(options):
    edgeMap = defaultdict(lambda: defaultdict(int))
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
                        edgeMap[edge][subroute] += (end - begin) / period
                flowLine = (flowLine + 1) % 3
    with open(options.output, "w") as outf:
        print("dist = {", file=outf)
        for edge, freq in edgeMap.items():
            print('  %s : {' % edge, file=outf)
            total = 0
            for subroute, count in freq.items():
                total += count
            for subroute, count in freq.items():
                print('    %s : %s,' % (subroute, count / total), file=outf)
            print('  },', file=outf)
        print("}", file=outf)


if __name__ == "__main__":
    if not main(get_options()):
        sys.exit(1)
