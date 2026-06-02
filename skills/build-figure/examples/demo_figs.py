"""Example brand-figure script. Run it directly, or via the CLI:

    python ../build_figure.py demo_figs.py --theme bone --strict
"""
import brandfig as bf

bf.use("bone")


def bars():
    fig, ax = bf.fig(figsize=(7, 3.4))
    x = ["logreg", "MLP", "CNN", "ResNet", "ViT"]
    acc = [0.71, 0.74, 0.80, 0.87, 0.85]
    ax.bar(x, acc, color=bf.palette(len(x)))
    ax.set_ylim(0.6, 0.95)
    ax.set_ylabel("val accuracy")
    bf.figtitle(fig, "The model ladder")
    bf.save(fig, "ladder.png")


def curve():
    import numpy as np
    fig, ax = bf.fig(figsize=(7, 3.4))
    ep = np.arange(1, 21)
    ax.plot(ep, 1.2 * np.exp(-ep / 6) + 0.15, color=bf.TURQUOISE, label="train")
    ax.plot(ep, 1.2 * np.exp(-ep / 7) + 0.28, color=bf.DEEPPINK, label="val")
    ax.set_xlabel("epoch"); ax.set_ylabel("loss"); ax.legend()
    bf.figtitle(fig, "Learning = loss rolling downhill")
    bf.save(fig, "loss_curve.png")


if __name__ == "__main__":
    bars()
    curve()
    print("demo figures written")
