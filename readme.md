# CityBrainChallenge-starter-kit


## Initial setup
1. Clone the repo `git clone https://github.com/DLR-TS/KDDCup2021-CityBrainChallenge-starter-kit.git`
2. Install docker (`sudo apt install docker.io; sudo adduser $USER docker; sudo reboot`)
3. Change into the directory and do `docker build -t kdd - < Dockerfile`

## Run the example / your code
0. `git pull`, if the Dockerfile changed also run the build command from above again
1. Run `docker run -it -p 3000:3000 -v $PWD:/starter-kit kdd bash`
2. Now you are inside the docker environment. Try `cd starter-kit; python3 evaluate.py --input_dir agent --output_dir out --sim_cfg cfg/simulator.cfg`

## Testing visualization
1.  `cd ui/src`
2.  `mkdir log; cp ../../log/*.json log`
3.  Edit index.js and add the mapbox token and set maxTime to a lower value, delete all unneeded `time*.json`
4.  `yarn start`
5.  Open http://localhost:3000 in your web browser

## Run optimization
Edit the gym_cfg.py in your agent dir. Every line of the form "PARAM=value" which also contains the keyword optimized and the range of values will be evaluated by the optimize script. Example:
```
HEADWAY = 2.0  # to be optimized 1.5 2.5
```
will trigger an optimization of the HEADWAY value between 1.5 and 2.5 with 2.0 as initial value (currently not used).
Then run `./optimize.py myagent`

## Docker Tricks and other useful commands
1. Copy a docker container to a different machine

`docker save kdd | bzip2 | pv | ssh user@machine 'bunzip2 | docker load`

2. Kill all running docker processes

`docker kill $(docker ps -q)`

3. Run your agent without bash

`docker run -v $PWD:/starter-kit kdd /starter-kit/run.sh myagent`


### FAQ

1. 
```
IndexError: basic_string::at: __n (which is 18446744073709551615) >= this->size() (which is 2)
```

If your operating system is Windows and you have set `git config --global core.autocrlf true` , when you clone this repo, git will automatically add CR to cfg/simulator.cfg. This will lead to the error in Linux of the docker container.

So please change cfg/simulator.cfg from CRLF to LF after cloning this repo.
