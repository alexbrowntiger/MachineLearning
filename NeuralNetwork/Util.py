import os
import sys
import time
import pickle
import numpy as np
import matplotlib.pyplot as plt

from config import *


def get_cache_path(path):
    return "Data/data.cache" if path is None else path[:path.rfind(".")] + ".cache"


def clear_cache(path, clear=CLEAR_CACHE):
    path = get_cache_path(path)
    if clear and os.path.isfile(path):
        os.remove(path)


def get_cache(path):
    path = get_cache_path(path)
    try:
        with open(path, "rb") as file:
            nn_data = pickle.load(file)
        return nn_data
    except FileNotFoundError:
        return None


def do_cache(path, data):
    path = get_cache_path(path)
    with open(path, "wb") as file:
        pickle.dump(data, file)


def data_cleaning(line):
    # line = line.replace('"', "")
    return list(map(lambda c: c.strip(), line.split(",")))


def get_data(path=None, n_classes=CLASSES_NUM):
    path = "Data/data.txt" if path is None else path
    categories = None

    x = []
    with open(path, "r") as file:
        flag = None
        for line in file:
            if SKIP_FIRST and flag is None:
                flag = True
                continue

            line = data_cleaning(line)

            tmp_x = []
            if not DATA_CLEANED:
                if categories is None:
                    categories = [{"flag": 1, _l: 0} for _l in line]
                for i, _l in enumerate(line):
                    if not WHETHER_NUMERICAL[i]:
                        if _l in categories[i]:
                            tmp_x.append(categories[i][_l])
                        else:
                            tmp_x.append(categories[i]["flag"])
                            categories[i][_l] = categories[i]["flag"]
                            categories[i]["flag"] += 1
                    else:
                        tmp_x.append(float(_l))
            else:
                for i, _l in enumerate(line):
                    if i == TAR_IDX:
                        tmp_x.append(int(_l))
                    elif not WHETHER_EXPAND[i]:
                        tmp_x.append(float(_l))
                    else:
                        _l = int(_l)
                        for _i in range(EXPAND_NUM_LST[i]):
                            if _i == _l - 1:
                                tmp_x.append(1)
                            else:
                                tmp_x.append(0)

            x.append(tmp_x)

    classes_num = categories[TAR_IDX]["flag"] if n_classes is None else n_classes
    expand_sum = sum(EXPAND_NUM_LST[:TAR_IDX])
    expand_seq = np.array(EXPAND_NUM_LST[:TAR_IDX]) > 0
    assert isinstance(expand_seq, np.ndarray), "Never mind. You'll never see this error"
    expand_num = np.sum(expand_seq)
    expand_total = expand_sum - expand_num
    y = np.array([xx.pop(TAR_IDX + expand_total) for xx in x])
    y = np.array([[0 if i != yy else 1 for i in range(classes_num)] for yy in y])

    return np.array(x), y


def get_and_cache_data(path=None, n_classes=CLASSES_NUM):
    clear_cache(path)
    _data = get_cache(path)

    if _data is None:
        x, y = get_data(path, n_classes)
        do_cache(path, (x, y))
    else:
        x, y = _data

    return x, y


def get_graphs_from_logs():
    with open("Results/logs.dat", "rb") as file:
        logs = pickle.load(file)
    for (hus, ep, bt), log in logs.items():
        hus = list(map(lambda _c: str(_c), hus))
        title = "hus: {} ep: {} bt: {}".format(
            "- " + " -> ".join(hus) + " -", ep, bt
        )
        fb_log, acc_log = log["fb_log"], log["acc_log"]
        xs = np.arange(len(fb_log)) + 1
        plt.figure()
        plt.title(title)
        plt.plot(xs, fb_log)
        plt.plot(xs, acc_log, c="g")
        plt.savefig("Results/img/" + "{}_{}_{}".format(
            "-".join(hus), ep, bt
        ))
        plt.close()


def init_size_and_path(size, path):
    size = int(size)
    path = "Data/data.txt" if path is None else path
    return size, path


def gen_xor(size, scale, path=None):
    size, path = init_size_and_path(size, path)
    with open(path, "w") as file:
        quarter_size = int(size / 4)
        seq1 = np.random.random(size=quarter_size) * scale
        seq2 = np.random.random(size=quarter_size) * scale
        seq = list(zip(seq1, seq2))
        x0 = [(str(_s1), str(_s2)) for _s1, _s2 in seq]
        x1 = [(str(-_s1), str(_s2)) for _s1, _s2 in seq]
        x2 = [(str(-_s1), str(-_s2)) for _s1, _s2 in seq]
        x3 = [(str(_s1), str(-_s2)) for _s1, _s2 in seq]
        for i, x in enumerate((x0, x1, x2, x3)):
            file.write("\n".join([",".join(_x) + ",{}".format(i % 2) for _x in x]) + "\n")


