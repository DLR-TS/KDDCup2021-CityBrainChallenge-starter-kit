mkdir -p log1x1
touch log1x1/.gitignore
python3 evaluate.py --input_dir qlagent --output_dir log1x1 --sim_cfg cfg/1x1.cfg
