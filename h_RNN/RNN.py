import random
import numpy as np
import tensorflow as tf
import tensorflow.contrib.layers as layers
import matplotlib.pyplot as plt

from g_CNN.Optimizers import OptFactory
from Util.ProgressBar import ProgressBar


class LSTMCell(tf.contrib.rnn.BasicRNNCell):
    def __call__(self, x, state, scope="LSTM"):
        with tf.variable_scope(scope):
            s_old, h_old = tf.split(state, 2, 1)
            gates = layers.fully_connected(
                tf.concat([x, s_old], 1),
                num_outputs=4 * self._num_units,
                activation_fn=None)
            r1, g1, g2, g3 = tf.split(gates, 4, 1)
            r1, g1, g3 = tf.nn.sigmoid(r1), tf.nn.sigmoid(g1), tf.nn.sigmoid(g3)
            g2 = tf.nn.tanh(g2)
            h_new = h_old * r1 + g1 * g2
            s_new = tf.nn.tanh(h_new) * g3
            return s_new, tf.concat([s_new, h_new], 1)

    @property
    def state_size(self):
        return 2 * self._num_units


class RNNWrapper:
    def __init__(self, **kwargs):
        self._log = {}
        self._optimizer = None
        self._generator = None
        self._tfx = self._tfy = self._output = None
        self._sess = tf.Session()

        self._params = {
            "cell": kwargs.get("cell", LSTMCell),
            "n_time_step": kwargs.get("n_time_step", 10),
            "random_scale": kwargs.get("random_scale", 1),
            "n_hidden": kwargs.get("n_hidden", 128),
            "activation": kwargs.get("activation", tf.nn.sigmoid),
            "lr": kwargs.get("lr", 0.01),
            "epoch": kwargs.get("epoch", 25),
            "n_iter": kwargs.get("n_iter", 128),
            "optimizer": kwargs.get("optimizer", "Adam"),
            "batch_size": kwargs.get("batch_size", 64),
            "eps": kwargs.get("eps", 1e-8),
            "verbose": kwargs.get("verbose", 1)
        }

    def _verbose(self):
        pass

    def fit(self, im, om, generator, cell=None, n_time_step=None, random_scale=None, n_hidden=None, activation=None,
            lr=None, epoch=None, n_iter=None, batch_size=None, optimizer=None, eps=None, verbose=None):
        if cell is None:
            cell = self._params["cell"]
        if n_time_step is None:
            n_time_step = self._params["n_time_step"]
        if random_scale is None:
            random_scale = self._params["random_scale"]
        if n_hidden is None:
            n_hidden = self._params["n_hidden"]
        if activation is None:
            activation = self._params["activation"]
        if lr is None:
            lr = self._params["lr"]
        if epoch is None:
            epoch = self._params["epoch"]
        if n_iter is None:
            n_iter = self._params["n_iter"]
        if optimizer is None:
            optimizer = self._params["optimizer"]
        if batch_size is None:
            batch_size = self._params["batch_size"]
        if eps is None:
            eps = self._params["eps"]
        if verbose is None:
            verbose = self._params["verbose"]

        self._generator = generator(n_time_step, random_scale, im, om)
        self._optimizer = OptFactory().get_optimizer_by_name(optimizer, lr)
        self._tfx = tf.placeholder(tf.float32, shape=[None, None, im])
        self._tfy = tf.placeholder(tf.float32, shape=[None, None, om])

        cell = cell(n_hidden)
        initial_state = cell.zero_state(tf.shape(self._tfx)[1], tf.float32)
        rnn_outputs, rnn_states = tf.nn.dynamic_rnn(
            cell, self._tfx, initial_state=initial_state, time_major=True)
        self._output = tf.map_fn(
            lambda x: layers.fully_connected(x, num_outputs=om, activation_fn=activation),
            rnn_outputs
        )
        err = -tf.reduce_mean(
            self._tfy * tf.log(self._output + eps) + (1 - self._tfy) * tf.log(1 - self._output + eps)
        )
        train_step = self._optimizer.minimize(err)
        self._log["iter_err"] = []
        self._log["epoch_err"] = []

        self._sess.run(tf.global_variables_initializer())
        bar = ProgressBar(max_value=epoch, name="Epoch", start=False)
        if verbose >= 2:
            bar.start()
        for _ in range(epoch):
            epoch_err = 0
            sub_bar = ProgressBar(max_value=n_iter, name="Iter", start=False)
            if verbose >= 2:
                sub_bar.start()
            for __ in range(n_iter):
                x_batch, y_batch = self._generator.gen(batch_size)
                iter_err = self._sess.run([err, train_step], {
                    self._tfx: x_batch, self._tfy: y_batch,
                })[0]
                self._log["iter_err"].append(iter_err)
                epoch_err += iter_err
                if verbose >= 2:
                    sub_bar.update()
            self._log["epoch_err"].append(epoch_err / n_iter)
            if verbose >= 1:
                self._verbose()
                if verbose >= 2:
                    bar.update()

    def draw_err_logs(self):
        ee, ie = self._log["epoch_err"], self._log["iter_err"]
        ee_base = np.arange(len(ee))
        ie_base = np.linspace(0, len(ee) - 1, len(ie))
        plt.figure()
        plt.plot(ie_base, ie, label="Iter error")
        plt.plot(ee_base, ee, linewidth=3, label="Epoch error")
        plt.legend()
        plt.show()


class RNNForAddition(RNNWrapper):
    def __init__(self, **kwargs):
        super(RNNForAddition, self).__init__(**kwargs)
        self._params["boost"] = kwargs.get("boost", 2)

    def _verbose(self):
        x_test, y_test = self._generator.gen(1, self._params["boost"])
        ans = np.argmax(self._sess.run(self._output, {
            self._tfx: x_test
        }), axis=2).ravel()
        x_test = x_test.astype(np.int)
        print("I think {} = {}, answer: {}...".format(
            " + ".join(
                ["".join(map(lambda n: str(n), x_test[..., 0, i][::-1])) for i in range(x_test.shape[2])]
            ),
            "".join(map(lambda n: str(n), ans[::-1])),
            "".join(map(lambda n: str(n), np.argmax(y_test, axis=2).ravel()[::-1]))))


class AdditionGenerator:
    def __init__(self, n_time_step, random_scale, im, base):
        self._n_time_step = n_time_step
        self._random_scale = random_scale
        self._im, self._base = im, base

    def _gen_seq(self, n_time_step, tar):
        seq = []
        for _ in range(n_time_step):
            seq.append(tar % self._base)
            tar //= self._base
        return seq

    def gen(self, batch_size, boost=0):
        if boost:
            n_time_step = self._n_time_step + self._random_scale + random.randint(1, boost)
        else:
            n_time_step = self._n_time_step + random.randint(0, self._random_scale)
        x = np.empty([n_time_step, batch_size, self._im])
        y = np.zeros([n_time_step, batch_size, self._base])
        for i in range(batch_size):
            targets = [int(random.randint(0, self._base ** n_time_step - 1) / self._im) for _ in range(self._im)]
            sequences = [self._gen_seq(n_time_step, tar) for tar in targets]
            for j in range(self._im):
                x[:, i, j] = sequences[j]
            y[range(n_time_step), i, self._gen_seq(n_time_step, sum(targets))] = 1
        return x, y

if __name__ == '__main__':
    _digit_len, _digit_base, _n_digit = 2, 10, 3
    lstm = RNNForAddition(n_time_step=_digit_len, epoch=100, random_scale=2)
    lstm.fit(_n_digit, _digit_base, generator=AdditionGenerator)
    lstm.draw_err_logs()
