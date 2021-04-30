# CityBrainChallenge-starter-kit


## Initial setup
1. Clone the repo git clone `https://github.com/DLR-TS/KDDCup2021-CityBrainChallenge-starter-kit.git`
2. Install docker
3. Change into the directory and do `docker build -t kdd - < Dockerfile`
4. Run `docker run -it -p 3000:3000 -v $PWD:/starter-kit kdd bash`
5. Now you are inside the docker environment. Try `cd starter-kit; python3 evaluate.py --input_dir agent --output_dir out --sim_cfg cfg/simulator.cfg`

### FAQ

1. 
```
IndexError: basic_string::at: __n (which is 18446744073709551615) >= this->size() (which is 2)
```

If your operating system is Windows and you have set `git config --global core.autocrlf true` , when you clone this repo, git will automatically add CR to cfg/simulator.cfg. This will lead to the error in Linux of the docker container.

So please change cfg/simulator.cfg from CRLF to LF after cloning this repo.
