mkdir -p log_warm_up
touch log_warm_up/.gitignore
python3 evaluate.py --input_dir qlagent --output_dir log_warm_up --sim_cfg cfg/warm_up.cfg
