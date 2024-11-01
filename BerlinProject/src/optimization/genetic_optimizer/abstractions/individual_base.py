from abc import ABC, abstractmethod


class IndividualBase(ABC):
    instance_count = 0

    def __init__(self, source: str = "base"):
        self.source: str = source
        self.instance_id = IndividualBase.instance_count
        IndividualBase.instance_count += 1

    @abstractmethod
    def copy_individual(self, source: str = "base") -> "IndividualBase":
        raise NotImplementedError
