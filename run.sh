#!/bin/bash
cd `dirname $0`
python3 evaluate.py --input_dir $1 --output_dir $1 --vehicle_info_path $1 --sim_cfg $1/simulator.cfg
