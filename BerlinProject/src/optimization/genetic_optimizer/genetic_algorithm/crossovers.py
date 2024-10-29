import random
import copy
from typing import List, Tuple


def uniform_crossover_copy(mom: List[any], dad: List[any], independent_probability: float)->Tuple[List[any], List[any]]:
    c1 = copy.copy(mom)
    c2 = copy.copy(dad)
    uniform_crossover(c1, c2, independent_probability=independent_probability)
    return c1, c2


def uniform_crossover(c1: List[any], c2: List[any], independent_probability: float):
    size = min(len(c1), len(c2))
    for i in range(size):
        if random.random() < independent_probability:
            c1[i], c2[i] = c2[i], c1[i]


def simulated_binary_crossover(mom: List[float], dad: List[float], eta: float) -> Tuple[List[float], List[float]]:
    """Executes a simulated binary crossover that modify in-place the input
    individuals. The simulated binary crossover expects :term:`sequence`
    individuals of floating point numbers.

    eta is the Crowding degree of the crossover. A high eta will produce
                children resembling to their parents, while a small eta will
                produce solutions much more different.
    This function uses the :func:`~random.random` function from the python base
    :mod:`random` module.
    """
    c1 = copy.copy(mom)
    c2 = copy.copy(dad)
    for i, (x1, x2) in enumerate(zip(mom, dad)):
        rand = random.random()
        if rand <= 0.5:
            beta = 2. * rand
        else:
            beta = 1. / (2. * (1. - rand))
        beta **= 1. / (eta + 1.)
        c1[i] = 0.5 * (((1 + beta) * x1) + ((1 - beta) * x2))
        c2[i] = 0.5 * (((1 - beta) * x1) + ((1 + beta) * x2))

    return c1, c2
