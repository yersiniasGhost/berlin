from typing import Optional, List, Dict
import random
from dataclasses import dataclass, field
from optimization.genetic_optimizer.abstractions.individual_base import IndividualBase
from models import MonitorConfiguration


# The definition of the optimization individual
class MlfIndividual(IndividualBase):

    def __init__(self, monitor: MonitorConfiguration):
        self.monitor = monitor


    @classmethod
    def create_itself(cls, monitor: MonitorConfiguration) -> "MlfIndividual":
        new_monitor = monitor
        return MlfIndividual(monitor=new_monitor)


    def mutate_function(self, mutate_probability: float):
        pass

    def copy_individual(self) -> "MlfIndividual":
        return MlfIndividual(self.monitor)

    def __str__(self):
        out = f"MlfIndividual: {self.monitor}"
        return out

