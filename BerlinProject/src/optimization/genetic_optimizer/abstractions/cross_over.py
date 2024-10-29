from abc import ABC, abstractmethod
from typing import List
from GeneticOptimizer.abstractions.individual_base import IndividualBase


class CrossOver(ABC):

    def cross_over(self, population: List[IndividualBase]) -> List[IndividualBase]:
        pass