def gen_random(size, scale, path=None):
    size, path = init_size_and_path(size, path)
    quarter_size = int(size / 4)
    with open(path, "w") as file:
        xs = (2 * np.random.rand(size, 2) - 1) * scale
        xs = list(map(lambda v: (str(v[0]), str(v[1])), xs))
        ans = np.random.randint(2, size=quarter_size * 4)
        file.write("\n".join([",".join(x) + ",{}".format(y) for x, y in zip(xs, ans)]) + "\n")


def gen_spin(size, n_classes=2, path=None):
    size, path = init_size_and_path(size, path)
    dimension = 2
    xs = np.zeros((size * n_classes, dimension))
    ys = np.zeros(size * n_classes, dtype='uint8')
    for j in range(n_classes):
        ix = range(size * j, size * (j + 1))
        r = np.linspace(0.0, 1, size)
        t = np.array(
            np.linspace(j * (n_classes + 1), (j + 1) * (n_classes + 1), size) +
            np.array(np.random.random(size=size)) * 0.2)
        xs[ix] = np.c_[r * np.sin(t), r * np.cos(t)]
        ys[ix] = j

    with open(path, "w") as file:
        xs = list(map(lambda v: (str(v[0]), str(v[1])), xs))
        file.write("\n".join([",".join(x) + ",{}".format(y) for x, y in zip(xs, ys)]) + "\n")


class ProgressBar:
    def __init__(self, min_value=None, max_value=None, width=30):
        self._min, self._max = min_value, max_value
        self._task_length = int(max_value - min_value) if (
            min_value is not None and max_value is not None
        ) else None
        self._counter = min_value
        self._bar_width = int(width)
        self._terminated = False
        self._started = False
        self._clock = 0
        self._cost = 0

    def _flush(self):

        if not self._started:
            print("Progress bar not started yet.")
        elif self._terminated:
            sys.stdout.write(
                "\r" + "## ({:d} : {:d} -> {:d}) Task Finished. Time cost: {:8.6}; Average: {:8.6}".format(
                    self._task_length, self._min, self._max, self._cost, self._cost / self._task_length
                ) + " ##        "
            )
        else:

            self._cost = time.time() - self._clock
            if self._counter > self._min:
                tmp_hour = int(self._cost / 3600)
                tmp_min = int(self._cost / 60)
                tmp_sec = self._cost % 60
                tmp_avg = self._cost / (self._counter - self._min)
                tmp_avg_hour = int(tmp_avg / 3600)
                tmp_avg_min = int(tmp_avg / 60)
                tmp_avg_sec = tmp_avg % 60
            else:
                tmp_hour = 0
                tmp_min = 0
                tmp_sec = 0
                tmp_avg_hour = 0
                tmp_avg_min = 0
                tmp_avg_sec = 0

            passed = int(self._counter * self._bar_width / self._max)
            sys.stdout.write("\r" + "## [" + "-" * passed + " " * (self._bar_width - passed) + "] : {} / {}".format(
                self._counter, self._max
            ) + " ##   Time Cost: {:3d} h {:4d} min {:8.6} s; Average: {:3d} h {:4d} min {:8.6} s ".format(
                tmp_hour, tmp_min, tmp_sec, tmp_avg_hour, tmp_avg_min, tmp_avg_sec
            ) if self._counter != self._min else "##  Progress bar initialized  ##")

            sys.stdout.flush()

            if self._counter >= self._max:
                self._terminated = True
                self._flush()

    def set_min(self, min_val):
        if self._max is not None:
            if self._max <= min_val:
                print("Target min_val: {} is larger than current max_val: {}".format(min_val, self._max))
                return
            self._task_length = self._max - min_val
        self._counter = self._min = min_val

    def set_max(self, max_val):
        if self._min is not None:
            if self._min >= max_val:
                print("Target max_val: {} is smaller than current min_val: {}".format(max_val, self._min))
                return
            self._task_length = max_val - self._min
        self._max = max_val

    def update(self, new_value):
        if new_value != self._min:
            self._counter = self._max if new_value >= self._max else int(new_value)
            self._flush()

    def start(self):
        if self._task_length is None:
            print("Error: Progress bar not initialized properly.")
            return
        self._clock = time.time()
        self._started = True
        self._flush()


if __name__ == '__main__':
    gen_spin(100)
