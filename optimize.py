#!/usr/bin/env python3
import os
import argparse
import shutil
import subprocess

#from optimparallel import minimize_parallel

def run_evaluation(par, names, agent):
    if agent.endswith("/"):
        agent = agent[:-1]
    par_agent = agent + "_".join(["_".join(p) for p in zip(names, [str(pp) for pp in par])])
    print("copying", agent, "to", par_agent)
    shutil.rmtree(par_agent, ignore_errors=True)
    shutil.copytree(agent, par_agent)
    with open(os.path.join(agent, "gym_cfg.py")) as cfg_in, open(os.path.join(par_agent, "gym_cfg.py"), "w") as cfg:
        for line in cfg_in:
            ls = line.split()
            for n, val in zip(names, par):
                if ls and ls[0] == n:
                    ls[2] = str(val)
                    line = " ".join(ls)
                    break
            cfg.write(line)
    subprocess.call("docker run -it -v $PWD:/starter-kit kdd /starter-kit/run.sh %s" % par_agent, shell=True)
    return 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("agent")
    args = parser.parse_args()

    init = []
    ranges = []
    names = []
    for line in open(os.path.join(args.agent, "gym_cfg.py")):
        r = None
        if "optimized" in line:
            ls = line.split()
            try:
                initial = float(ls[2]) 
                r = (float(ls[-2]), float(ls[-1]))
            except:
                pass
        if r:
            init.append(initial)
            ranges.append(r)
            names.append(ls[0])
    print("optimizing", names, init, ranges)
    num_steps = 10
    for idx in range(len(init)):
        step = (ranges[idx][1] - ranges[idx][0]) / num_steps
        values = list(init)
        for i in range(num_steps):
            values[idx] = ranges[idx][0] + i * step
            run_evaluation(values, names, args.agent)
#    opt = minimize_parallel(run_evaluation, init, names, bounds=ranges)
