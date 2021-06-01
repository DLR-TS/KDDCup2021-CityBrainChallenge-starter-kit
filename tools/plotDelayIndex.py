import os,sys
import matplotlib
import matplotlib.pyplot as plt  # noqa
import json
from glob import glob

dirs = sys.argv[1:]

for d in dirs:
    xdata = []
    ydata = []
    files = glob(d + "/scores*.json")
    files = [(int(os.path.basename(f)[6:-5]), f) for f in files if os.path.basename(f) != "scores.json"]
    files.sort()
    for step, f in files:
        data = json.load(open(f))
        xdata.append(step)
        ydata.append(float(data['data']['delay_index']))
    plt.plot(xdata, ydata, label=d)

plt.legend()
plt.show()
