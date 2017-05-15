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
    def __init__(self):
        self._log = {}
        self._im = self._om = None
        self._optimizer = self._generator = None
        self._tfx = self._tfy = self._input = self._output = None
        self._sess = tf.Session()

        self._squeeze = False
        self._activation = tf.nn.sigmoid

    def _verbose(self):
        x_test, y_test = self._generator.gen(1, True)
        axis = 1 if self._squeeze else 2
        if len(y_test.shape) == 1:
            y_true = y_test
        else:
            y_true = np.argmax(y_test, axis=axis).ravel()  # type: np.ndarray
        y_pred = np.argmax(self._sess.run(self._output, {self._tfx: x_test}), axis=axis).ravel()  # type: np.ndarray
        print("Test acc: {:8.6} %".format(np.mean(y_true == y_pred) * 100))

    def _define_input(self, im, om):
        self._input = self._tfx = tf.placeholder(tf.float32, shape=[None, None, im])
        if self._squeeze:
            self._tfy = tf.placeholder(tf.float32, shape=[None, om])
        else:
            self._tfy = tf.placeholder(tf.float32, shape=[None, None, om])

    def _get_loss(self, eps):
        return -tf.reduce_mean(
            self._tfy * tf.log(self._output + eps) + (1 - self._tfy) * tf.log(1 - self._output + eps)
        )

    def _get_output(self, rnn_outputs, rnn_states, n_history):
        if n_history == 0 and self._squeeze:
            raise ValueError("'n_history' should not be 0 when trying to squeeze the outputs")
        if n_history == 1 and self._squeeze:
            outputs = rnn_outputs[..., -1, :]
        else:
            outputs = rnn_outputs[..., -n_history:, :]
            if self._squeeze:
                outputs = tf.reshape(outputs, [-1, n_history * int(outputs.get_shape()[2])])
        self._output = layers.fully_connected(
            outputs, num_outputs=self._om, activation_fn=self._activation)

    def fit(self, im, om, generator, cell=LSTMCell,
            n_hidden=128, n_history=0, squeeze=None, activation=None,
            lr=0.01, epoch=10, n_iter=128, batch_size=64, optimizer="Adam", eps=1e-8, verbose=1):
        if squeeze:
            self._squeeze = True
        if callable(activation):
            self._activation = activation
        self._generator = generator
        self._im, self._om = im, om
        self._optimizer = OptFactory().get_optimizer_by_name(optimizer, lr)
        self._define_input(im, om)

        cell = cell(n_hidden)
        initial_state = cell.zero_state(tf.shape(self._input)[0], tf.float32)
        rnn_outputs, rnn_states = tf.nn.dynamic_rnn(
            cell, self._input, initial_state=initial_state)
        self._get_output(rnn_outputs, rnn_states, n_history)
        loss = self._get_loss(eps)
        train_step = self._optimizer.minimize(loss)
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
                iter_err = self._sess.run([loss, train_step], {
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


class RNNForOp(RNNWrapper):
    def __init__(self, boost=2):
        super(RNNForOp, self).__init__()
        self._boost = boost
        self._op = ""

    def _verbose(self):
        x_test, y_test = self._generator.gen(1, boost=self._boost)
        ans = np.argmax(self._sess.run(self._output, {
            self._tfx: x_test
        }), axis=2).ravel()
        x_test = x_test.astype(np.int)
        print("I think {} = {}, answer: {}...".format(
            " {} ".format(self._op).join(
                ["".join(map(lambda n: str(n), x_test[0, ..., i][::-1])) for i in range(x_test.shape[2])]
            ),
            "".join(map(lambda n: str(n), ans[::-1])),
            "".join(map(lambda n: str(n), np.argmax(y_test, axis=2).ravel()[::-1]))))


class RNNForAddition(RNNForOp):
    def __init__(self, boost=2):
        super(RNNForAddition, self).__init__(boost)
        self._op = "+"


class RNNForMultiple(RNNForOp):
    def __init__(self, boost=2):
        super(RNNForMultiple, self).__init__(boost)
        self._op = "*"


class Generator:
    def __init__(self, im=None, om=None, **kwargs):
        self._im, self._om = im, om

    def gen(self, batch, test=False, **kwargs):
        pass


class OpGenerator(Generator):
    def __init__(self, im, om, n_time_step, random_scale):
        super(OpGenerator, self).__init__(im, om)
        self._base = self._om
        self._n_time_step = n_time_step
        self._random_scale = random_scale

    def _op(self, seq):
        return 0

    def _gen_seq(self, n_time_step, tar):
        seq = []
        for _ in range(n_time_step):
            seq.append(tar % self._base)
            tar //= self._base
        return seq

    def _gen_targets(self, n_time_step):
        return []

    def gen(self, batch_size, test=False, boost=0):
        if boost:
            n_time_step = self._n_time_step + self._random_scale + random.randint(1, boost)
        else:
            n_time_step = self._n_time_step + random.randint(0, self._random_scale)
        x = np.empty([batch_size, n_time_step, self._im])
        y = np.zeros([batch_size, n_time_step, self._om])
        for i in range(batch_size):
            targets = self._gen_targets(n_time_step)
            sequences = [self._gen_seq(n_time_step, tar) for tar in targets]
            for j in range(self._im):
                x[i, ..., j] = sequences[j]
            y[i, range(n_time_step), self._gen_seq(n_time_step, self._op(targets))] = 1
        return x, y


class AdditionGenerator(OpGenerator):
    def _op(self, seq):
        return sum(seq)

    def _gen_targets(self, n_time_step):
        return [int(random.randint(0, self._om ** n_time_step - 1) / self._im) for _ in range(self._im)]


class MultipleGenerator(OpGenerator):
    def _op(self, seq):
        return np.prod(seq)

    def _gen_targets(self, n_time_step):
        return [int(random.randint(0, self._om ** n_time_step - 1) ** (1 / self._im)) for _ in range(self._im)]

if __name__ == '__main__':
    _random_scale = 2
    _digit_len, _digit_base, _n_digit = 2, 10, 3
    _generator = AdditionGenerator(
        _n_digit, _digit_base,
        n_time_step=_digit_len, random_scale=_random_scale
    )
    lstm = RNNForAddition()
    lstm.fit(
        _n_digit, _digit_base, _generator,
        # cell=tf.contrib.rnn.GRUCell,
        # cell=tf.contrib.rnn.LSTMCell,
        # cell=tf.contrib.rnn.BasicRNNCell,
        # cell=tf.contrib.rnn.BasicLSTMCell,
        epoch=100
    )
    lstm.draw_err_logs()
