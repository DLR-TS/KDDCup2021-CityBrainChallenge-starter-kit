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

### FAQ

1. 
```
IndexError: basic_string::at: __n (which is 18446744073709551615) >= this->size() (which is 2)
```

If your operating system is Windows and you have set `git config --global core.autocrlf true` , when you clone this repo, git will automatically add CR to cfg/simulator.cfg. This will lead to the error in Linux of the docker container.

So please change cfg/simulator.cfg from CRLF to LF after cloning this repo.
