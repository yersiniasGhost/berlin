from abc import ABC, abstractmethod


class IndividualBase(ABC):
    pass

    @abstractmethod
    def copy_individual(self) -> "IndividualBase":
        raise NotImplementedError
