from NN import *

np.random.seed(142857)  # for reproducibility


def main():
    log = ""

    nn = NN()
    save = False
    load = False
    show_loss = True
    train_only = False
    visualize = False
    verbose = 2

    lr = 0.001
    lb = 0.001
    epoch = 10
    record_period = 1

    timing = Timing(enabled=True)
    timing_level = 1

    import pickle

    with open("Data/mini_mnist.dat", "rb") as file:
        x, y = pickle.load(file)

    x = x.reshape(len(x), 1, 28, 28)
    # x = x.reshape(len(x), -1)

    draw = True

    if not load:

        nn.add("ConvTanh", (x.shape[1:], (16, 3, 3)))
        nn.add("ConvTanh", ((16, 3, 3), ))
        nn.add("MaxPool", ((2, 2), ), 2)
        nn.add("ConvNorm")
        nn.add("ConvELU", ((32, 3, 3), ))
        nn.add("ConvELU", ((32, 3, 3), ))
        nn.add("MaxPool", ((2, 2), ), 2)
        nn.add("ConvNorm", momentum=0.8)

        # nn.add("ReLU", (x.shape[1], 400))
        nn.add("ReLU", (400, ))
        # nn.add("Normalize")
        nn.add("CrossEntropy", (y.shape[1], ))

        nn.optimizer = "Adam"

        nn.preview()
        nn.feed_timing(timing)

        nn.fit(x, y, lr=lr, lb=lb,
               epoch=epoch, batch_size=256, record_period=record_period,
               show_loss=show_loss, train_only=train_only,
               do_log=True, verbose=verbose, visualize=visualize)
        if save:
            nn.save()
        if draw:
            nn.draw_conv_series(x[:3])
            nn.draw_conv_weights()
        nn.draw_results()

    else:

        nn.load("Models/Model")
        nn.feed(x, y)
        nn.preview()
        nn.fit(epoch=5, lr=lr, lb=lb, verbose=verbose)
        if visualize:
            nn.visualize_2d()
        if draw:
            nn.draw_conv_series(x[6:9])
        # nn.draw_results()

        acc = nn.evaluate(x, y)[0]
        log += "Whole set Accuracy  : {:12.6} %".format(100 * acc) + "\n"

        print()
        print("=" * 30 + "\n" + "Results\n" + "-" * 30)
        print(log)

    timing.show_timing_log(timing_level)


if __name__ == '__main__':
    main()
