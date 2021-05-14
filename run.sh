#!/bin/bash
cd `dirname $0`
python3 evaluate.py --input_dir $1 --output_dir $1 --sim_cfg cfg/simulator.cfg
